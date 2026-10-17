"""Play one agent against F, the random floor and every opponent in this folder, in one command.

Run it from the kit folder on the team machine (that is where catan_kit lives):

    cd ~/catan-agent-hackathon && source .venv/bin/activate
    python ~/Seed-404/opponents/run_pool.py --a ~/Seed-404/agents/v01_x/agent.py --games 200

It uses the organisers' scoring harness (catan_kit.evaluate.run), one opponent after the other on a
single core, and prints a table. At the end it prints one CSV line per opponent in the column order of
results/results.csv, ready to paste there. This script never writes results.csv itself: Jainam owns it.

Use --only NAME to run one opponent (for example to split the pool over several cores by hand).
The default seeds (100000 and up) are the quick-check range. Do not tune on 990000.
"""
import os
import sys

sys.path.insert(0, os.getcwd())          # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
NOT_OPPONENTS = {"run_pool.py"}


def opponents(kit_root):
    """The fixed anchors first, then every agent file in this folder."""
    found = [("F", os.path.join(kit_root, "examples", "f_agent.py")),
             ("random", os.path.join(kit_root, "examples", "random_agent.py"))]
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py") and not name.startswith("_") and name not in NOT_OPPONENTS:
            found.append((name[:-3], os.path.join(HERE, name)))
    return found


def main():
    ensure_hash_seed()          # may restart this process with PYTHONHASHSEED=0
    import argparse
    import datetime

    import catan_kit
    from catan_kit import evaluate

    kit_root = os.path.dirname(os.path.dirname(os.path.abspath(catan_kit.__file__)))

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--a", required=True, help="the agent being measured, path to its agent.py")
    p.add_argument("--games", type=int, default=200, help="games per opponent")
    p.add_argument("--seed0", type=int, default=100000)
    p.add_argument("--only", help="run just this opponent (F, random, or a file name without .py)")
    p.add_argument("--notes", default="")
    args = p.parse_args()

    path_a = os.path.abspath(os.path.expanduser(args.a))
    version = os.path.basename(os.path.dirname(path_a))
    pool = opponents(kit_root)
    if args.only:
        pool = [o for o in pool if o[0] == args.only]
        if not pool:
            sys.exit(f"no opponent called {args.only!r}")

    rows = []
    print(f"{version}: {args.games} games per opponent, seed0 {args.seed0}\n")
    print(f"{'opponent':<16}{'win rate':>10}{'+-95%':>8}{'CPU ms':>9}{'worst':>8}{'over':>6}{'faults':>8}")
    for name, path in pool:
        r = evaluate.run(path_a, path, args.games, seed0=args.seed0, quiet=True)
        faults = r["errors"] + r["timeouts"] + r["crashes"]
        print(f"{name:<16}{r['win_rate']:>10.3f}{r['ci95']:>8.3f}{r['mean_cpu_s'] * 1000:>9.0f}"
              f"{r['worst_cpu_s'] * 1000:>8.0f}{r['games_over_budget']:>6d}{faults:>8d}", flush=True)
        rows.append((name, r, faults))

    # time,version,opponent,seed0,games,win_rate,ci95,mean_cpu_ms,worst_cpu_ms,games_over_budget,errors,notes
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print("\nCSV lines for results/results.csv:")
    for name, r, faults in rows:
        print(f"{now},{version},{name},{args.seed0},{args.games},{r['win_rate']:.4f},{r['ci95']:.4f},"
              f"{r['mean_cpu_s'] * 1000:.1f},{r['worst_cpu_s'] * 1000:.1f},{r['games_over_budget']},"
              f"{faults},{args.notes}")


if __name__ == "__main__":
    main()
