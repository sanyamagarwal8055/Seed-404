"""vj04: tune v01's value-function weights directly on win rate against F (evolution strategy).

Search space: log10 of every weight of F's value function (except public_vps, fixed at 3e14 as the
scale) plus v01's four extras (2:1 port, 3:1 port, road, army). F's weights work almost
lexicographically (points 3e14, production 1e8, reachability 1e4, ...), so the search moves whole
orders of magnitude, not percentages. Signs stay as in v01 (enemy_production and discard_penalty
negative). Starts from v01.

Each generation samples LAMBDA candidates around the mean, plays each one GAMES games against F
(catanatron directly, perfect information, no clock: one-move greedy players, seats alternated, the
same fresh boards for every candidate in a generation), and moves the mean towards the best MU.
Every EVAL_EVERY generations the mean itself is played on more games, and the best measured mean is
kept. Seeds 500000 and up (tuning range). Writes progress to <out>/log.txt and the best weights to
<out>/best.json, and builds a self-contained agent at vj/vj04_tuned/agent.py.

    cd catan-agent-hackathon
    .venv\\Scripts\\python ..\\Seed-404\\vj\\vj04_tuned\\tune_es.py --out ..\\vj_data\\es1 --minutes 45 --workers 14
"""
import json
import math
import os
import sys

sys.path.insert(0, os.getcwd())

from catan_kit._patch import ensure_hash_seed  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# name: (log10 of |v01 value|, sign)
START = {
    "production": (8.0, 1), "enemy_production": (8.0, -1), "num_tiles": (0.0, 1),
    "reachable_production_0": (4.0, 1), "reachable_production_1": (4.0, 1),
    "buildable_nodes": (3.0, 1), "longest_road": (1.0, 1), "hand_synergy": (2.0, 1),
    "hand_resources": (0.0, 1), "discard_penalty": (math.log10(5), -1), "hand_devs": (1.0, 1),
    "army_size": (math.log10(10.1), 1),
    "PORT2": (math.log10(3e7), 1), "PORT3": (7.0, 1), "ROAD": (math.log10(3e6), 1),
    "ARMY": (math.log10(3e6), 1),
}
NAMES = list(START)
PUBLIC_VPS = 3e14


def weights_of(x):
    return {n: START[n][1] * 10 ** x[i] for i, n in enumerate(NAMES)}


def make_value(w):
    from catanatron.features import build_production_features
    from catanatron.models.enums import RESOURCES
    from catanatron.players.value import base_fn
    from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

    params = {k: w[k] for k in NAMES if k not in ("PORT2", "PORT3", "ROAD", "ARMY")}
    params["public_vps"] = PUBLIC_VPS
    base = base_fn(params)
    prod = build_production_features(True)

    def value(game, color):
        v = base(game, color)
        ports = game.state.board.get_player_port_resources(color)
        if ports:
            s = prod(game, color)
            for r in ports:
                if r is None:
                    v += w["PORT3"] * sum(s[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
                else:
                    v += w["PORT2"] * s[f"EFFECTIVE_P0_{r}_PRODUCTION"]
        v += w["ROAD"] * min(get_longest_road_length(game.state, color), 8)
        v += w["ARMY"] * min(get_played_dev_cards(game.state, color, "KNIGHT"), 4)
        return v

    return value


def play(task):
    """One game, candidate (weights w) against F; returns (cand, won)."""
    import random

    from catanatron import Color, Game
    from catanatron.models.player import Player
    from catanatron.players.value import DEFAULT_WEIGHTS, base_fn

    cand, w, seed = task
    value = make_value(w)
    f_value = base_fn(DEFAULT_WEIGHTS)

    class Greedy(Player):
        def __init__(self, color, fn):
            super().__init__(color)
            self.fn = fn

        def decide(self, game, playable_actions):
            if len(playable_actions) == 1:
                return playable_actions[0]
            best, best_v = playable_actions[0], None
            for a in playable_actions:
                g = game.copy()
                try:
                    g.execute(a)
                except Exception:
                    continue
                v = self.fn(g, self.color)
                if best_v is None or v > best_v:
                    best, best_v = a, v
            return best

    random.seed(seed * 2 + (seed % 2))
    us_first = (seed // 1) % 2 == 0
    colors = [Color.RED, Color.BLUE]
    fns = [value, f_value] if us_first else [f_value, value]
    game = Game([Greedy(c, f) for c, f in zip(colors, fns)], seed=seed, vps_to_win=10)
    winner = game.play()
    me = colors[0] if us_first else colors[1]
    return cand, winner == me


def write_agent(x, rate, games, path):
    w = weights_of(x)
    src = open(os.path.join(HERE, "..", "..", "agents", "v01_catan_fixes", "agent.py"), encoding="utf-8").read()
    body = src[src.index("import random"):]
    lines = ["WEIGHTS = dict(DEFAULT_WEIGHTS)"]
    lines += [f'WEIGHTS["{n}"] = {w[n]!r}' for n in NAMES if n not in ("PORT2", "PORT3", "ROAD", "ARMY")]
    head = body[:body.index("WEIGHTS = dict(DEFAULT_WEIGHTS)")]
    tail = body[body.index("BASE = base_fn(WEIGHTS)"):]
    consts = (f"PORT2 = {w['PORT2']!r}   # x our production of the resource a 2:1 port we own trades\n"
              f"PORT3 = {w['PORT3']!r}   # x our total production, if we own a 3:1 port\n"
              f"ROAD = {w['ROAD']!r}    # x our longest road length, capped at 8\n"
              f"ARMY = {w['ARMY']!r}    # x knights we have played, capped at 4\n\n")
    doc = ('"""vj04_tuned (parent: v01_catan_fixes). Jainam\'s experiment: v01 with every weight tuned\n'
           "on win rate against F by an evolution strategy (tune_es.py, seeds 500000 and up,\n"
           "perfect-information games). Only the numbers below differ from v01.\n"
           f"Tuner's own estimate for these weights: {rate:.3f} over {games} games against F.\n"
           '"""\n')
    open(path, "w", encoding="utf-8").write(doc + head + "\n".join(lines) + "\n\n" + consts + tail)


def main():
    ensure_hash_seed()
    import argparse
    import multiprocessing as mp
    import random
    import time

    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--minutes", type=float, default=45)
    p.add_argument("--workers", type=int, default=14)
    p.add_argument("--lam", type=int, default=14)
    p.add_argument("--mu", type=int, default=5)
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--sigma", type=float, default=0.7)
    p.add_argument("--eval-every", type=int, default=4)
    p.add_argument("--eval-games", type=int, default=300)
    p.add_argument("--seed0", type=int, default=500000)
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    log = open(os.path.join(a.out, "log.txt"), "a")

    def say(msg):
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    rng = random.Random(1)
    mean = [START[n][0] for n in NAMES]
    sigma = a.sigma
    rw = [math.log(a.mu + 0.5) - math.log(i + 1) for i in range(a.mu)]
    rw = [r / sum(rw) for r in rw]
    seed = a.seed0
    best = None
    t0 = time.time()
    gen = 0
    with mp.Pool(a.workers) as pool:
        def evaluate(xs, games):
            nonlocal seed
            seeds = list(range(seed, seed + games))
            seed += games
            tasks = [(c, weights_of(x), s) for c, x in enumerate(xs) for s in seeds]
            wins = [0] * len(xs)
            for c, won in pool.imap_unordered(play, tasks, chunksize=2):
                wins[c] += won
            return [w / games for w in wins]

        while True:
            gen += 1
            cands = [[m + sigma * rng.gauss(0, 1) for m in mean] for _ in range(a.lam)]
            rates = evaluate(cands, a.games)
            order = sorted(range(a.lam), key=lambda i: -rates[i])
            mean = [sum(rw[k] * cands[order[k]][j] for k in range(a.mu)) for j in range(len(NAMES))]
            sigma = max(0.15, sigma * 0.95)
            say(f"gen {gen:3d}  {time.time() - t0:5.0f} s  sigma {sigma:.2f}  "
                f"candidates best {rates[order[0]]:.2f}  median {sorted(rates)[a.lam // 2]:.2f}")
            last = time.time() - t0 > a.minutes * 60
            if gen % a.eval_every == 0 or last:
                r = evaluate([mean], a.eval_games)[0]
                say(f"  mean measured {r:.3f} over {a.eval_games} games: "
                    + ", ".join(f"{n}={START[n][1] * 10 ** v:.3g}" for n, v in zip(NAMES, mean)))
                if best is None or r > best[0]:
                    best = (r, list(mean))
                    json.dump({"rate": r, "games": a.eval_games, "log10": dict(zip(NAMES, mean)),
                               "weights": weights_of(mean)}, open(os.path.join(a.out, "best.json"), "w"),
                              indent=1)
                    write_agent(mean, r, a.eval_games, os.path.join(HERE, "agent.py"))
                    say(f"  new best -> {os.path.join(HERE, 'agent.py')}")
            if last:
                break
    say(f"done: best measured mean {best[0]:.3f}")


if __name__ == "__main__":
    main()
