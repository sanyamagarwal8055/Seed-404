# Seed 404: evaluation results

Runner's summary of every evaluation so far. The raw numbers, one row per run, are in
[`results.csv`](results.csv); this file explains them. Last updated 17 Oct 2026, 13:35 IST, after
`v02_openings`.

**Bottom line:** `v01_catan_fixes` beats F by a measurable margin (55.3% against the baseline's 48.9%
on the 1,000-game judge). `v02_openings` adds better opening placement but plays the same as `v01`
within the margin, on every test. Current best: `v01` (simpler, same strength).

**Official score (portal, submission #1, v01):** 0.541 ± 0.031 against F and **0.393 ± 0.030 against
O**, strength 0.467. Our local numbers against F are confirmed; O is much stronger than F and is now
the bottleneck (section 0).

---

## 0. Official scores from the portal

| # | Uploaded (IST) | Version | vs F | vs O | Strength (0.5 F + 0.5 O) | Mean / worst CPU | Over clock | Faults |
|---|---|---|---|---|---|---|---|---|
| 1 | 13:47 | v01_catan_fixes | 0.541 ± 0.031 | 0.393 ± 0.030 | 0.467 | 189 / 685 ms | 0 | 0 |

1,000 games against each anchor on the organisers' public board set, on their machine.

- **Local testing matches the official score.** Our judge said 0.553 ± 0.031 against F; the portal
  says 0.541 ± 0.031. The intervals overlap almost completely, so the local judge can be trusted to
  rank versions against F. CPU also matches (182 ms locally, 189 ms on their machine).
- **O is the weak spot.** We win 39% against O, against 54% against F. Since strength is the average
  of the two, every point gained against O counts as much as a point against F, and there is far more
  room to gain there.
- **We cannot test against O locally.** Each upload is our only reading of O, so uploads should go to
  versions that have already beaten the current best on the local judge. 6 scored submissions and 9
  uploads are left.
- The leaderboard uses the public set; the top-30 cut uses a private set. Expect the private numbers
  to differ a little.

---

## 1. How we measure

- **Harness:** the organisers' `catan_kit.evaluate` (the script they score with), on the team machine
  (8 cores, Python 3.11). Opponent pool runs use Vivaan's `opponents/run_pool.py`, which calls the
  same harness.
- **Seeds:** quick checks and opponent runs use `seed0 100000`, 400 games. The judge uses
  `seed0 990000`, 1,000 games, split over 3 cores (334 + 334 + 332 games on seed0 990000 / 990167 /
  990334, so no board repeats). Every board is played twice, once from each seat, with the same dice.
  Every version faces the same boards, so the comparisons are paired.
- **Significance rule:** a difference smaller than the ci95 (about ±3 points at 1,000 games, ±5 at
  400) is reported as "no measurable difference", not as a win or a loss.
- **CPU:** the team machine matches the scoring machine (F: 157 ms here against the organisers' 158 ms
  reference), so CPU numbers are read as-is. Runs with several games in parallel read 10 to 20 ms
  higher than runs on an idle machine.

## 2. Versions

| Version | Parent | What changed |
|---|---|---|
| `v00_f_copy` | none | Exact copy of F (`examples/f_agent.py`). Baseline. |
| `v01_catan_fixes` | v00 | F plus four value-function fixes: 2:1 and 3:1 port bonus, always-on Longest Road progress, Largest Army progress (knights played), and weight 1e4 on `reachable_production_0`. |
| `v02_openings` | v01 | v01 plus a hand-made opening: picks settlement pairs under the 2-player snake order, adds a complement bonus for the second settlement, and points the first roads at the best free spot. The rest of the game is unchanged. |

## 3. Against F (the anchor that counts for strength)

| Version | Judge, 1,000 games (seed 990000) | Quick, 400 games (seed 100000) | Mean CPU / worst (judge) |
|---|---|---|---|
| v00_f_copy | 0.489 ± 0.031 | 0.518 ± 0.049 | 182 / 480 ms |
| **v01_catan_fixes** | **0.553 ± 0.031** | 0.560 ± 0.049 | 183 / 470 ms |
| v02_openings | 0.554 ± 0.031 | 0.558 ± 0.049 | 175 / 470 ms |

- **v01 vs v00: +6.4 points on the judge, larger than the ci95. A real improvement.** The baseline
  sits at about 50%, as an exact copy of F should.
- **v02 vs v01: +0.1 points. No measurable difference.**

## 4. Against the opponent pool (robustness)

400 games each, seed0 100000. Robustness is scored on the opponents we do worst against, so the lowest
number in each row matters most.

| Version | road_army_f | card_hoarder | greedy_builder (new) | greedy_builder_old | random |
|---|---|---|---|---|---|
| v00_f_copy | 0.440 | 0.650 | 0.760 | 0.583 | — |
| v01_catan_fixes | 0.488 | 0.713 | 0.795 | 0.638 | 1.000 |
| v02_openings | 0.508 | 0.685 | 0.808 | 0.610 | 1.000 |

ci95 is about ±0.04 to ±0.05 for every cell.

- **v01 is ahead of v00 against every opponent** (+4.8 to +6.3 points). Each single gap is inside its
  margin, but the direction is the same five times out of five, together with the measurable gain
  against F. The fixes look like a general improvement, not something tuned to F.
- **v02 against v01 is mixed:** +2.0 against road_army_f and +1.3 against the new greedy builder, −2.8
  against card_hoarder and the old greedy builder. All inside the margin.
- **road_army_f is our weakest matchup** for every version (44% to 51%). Vivaan's style check shows it
  plays as a road racer (longest road 8.4 against F's 5.3). An opponent that races for Longest Road
  is the clearest threat found so far.
- **greedy_builder was changed by Vivaan at 13:24 IST** (commit `7117fc4`): it no longer buys
  development cards. Rows for the earlier version are kept as `greedy_builder_old`. The new one is the
  version we use from now on; it is easier for us to beat (76% to 81% against 58% to 64%).

## 5. Head to head

| Match | Win rate (400 games, seed 100000) | Verdict |
|---|---|---|
| v02_openings vs v01_catan_fixes | 0.475 ± 0.049 | no measurable difference |

A head-to-head of v01 against v00 was not run: v00 is byte-identical to F, so it would replay the F
judge exactly.

## 6. Clock and faults

Every run so far: **0 errors, 0 timeouts, 0 crashes, 0 games over budget.** Mean CPU is 163 to 214 ms
per game against an allowance of about 1,000 ms (at most 1,500 ms). Worst single game: 680 ms
(v01 against the new greedy builder, 3 runs in parallel). There is room for about 5 times more search
per decision than F uses.

## 7. What this means

1. **The value-function fixes in v01 work.** Ports, road and army progress and immediate reachable
   production are worth about 6 points against F, and the gain carries over to every opponent.
2. **The v02 opening, as built, adds nothing measurable.** Either F's own one-move opening is already
   about as good as this hand-made score, or the opening gain is smaller than ±3 points. A 1,000-game
   head-to-head against v01 on fresh seeds would tell which, if the team wants to keep it.
3. **CPU is not a constraint yet.** Every version uses under 20% of the allowance, so the next gains
   can come from spending more compute: several sampled worlds per decision, or a short lookahead.
4. **For robustness, the weak spot is a Longest Road racer.** A version that contests the road (or
   blocks it) should be tested against road_army_f first.

## 8. Suggested next steps

- **Sanyam:** keep v01 as the candidate for upload; treat the v02 opening as optional. Next ideas
  with room in the budget: average over 3 to 5 sampled worlds; respond to an opponent's road race.
- **Vivaan:** loss analysis on v01 against road_army_f (seed0 100000) to see where the road race wins
  games; the tables above can go straight into the report.
- **Jainam:** run every new version through the same set (quick, judge, pool, head-to-head against
  the current best) and update this file.
