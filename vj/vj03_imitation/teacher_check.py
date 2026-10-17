"""How strong are catanatron's slow search players against F when they get unlimited time?

Plays full games with catanatron directly (perfect information, no harness, no clock), seats
alternated, in parallel. A player that wins clearly here is a teacher worth imitating (vj03).
Tuning seeds only (400000 and up).

    cd catan-agent-hackathon
    .venv\\Scripts\\python ..\\Seed-404\\vj\\vj03_imitation\\teacher_check.py --games 40 --workers 14
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from catan_kit._patch import ensure_hash_seed  # noqa: E402


def make(kind, color):
    from catanatron.players.minimax import AlphaBetaPlayer, SameTurnAlphaBetaPlayer
    from catanatron.players.value import ValueFunctionPlayer
    if kind == "F":
        return ValueFunctionPlayer(color)
    if kind == "AB2":
        return AlphaBetaPlayer(color, depth=2, prunning=True)
    if kind == "AB3":
        return AlphaBetaPlayer(color, depth=3, prunning=True)
    if kind == "STAB2":
        return SameTurnAlphaBetaPlayer(color, depth=2, prunning=True)
    raise ValueError(kind)


def play(args):
    import random
    import time

    from catanatron import Color, Game

    kind, seed = args
    random.seed(seed)
    me_first = seed % 2 == 0
    colors = [Color.RED, Color.BLUE]
    kinds = [kind, "F"] if me_first else ["F", kind]
    players = [make(k, c) for k, c in zip(kinds, colors)]
    t = time.process_time()
    game = Game(players, seed=seed, vps_to_win=10)
    winner = game.play()
    me = colors[0] if me_first else colors[1]
    return kind, winner == me, winner is None, time.process_time() - t


def main():
    ensure_hash_seed()
    import argparse
    import multiprocessing as mp

    p = argparse.ArgumentParser()
    p.add_argument("--kinds", nargs="+", default=["AB2", "STAB2"])
    p.add_argument("--games", type=int, default=40)
    p.add_argument("--seed0", type=int, default=400000)
    p.add_argument("--workers", type=int, default=14)
    a = p.parse_args()
    jobs = [(k, a.seed0 + i) for k in a.kinds for i in range(a.games)]
    with mp.Pool(a.workers) as pool:
        res = pool.map(play, jobs, chunksize=1)
    for k in a.kinds:
        r = [x for x in res if x[0] == k]
        wins = sum(x[1] for x in r)
        n = len(r)
        rate = wins / n
        print(f"{k:6} vs F: {wins}/{n} = {rate:.3f} +-{1.96 * (rate * (1 - rate) / n) ** 0.5:.3f}, "
              f"no winner {sum(x[2] for x in r)}, {sum(x[3] for x in r) / n:.1f} s CPU per game (both players)")


if __name__ == "__main__":
    main()
