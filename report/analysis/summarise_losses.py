"""Compare the games an agent wins with the games it loses. Standard library only.

    python report/analysis/summarise_losses.py v02_vs_F.csv [more.csv ...]

Input: CSV files written by collect_games.py (several files are pooled). Prints the win rate, the win
rate by seat and by opening quality, how the agent's losses look (how close, how often the opponent
won with hidden victory points), and a ranking of which per-game facts differ most between wins and
losses.

Read the ranking with care. It shows what goes with winning, not what causes it: a player with more
cities wins more, but may have more cities because it was already winning. The opening columns are
the cleanest signal, because they are fixed before anything else happens.
"""
import csv
import math
import sys

#: facts that are mostly the game's outcome itself; shown for context, not as findings
OUTCOME_LIKE = {"turns", "a_vps", "b_vps", "a_has_army", "a_has_road", "b_has_army", "b_has_road"}
SKIP = {"game", "board_seed", "win"}


def load(paths):
    rows = []
    for path in paths:
        with open(path, newline="") as fh:
            for r in csv.DictReader(fh):
                rows.append({k: float(v) for k, v in r.items()})
    return rows


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rate(rows):
    return mean([r["win"] for r in rows])


def ci(rows):
    p, n = rate(rows), len(rows)
    return 1.96 * math.sqrt(p * (1 - p) / n) if n else float("nan")


def show_rate(label, rows):
    if rows:
        print(f"  {label:<34}{rate(rows):>7.3f} +-{ci(rows):.3f}   ({len(rows)} games)")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rows = load(sys.argv[1:])
    wins = [r for r in rows if r["win"] == 1]
    losses = [r for r in rows if r["win"] == 0]
    print(f"{len(rows)} games: {len(wins)} won, {len(losses)} lost\n")

    print("win rate")
    show_rate("overall", rows)
    show_rate("when the agent moves first", [r for r in rows if r["a_first"] == 1])
    show_rate("when the agent moves second", [r for r in rows if r["a_first"] == 0])
    over = [r for r in rows if r["a_over_budget"] == 1]
    print(f"  games the agent ran out of clock: {len(over)}")

    print("\nopening quality: our first two settlements against the opponent's (in 36ths of a roll)")
    diffs = sorted(r["a_open_pips"] - r["b_open_pips"] for r in rows)
    lo, hi = diffs[len(diffs) // 3], diffs[2 * len(diffs) // 3]
    show_rate(f"opening pips behind (diff <= {lo:.0f})", [r for r in rows if r["a_open_pips"] - r["b_open_pips"] <= lo])
    show_rate("opening pips about level",
              [r for r in rows if lo < r["a_open_pips"] - r["b_open_pips"] < hi])
    show_rate(f"opening pips ahead (diff >= {hi:.0f})", [r for r in rows if r["a_open_pips"] - r["b_open_pips"] >= hi])
    print(f"  mean opening pips: agent {mean([r['a_open_pips'] for r in rows]):.1f}, "
          f"opponent {mean([r['b_open_pips'] for r in rows]):.1f}")

    if losses:
        print("\nhow the losses look")
        close = [r for r in losses if r["a_vps"] >= 8]
        print(f"  lost with 8 or more points (close): {len(close)} of {len(losses)}")
        print(f"  lost with 5 or fewer points (blown out): {sum(r['a_vps'] <= 5 for r in losses)} of {len(losses)}")
        hid = [r for r in losses if r["b_hidden_vp"] >= 1]
        print(f"  opponent held hidden victory points when it won: {len(hid)} of {len(losses)}")
        print(f"  mean opponent hidden VP: in our losses {mean([r['b_hidden_vp'] for r in losses]):.2f}, "
              f"in our wins {mean([r['b_hidden_vp'] for r in wins]):.2f}")
        print(f"  mean game length (turns): wins {mean([r['turns'] for r in wins]):.0f}, "
              f"losses {mean([r['turns'] for r in losses]):.0f}")

    if wins and losses:
        print("\nwhat differs between wins and losses (t = difference / its standard error; |t| > 2 is "
              "unlikely to be chance)")
        print(f"  {'fact':<18}{'in wins':>9}{'in losses':>11}{'diff':>8}{'t':>7}")
        out = []
        for k in rows[0]:
            if k in SKIP:
                continue
            w, l = [r[k] for r in wins], [r[k] for r in losses]
            se = math.sqrt(sd(w) ** 2 / len(w) + sd(l) ** 2 / len(l))
            t = (mean(w) - mean(l)) / se if se and not math.isnan(se) else 0.0
            out.append((abs(t), k, mean(w), mean(l), t))
        for _, k, mw, ml, t in sorted(out, reverse=True):
            tag = "  (outcome-like)" if k in OUTCOME_LIKE else ""
            print(f"  {k:<18}{mw:>9.2f}{ml:>11.2f}{mw - ml:>8.2f}{t:>7.1f}{tag}")


if __name__ == "__main__":
    main()
