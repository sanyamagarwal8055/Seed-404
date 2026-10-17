"""Pick vj01's BLEND: play each variant against F with the organisers' harness, in parallel.

Variants: BLEND 0 (exactly v01's choices, the control), 0.25, 0.5, 1, 2, and "learned only".
Each variant is a copy of agent.py with MODE/BLEND set, next to a copy of weights.npz, under --work.
Uses seed0 300000 by default: tuning range, and away from the training boards (200000-209999).
Win rates only: run it on any machine (no CPU deadline in vj01), but trust CPU numbers only from the
team machine.

    cd catan-agent-hackathon
    .venv\\Scripts\\python ..\\Seed-404\\vj\\vj01_learned_value\\sweep_blend.py --work ..\\vj_data\\sweep1 --games 400
"""
import os
import re
import shutil
import sys

sys.path.insert(0, os.getcwd())

from catan_kit._patch import ensure_hash_seed  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = [("blend_0", "blend", 0.0), ("blend_0.25", "blend", 0.25), ("blend_0.5", "blend", 0.5),
            ("blend_1", "blend", 1.0), ("blend_2", "blend", 2.0), ("learned", "learned", 1.0)]


def make_variant(work, name, mode, blend, weights):
    d = os.path.join(work, name)
    os.makedirs(d, exist_ok=True)
    src = open(os.path.join(HERE, "agent.py"), encoding="utf-8").read()
    src = re.sub(r'^MODE = .*$', f'MODE = "{mode}"', src, count=1, flags=re.M)
    src = re.sub(r'^BLEND = .*$', f'BLEND = {blend}', src, count=1, flags=re.M)
    open(os.path.join(d, "agent.py"), "w", encoding="utf-8").write(src)
    shutil.copy(weights, os.path.join(d, "weights.npz"))
    return os.path.join(d, "agent.py")


def main():
    ensure_hash_seed()
    import argparse
    import subprocess

    p = argparse.ArgumentParser()
    p.add_argument("--work", required=True)
    p.add_argument("--weights", default=os.path.join(HERE, "weights.npz"))
    p.add_argument("--games", type=int, default=400)
    p.add_argument("--seed0", type=int, default=300000)
    p.add_argument("--blends", type=float, nargs="*", default=None,
                   help="BLEND values to try instead of the default set (plus learned-only)")
    a = p.parse_args()
    assert not (990000 <= a.seed0 < 1000000), "never tune on the judge seeds"
    variants = VARIANTS if a.blends is None else (
        [(f"blend_{b:g}", "blend", b) for b in a.blends] + [("learned", "learned", 1.0)])

    # one organisers' evaluate process per variant, all at once (the harness starts its own
    # processes, which a multiprocessing.Pool worker may not do)
    procs = []
    for n, m, b in variants:
        path = make_variant(a.work, n, m, b, a.weights)
        log = open(os.path.join(a.work, n + ".txt"), "w")
        procs.append((n, log, subprocess.Popen(
            [sys.executable, "-m", "catan_kit.evaluate", "--a", path, "--b", os.path.join("examples", "f_agent.py"),
             "--games", str(a.games), "--seed0", str(a.seed0)], stdout=log, stderr=subprocess.STDOUT)))
    print(f"vs F, {a.games} games each, seed0 {a.seed0}")
    for n, log, proc in procs:
        proc.wait()
        log.close()
        out = open(os.path.join(a.work, n + ".txt")).read()
        rows = [ln for ln in out.splitlines() if re.search(r"win rate|CPU|over budget|errors|timeouts", ln)]
        print(f"== {n}\n" + "\n".join(rows))


if __name__ == "__main__":
    main()
