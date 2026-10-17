"""Is alpha-beta search on v04's tuned value function a teacher clearly stronger than v04 itself?

Distillation only pays if the teacher is much stronger than the student. catanatron's AlphaBeta on F's
value function only tied F (vj03 teacher_check), so here the same search runs on v04's tuned value.
Perfect information, no clock, catanatron directly. Seeds 410000 and up (tuning range).

    cd Seed-404
    ..\\catan-agent-hackathon\\.venv\\Scripts\\python vj\\vj05_distill\\teacher_v04.py --games 84 --workers 14
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V04 = os.path.join(ROOT, "agents", "v04_tuned", "agent.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make(kind, color, depth):
    from catanatron.models.player import Player
    from catanatron.players import minimax
    from catanatron.players.value import ValueFunctionPlayer

    v04 = _load(V04, "v04")
    value = v04.Value(v04.load_weights())
    if kind == "F":
        return ValueFunctionPlayer(color)
    if kind == "AB":
        minimax.get_value_fn = lambda *a, **k: value   # AlphaBeta scores leaves with v04's value
        return minimax.AlphaBetaPlayer(color, depth=depth, prunning=True)

    class Greedy(Player):        # v04's own decision rule, perfect information
        def decide(self, game, actions):
            if len(actions) == 1:
                return actions[0]
            best, best_v = actions[0], None
            for a in actions:
                g = game.copy()
                try:
                    g.execute(a)
                except Exception:
                    continue
                v = value(g, self.color)
                if best_v is None or v > best_v:
                    best, best_v = a, v
            return best

    return Greedy(color)


def play(args):
    import random
    import time

    from catanatron import Color, Game

    a, b, seed, depth = args
    random.seed(seed)
    first = seed % 2 == 0
    colors = [Color.RED, Color.BLUE]
    kinds = [a, b] if first else [b, a]
    t = time.process_time()
    game = Game([make(k, c, depth) for k, c in zip(kinds, colors)], seed=seed, vps_to_win=10)
    winner = game.play()
    me = colors[0] if first else colors[1]
    return (a, b), winner == me, time.process_time() - t


def main():
    import argparse
    import multiprocessing as mp

    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=84)
    p.add_argument("--workers", type=int, default=14)
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--seed0", type=int, default=410000)
    a = p.parse_args()
    pairs = [("AB", "v04"), ("AB", "F"), ("v04", "F")]
    jobs = [(x, y, a.seed0 + i, a.depth) for x, y in pairs for i in range(a.games)]
    with mp.Pool(a.workers) as pool:
        res = pool.map(play, jobs, chunksize=1)
    for pr in pairs:
        r = [x for x in res if x[0] == pr]
        w, n = sum(x[1] for x in r), len(r)
        rate = w / n
        print(f"{pr[0]:>3} (depth {a.depth}) vs {pr[1]:3}: {w}/{n} = {rate:.3f} +-{1.96 * (rate * (1 - rate) / n) ** 0.5:.3f}"
              f"   {sum(x[2] for x in r) / n:.1f} s CPU per game")


if __name__ == "__main__":
    main()
