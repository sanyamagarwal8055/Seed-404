"""Tune v01's weights by evolution strategy, on this machine only.

    cd ~/seed404/catan-hackathon-agent && .venv/bin/python ../Seed-404/tuning/tune.py --until 15:20

Fitness = mean of the win rate against F (200 games) and road_army_f (120 games), on boards that
rotate every generation (200000 and up, never 100000 or 990000). Each generation plays the current
best (the incumbent) and 5 children on the SAME boards, and the best of the six becomes the incumbent.
A child changes 3 random weights by a random factor (log scale). Everything is logged to log.csv.
Run validate.py afterwards: the winner of a noisy search is partly luck, so it is checked on fresh boards.
"""
import os
import sys

sys.path.insert(0, os.getcwd())          # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = ["production", "enemy_production", "num_tiles", "reachable_production_0",
          "reachable_production_1", "buildable_nodes", "hand_synergy", "hand_resources", "hand_devs",
          "PORT2", "PORT3", "ROAD", "ARMY", "ROAD_REL"]
#: ROAD_REL is an absolute weight in the template (0 = off); the tuner searches it as a factor on this
ROAD_REL_BASE = 1e7


def make_candidate(mult, workdir, name):
    """A folder holding agent.py (the template) and weights.json; returns the agent.py path."""
    import json
    import shutil
    d = os.path.join(workdir, name)
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(HERE, "agent_template.py"), os.path.join(d, "agent.py"))
    with open(os.path.join(d, "weights.json"), "w") as fh:
        json.dump({"mult": mult}, fh)
    return os.path.join(d, "agent.py")


def _chunk(args):
    from catan_kit import match
    path_a, path_b, seeds, idx = args
    records, _ = match.play_chunk(path_a, path_b, seeds, idx)
    return sum(r["winner"] == "a" for r in records), len(records)


def evaluate(pool, agent_path, plan, seed0):
    """Win rate of agent_path against each opponent. plan = [(opponent path, boards, chunks), ...]:
    `boards` boards from seed0, each played twice (both seats), split into `chunks` parallel tasks."""
    tasks, owner = [], []
    for oi, (opp, pairs, chunks) in enumerate(plan):
        for k in range(chunks):
            mine = list(range(k, pairs, chunks))
            idx = [i for p in mine for i in (2 * p, 2 * p + 1)]
            tasks.append((agent_path, opp, [seed0 + i // 2 for i in idx], idx))
            owner.append(oi)
    wins, games = [0] * len(plan), [0] * len(plan)
    for oi, (w, n) in zip(owner, pool.map(_chunk, tasks)):
        wins[oi] += w
        games[oi] += n
    return [w / n for w, n in zip(wins, games)]

def main():
    ensure_hash_seed()          # may restart this process with PYTHONHASHSEED=0
    import argparse
    import concurrent.futures as cf
    import csv
    import datetime
    import json
    import math
    import multiprocessing as mp
    import random
    import tempfile
    import time

    import catan_kit

    kit = os.path.dirname(os.path.dirname(os.path.abspath(catan_kit.__file__)))
    p = argparse.ArgumentParser()
    p.add_argument("--until", required=True, help="stop starting generations at this local time, HH:MM")
    p.add_argument("--pairs-f", type=int, default=100, help="boards against F (2 games each)")
    p.add_argument("--pairs-r", type=int, default=60, help="boards against road_army_f (2 games each)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--children", type=int, default=5)
    p.add_argument("--sigma", type=float, default=0.4, help="step size, in powers of 10")
    p.add_argument("--seed0", type=int, default=200000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--start", help="best.json to start from (log10_mult); default: v01 itself")
    p.add_argument("--out-dir", default=HERE, help="where log.csv and best.json go")
    p.add_argument("--no-probes", action="store_true", help="skip the hand-picked first round")
    p.add_argument("--wide", type=float, default=0.2, help="chance that a child takes one wide step (x10)")
    args = p.parse_args()

    f_path = os.path.join(kit, "examples", "f_agent.py")
    r_path = os.path.abspath(os.path.join(HERE, "..", "opponents", "road_army_f.py"))
    # split the 8 workers in proportion to the games: 200 F games in 5 tasks, 120 in 3 (40 games each)
    if args.pairs_r > 0:
        cf_ = max(1, round(args.workers * args.pairs_f / (args.pairs_f + args.pairs_r)))
        plan = [(f_path, args.pairs_f, cf_), (r_path, args.pairs_r, max(1, args.workers - cf_))]
    else:                                     # F only: every worker plays F
        plan = [(f_path, args.pairs_f, args.workers)]
    until = datetime.datetime.combine(datetime.date.today(),
                                      datetime.datetime.strptime(args.until, "%H:%M").time())
    rng = random.Random(args.seed)
    work = tempfile.mkdtemp(prefix="tune-")
    os.makedirs(args.out_dir, exist_ok=True)
    log_path = os.path.join(args.out_dir, "log.csv")
    best_path = os.path.join(args.out_dir, "best.json")
    logf = open(log_path, "w", newline="")
    log = csv.writer(logf)
    log.writerow(["time", "generation", "candidate", "win_F", "win_road_army_f", "fitness", "mult_log10"])

    incumbent = {k: 0.0 for k in PARAMS}      # log10 of the factor on each weight; 0 = v01 itself
    incumbent["ROAD_REL"] = None              # None = off (v01); a number = log10 factor on ROAD_REL_BASE
    if args.start:
        incumbent.update(json.load(open(args.start))["log10_mult"])

    def mult_of(vec):
        out = {k: 10 ** v for k, v in vec.items() if k != "ROAD_REL"}
        if vec.get("ROAD_REL") is not None:
            out["ROAD_REL"] = ROAD_REL_BASE * 10 ** vec["ROAD_REL"]
        return out

    with cf.ProcessPoolExecutor(args.workers, mp_context=mp.get_context("spawn")) as pool:
        gen = 0
        while datetime.datetime.now() < until:
            seed0 = args.seed0 + gen * max(args.pairs_f, args.pairs_r)
            cands = [("incumbent", incumbent)]
            if gen == 0 and not args.no_probes:
                # First round: the directions the loss analysis points to (results/ANALYSIS.md 3.1, 3.2)
                for c, change in enumerate([{"ROAD": 1.0}, {"ROAD": 1.5}, {"enemy_production": 0.3},
                                            {"buildable_nodes": 1.0, "reachable_production_1": 0.5},
                                            {"production": 0.3, "hand_synergy": 1.0}]):
                    child = dict(incumbent)
                    child.update(change)
                    cands.append((f"g0c{c}", child))
            for c in range(args.children if (gen > 0 or args.no_probes) else 0):
                child = dict(incumbent)
                keys = rng.sample(PARAMS, 3)
                for j, k in enumerate(keys):
                    cur = 0.0 if child[k] is None else child[k]
                    step = rng.choice([-1.0, 1.0]) if (j == 0 and rng.random() < args.wide) \
                        else rng.gauss(0, args.sigma)
                    child[k] = max(-2.0, min(2.0, cur + step))
                cands.append((f"g{gen}c{c}", child))
            results = []
            for name, vec in cands:
                t0 = time.time()
                path = make_candidate(mult_of(vec), work, f"{name}")
                rates = evaluate(pool, path, plan, seed0)
                wf, wr = rates[0], (rates[1] if len(rates) > 1 else float("nan"))
                fit = sum(rates) / len(rates)
                results.append((fit, name, vec))
                log.writerow([datetime.datetime.now().strftime("%H:%M:%S"), gen, name, f"{wf:.3f}",
                              f"{wr:.3f}", f"{fit:.4f}", json.dumps({k: (None if v is None else round(v, 3)) for k, v in vec.items()})])
                logf.flush()
                print(f"gen {gen} {name:<10} F {wf:.3f}  road_army_f {wr:.3f}  fitness {fit:.4f}  "
                      f"({time.time() - t0:.0f}s)", flush=True)
            fit_inc = results[0][0]
            best = max(results, key=lambda r: r[0])
            if best[1] != "incumbent":
                incumbent = best[2]
                print(f"  -> new incumbent {best[1]}: {best[0]:.4f} vs {fit_inc:.4f} on the same boards",
                      flush=True)
            with open(best_path, "w") as fh:
                json.dump({"generation": gen, "log10_mult": incumbent, "mult": mult_of(incumbent)}, fh, indent=1)
            gen += 1
    print("done", flush=True)


if __name__ == "__main__":
    main()
