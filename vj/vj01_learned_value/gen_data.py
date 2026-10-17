"""Generate training data for vj01: positions (agent.py's feature_dict) labelled with who won.

Plays full games with catanatron directly (perfect information, no harness, no clock: only win/loss
labels matter here, so CPU timing is irrelevant and a laptop is fine). Each game picks a pairing:

    v01 vs F, v01 vs v01, F vs F

and every player makes a uniformly random legal move with probability EPS, so the data covers
positions the greedy players would never reach on their own. Every STRIDE-th tick the position is
recorded from BOTH players' point of view (P0 = the player in question), with label 1 if that player
went on to win. Games that hit the turn limit without a winner are dropped.

Seeds: 200000 and up only (the tuning range). Never 990000, which is reserved for judging.

Run from the kit folder so catan_kit is importable, for example:

    cd catan-agent-hackathon
    .venv\\Scripts\\python ..\\Seed-404\\vj\\vj01_learned_value\\gen_data.py --games 4000 --workers 14 --out ..\\vj_data\\run1
"""
import os
import sys

sys.path.insert(0, os.getcwd())  # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
V01_PATH = os.path.join(HERE, "..", "..", "agents", "v01_catan_fixes", "agent.py")
AGENT_PATH = os.path.join(HERE, "agent.py")   # feature_dict lives there, shared with play time

EPS = 0.10       # chance of a uniformly random legal move, per decision
STRIDE = 4       # record every STRIDE-th tick
SEED0 = 200000   # tuning range; never 990000
PAIRINGS = ("v01_F", "v01_v01", "F_F")


def _load(path, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_player(kind, color, rng, v01_value, f_value):
    from catanatron.models.player import Player

    fn = v01_value if kind == "v01" else f_value

    class ValuePlayer(Player):
        def decide(self, game, playable_actions):
            if len(playable_actions) == 1:
                return playable_actions[0]
            if rng.random() < EPS:
                return playable_actions[rng.randrange(len(playable_actions))]
            best, best_v = playable_actions[0], None
            for action in playable_actions:
                g = game.copy()
                try:
                    g.execute(action)
                except Exception:
                    continue
                v = fn(g, self.color)
                if best_v is None or v > best_v:
                    best, best_v = action, v
            return best

    return ValuePlayer(color)


def play_one(seed):
    """Play one game; return (X float32 [n, features], y int8 [n], meta) or None if no winner."""
    import random

    import numpy as np
    from catanatron import Color, Game
    from catanatron.players.value import DEFAULT_WEIGHTS, get_value_fn

    global _V01, _F, _FEAT
    if "_V01" not in globals():
        _V01 = _load(V01_PATH, "v01_agent").value
        _F = get_value_fn("base_fn", DEFAULT_WEIGHTS)
        _FEAT = _load(AGENT_PATH, "vj01_agent")

    rng = random.Random(seed)
    random.seed(seed)
    pairing = PAIRINGS[seed % len(PAIRINGS)]
    kinds = pairing.split("_")
    if rng.random() < 0.5:
        kinds = kinds[::-1]
    colors = [Color.RED, Color.BLUE]
    players = [_make_player(k, c, rng, _V01, _F) for k, c in zip(kinds, colors)]
    game = Game(players, seed=seed, vps_to_win=10)

    rows, owners, ticks = [], [], 0
    while game.winning_color() is None and game.state.num_turns < 1000:
        if ticks % STRIDE == 0:
            for c in colors:
                rows.append(_FEAT.feature_vector(game, c, feature_names()))
                owners.append(c)
        game.play_tick()
        ticks += 1
    winner = game.winning_color()
    if winner is None or not rows:
        return None
    X = np.asarray(rows, dtype=np.float32)
    y = np.asarray([1 if c == winner else 0 for c in owners], dtype=np.int8)
    return X, y, (seed, pairing, ticks)


def feature_names():
    """Sorted feature names, from one position of a fresh game (the key set never changes)."""
    global _NAMES
    if "_NAMES" not in globals():
        from catanatron import Color, Game
        from catanatron.models.player import SimplePlayer
        g = Game([SimplePlayer(Color.RED), SimplePlayer(Color.BLUE)], seed=0)
        _NAMES = sorted(_load(AGENT_PATH, "vj01_agent").feature_dict(g, Color.RED))
    return _NAMES


def main():
    ensure_hash_seed()  # may restart this process with PYTHONHASHSEED=0
    import argparse
    import multiprocessing as mp
    import time

    import numpy as np

    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed0", type=int, default=SEED0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", required=True, help="output prefix; writes <out>.npz")
    a = p.parse_args()
    assert a.seed0 >= 200000 and (a.seed0 + a.games <= 990000 or a.seed0 >= 1000000), \
        "use tuning seeds only (200000 and up, never 990000-999999)"

    seeds = list(range(a.seed0, a.seed0 + a.games))
    t0 = time.time()
    Xs, ys, gids, metas = [], [], [], []
    with mp.Pool(a.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(play_one, seeds, chunksize=4), 1):
            if res is not None:
                X, y, meta = res
                Xs.append(X)
                ys.append(y)
                gids.append(np.full(len(y), meta[0], dtype=np.int32))
                metas.append(meta)
            if i % 200 == 0 or i == len(seeds):
                print(f"{i}/{len(seeds)} games, {time.time() - t0:.0f} s", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(a.out + ".npz", X=np.concatenate(Xs), y=np.concatenate(ys),
                        game=np.concatenate(gids), names=np.array(feature_names()),
                        pairing=np.array([m[1] for m in metas]), seeds=np.array([m[0] for m in metas]))
    n = sum(len(y) for y in ys)
    print(f"done: {len(metas)} games with a winner of {len(seeds)}, {n} positions, "
          f"{time.time() - t0:.0f} s -> {a.out}.npz")


if __name__ == "__main__":
    main()
