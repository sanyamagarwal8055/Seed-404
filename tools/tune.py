"""Tune an agent's weights against a pool of opponents with a (1+lambda) evolution strategy.

Needs only catanatron (no catan_kit), so it runs on the team machine or any laptop:

    python tools/tune.py --agent agents/v04_tuned/agent.py --minutes 40 --workers 7

Each generation: the incumbent and LAMBDA mutants (1 to 3 weights multiplied by exp(N(0, SIGMA)),
signs kept, public_vps fixed) play GAMES games against every opponent on the SAME fresh seeds
(paired comparison, seats alternated). The best mutant must beat the incumbent there AND again on a
second fresh seed block (guards against the winner's curse) before it becomes the incumbent.
Fitness = mean win rate over the opponents. Seeds start at 200000 (never 100000 or 990000).
Every candidate is logged to --log (CSV); the incumbent is written to --best (JSON) on each change.
The agent must accept Agent(weights=dict). Opponents: "F" (catanatron's ValueFunctionPlayer) or a
path to any agent.py with an Agent class.
"""
import argparse
import csv
import importlib.util
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_OPPS = ["F", "opponents/road_army_f.py", "opponents/card_hoarder.py",
                "agents/v01_catan_fixes/agent.py"]

_mods = {}


def load(path):
    if path not in _mods:
        spec = importlib.util.spec_from_file_location(f"m{len(_mods)}", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _mods[path] = m
    return _mods[path]


class Obs:
    def __init__(self, game, me):
        self.game, self.me, self.cpu_left, self.turn = game, me, None, game.state.num_turns

    def sample_world(self, rng):
        return self.game.copy()


def make_player(spec, color, weights=None):
    from catanatron.models.player import Player
    if spec == "F":
        from catanatron.players.value import ValueFunctionPlayer
        return ValueFunctionPlayer(color)
    mod = load(spec)

    class Wrapped(Player):
        def __init__(self):
            super().__init__(color)
            self.agent = mod.Agent(weights=weights) if weights is not None else mod.Agent()

        def decide(self, game, actions):
            if len(actions) == 1:
                return actions[0]
            try:
                i = self.agent.decide(Obs(game, color), actions)
                return actions[i] if 0 <= i < len(actions) else actions[0]
            except Exception:
                return actions[0]
    return Wrapped()


def play_chunk(task):
    """task = (agent_path, weights, opp_spec, seeds) -> (wins, games)."""
    agent_path, weights, opp, seeds = task
    from catanatron.game import Game
    from catanatron.models.player import Color
    wins = 0
    for seed in seeds:
        first = seed % 2 == 0
        me, them = (Color.RED, Color.BLUE) if first else (Color.BLUE, Color.RED)
        a = make_player(agent_path, me, weights)
        b = make_player(opp, them)
        random.seed(seed)
        try:
            game = Game([a, b] if first else [b, a], seed=seed)
            wins += game.play() == me
        except Exception:
            pass
    return wins, len(seeds)


def evaluate(pool, agent, cands, opps, seeds, chunk=10):
    tasks, index = [], []
    for ci, w in enumerate(cands):
        for oi, opp in enumerate(opps):
            for k in range(0, len(seeds), chunk):
                tasks.append((agent, w, opp, seeds[k:k + chunk]))
                index.append((ci, oi))
    rates = [[0.0] * len(opps) for _ in cands]
    counts = [[0] * len(opps) for _ in cands]
    for (ci, oi), (wins, n) in zip(index, pool.map(play_chunk, tasks)):
        rates[ci][oi] += wins
        counts[ci][oi] += n
    return [[r / max(c, 1) for r, c in zip(rr, cc)] for rr, cc in zip(rates, counts)]


def mutate(w, rng, sigma, keys):
    m = dict(w)
    for k in rng.sample(keys, rng.randint(1, 3)):
        m[k] = w[k] * math.exp(rng.gauss(0, sigma))
    return m


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--agent", required=True)
    p.add_argument("--opps", nargs="+", default=DEFAULT_OPPS)
    p.add_argument("--start", help="JSON weights to start from (default: the agent's own)")
    p.add_argument("--minutes", type=float, default=40)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--lam", type=int, default=10, help="mutants per generation")
    p.add_argument("--games", type=int, default=40, help="games per opponent per candidate")
    p.add_argument("--sigma", type=float, default=0.7, help="log-scale mutation size")
    p.add_argument("--seed0", type=int, default=200000)
    p.add_argument("--log", default=os.path.join(HERE, "tune_log.csv"))
    p.add_argument("--best", default=os.path.join(HERE, "tune_best.json"))
    a = p.parse_args()
    assert a.seed0 >= 200000, "tune on seeds 200000+ only"

    agent = os.path.abspath(a.agent)
    opps = [o if o == "F" else os.path.abspath(o if os.path.isabs(o) else os.path.join(ROOT, o))
            for o in a.opps]
    mod = load(agent)
    inc = json.load(open(a.start)) if a.start else mod.load_weights()
    inc = {k: float(v) for k, v in inc.items()}
    keys = [k for k, v in inc.items() if k != "public_vps" and v != 0]
    rng = random.Random(a.seed0)
    names = [os.path.basename(os.path.dirname(o)) if o.endswith("agent.py") else
             os.path.basename(o)[:-3] if o != "F" else "F" for o in opps]

    new_log = not os.path.exists(a.log)
    log = open(a.log, "a", newline="")
    out = csv.writer(log)
    if new_log:
        out.writerow(["time", "gen", "role", "seed_block", "mean"] + names + ["weights"])
    end = time.time() + 60 * a.minutes
    block = a.seed0
    with Pool(a.workers) as pool:
        gen = 0
        while time.time() < end:
            seeds = list(range(block, block + a.games))
            cands = [inc] + [mutate(inc, rng, a.sigma, keys) for _ in range(a.lam)]
            fits = evaluate(pool, agent, cands, opps, seeds)
            means = [sum(f) / len(f) for f in fits]
            for ci, (w, f, m) in enumerate(zip(cands, fits, means)):
                out.writerow([time.strftime("%H:%M:%S"), gen, "incumbent" if ci == 0 else "mutant",
                              block, f"{m:.4f}"] + [f"{x:.3f}" for x in f] + [json.dumps(w)])
            best = max(range(1, len(cands)), key=lambda i: means[i])
            msg = f"gen {gen}: incumbent {means[0]:.3f}, best mutant {means[best]:.3f}"
            block += a.games
            if means[best] > means[0]:
                seeds2 = list(range(block, block + a.games))
                f2 = evaluate(pool, agent, [inc, cands[best]], opps, seeds2)
                m2 = [sum(f) / len(f) for f in f2]
                for role, w, f, m in (("confirm_inc", inc, f2[0], m2[0]),
                                      ("confirm_mut", cands[best], f2[1], m2[1])):
                    out.writerow([time.strftime("%H:%M:%S"), gen, role, block, f"{m:.4f}"]
                                 + [f"{x:.3f}" for x in f] + [json.dumps(w)])
                block += a.games
                msg += f" | confirm {m2[0]:.3f} vs {m2[1]:.3f}"
                if means[best] + m2[1] > means[0] + m2[0]:
                    inc = cands[best]
                    json.dump(inc, open(a.best, "w"), indent=1)
                    msg += " -> ACCEPTED"
            log.flush()
            print(msg, flush=True)
            gen += 1
    log.close()
    json.dump(inc, open(a.best, "w"), indent=1)
    print("final weights in", a.best)


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    main()
