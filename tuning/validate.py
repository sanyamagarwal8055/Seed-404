"""Check the tuned weights (best.json) against v01 on fresh boards that the search never saw.

    cd ~/seed404/catan-hackathon-agent && .venv/bin/python ../Seed-404/tuning/validate.py --pairs 200

Plays v01 (all factors 1) and the tuned weights on the same boards (700000 and up) against F and
road_army_f, and prints both win rates with 95% intervals and the difference. The search picks the
best of many noisy results, so its own score is optimistic; this is the number to believe.
"""
import os
import sys

sys.path.insert(0, os.getcwd())          # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402


def main():
    ensure_hash_seed()
    import argparse
    import concurrent.futures as cf
    import json
    import math
    import multiprocessing as mp
    import tempfile

    import catan_kit
    from tune import HERE, evaluate, make_candidate

    kit = os.path.dirname(os.path.dirname(os.path.abspath(catan_kit.__file__)))
    p = argparse.ArgumentParser()
    p.add_argument("--pairs-f", type=int, default=150, help="boards against F (2 games each)")
    p.add_argument("--pairs-r", type=int, default=90, help="boards against road_army_f (2 games each)")
    p.add_argument("--seed0", type=int, default=700000)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--best", default=os.path.join(HERE, "best.json"))
    p.add_argument("--road-rel", type=float, default=0.0,
                   help="also test the tuned weights plus this road-race weight (our length - theirs)")
    args = p.parse_args()

    plan = [(os.path.join(kit, "examples", "f_agent.py"), args.pairs_f, 5),
            (os.path.abspath(os.path.join(HERE, "..", "opponents", "road_army_f.py")), args.pairs_r, 3)]
    names = ["F", "road_army_f"]
    best = json.load(open(args.best))["mult"]
    work = tempfile.mkdtemp(prefix="validate-")
    paths = {"v01 (baseline)": make_candidate({}, work, "base"), "tuned": make_candidate(best, work, "tuned")}
    if args.road_rel:
        paths["tuned+road_rel"] = make_candidate(dict(best, ROAD_REL=args.road_rel), work, "tuned_rr")
    ns = [args.pairs_f * 2, args.pairs_r * 2]
    res = {}
    with cf.ProcessPoolExecutor(args.workers, mp_context=mp.get_context("spawn")) as pool:
        for label, path in paths.items():
            res[label] = evaluate(pool, path, plan, args.seed0)
    ci = lambda r, n: 1.96 * math.sqrt(max(r * (1 - r), 1e-9) / n)
    print(f"{ns[0]} games vs F, {ns[1]} vs road_army_f, boards {args.seed0}+, same boards for both\n")
    print(f"{'':<16}" + "".join(f"{nm:>22}" for nm in names) + f"{'mean':>10}")
    for label, r in res.items():
        print(f"{label:<16}" + "".join(f"{x:>14.3f} +-{ci(x, n):.3f}" for x, n in zip(r, ns)) + f"{sum(r) / 2:>10.3f}")
    se = [math.sqrt(2) * ci(b, n) / 1.96 for b, n in zip(res["v01 (baseline)"], ns)]
    for label in [k for k in res if k != "v01 (baseline)"]:
        d = [t - b for t, b in zip(res[label], res["v01 (baseline)"])]
        print(f"{label + ' - v01':<16}" + "".join(f"{x:>+14.3f} +-{1.96 * s:.3f}" for x, s in zip(d, se))
              + f"{sum(d) / 2:>+10.3f}")
    print("\ntuned factors (log10):", json.dumps({k: round(v, 2) for k, v in json.load(open(args.best))["log10_mult"].items() if abs(v) > 0.001}))


if __name__ == "__main__":
    main()
