# Seed 404: evaluation results

Runner's summary of every evaluation so far. The raw numbers, one row per run, are in
[`results.csv`](results.csv); this file explains them. Last updated 17 Oct 2026, 16:20 IST, after
`vj07_ensemble`.

**Bottom line (16:20):** best on the portal is **upload #3, Vivaan's `v01_tuned_roadrace`**: 0.611
against F, 0.424 against O (strength 0.518). The best local judge is now the **`vj07_ensemble`**
(three tuned value functions voting on each move): **0.650 ± 0.030** against F, even with #3 head to
head. Everything that gained came from tuning weights on win rate or combining tuned weights; search,
hand-made features and a learned win predictor did not (section 8).

| Version | Judge vs F | Verdict |
|---|---|---|
| v00_f_copy | 0.489 | baseline |
| v01_catan_fixes | 0.553 | better than v00 (upload #1) |
| v02_openings | 0.554 | = v01 |
| v03_search | 0.556 | = v01, 55% more CPU |
| v04_tuned | 0.621 | better than v01 (upload #2) |
| v05_expect_relative | 0.439 | **worse than v01** |
| x1_v03_budget (vj) | 0.567 | = v01 |
| x2_v01_road (vj) | 0.562 | = v01 |
| v01_tuned_roadrace (Vivaan) | 0.623 | = v04 on F, better on the portal (upload #3) |
| vj06_vpcards (K = 0.5) | 0.623 | = #3 on F (0.500 head to head); aimed at O |
| x3_v04c | 0.636 | ≥ #3, inside the margin |
| **vj07_ensemble** | **0.650** | **highest judge; even with #3 head to head (0.508)** |

**Not yet uploaded (16:20):** vj07, x3_v04c and vj06 are tested and clean (0 errors, 0 games over the
clock). Only the best submission counts, so all three can go up as extra chances.

**Official score (portal, submission #1, v01):** 0.541 ± 0.031 against F and **0.393 ± 0.030 against
O**, strength 0.467. Our local numbers against F are confirmed; O is much stronger than F and is now
the bottleneck (section 0).

---

## 0. Official scores from the portal

| # | Uploaded (IST) | Version | vs F | vs O | Strength (0.5 F + 0.5 O) | Mean / worst CPU | Over clock | Faults |
|---|---|---|---|---|---|---|---|---|
| 1 | 13:47 | v01_catan_fixes | 0.541 ± 0.031 | 0.393 ± 0.030 | 0.467 | 189 / 685 ms | 0 | 0 |
| 2 | 15:25 | v04_tuned | 0.580 ± 0.031 | 0.400 ± 0.030 | 0.490 | 205 / 641 ms | 0 | 0 |
| 3 | 15:44 | v01_tuned_roadrace (Vivaan) | 0.611 ± 0.030 | 0.424 ± 0.031 | 0.518 | 213 / 679 ms | 0 | 0 |
| 4 | 16:29 | **vj07_ensemble** (Jainam) | **0.634 ± 0.030** | **0.449 ± 0.031** | **0.542** | 288 / 833 ms | 0 | 0 |

**v04 on the portal: +3.9 against F, but only +0.7 against O.** Tuning against F, road_army_f,
card_hoarder and v01 improved play against F-like opponents and barely touched O. (Our judge said
0.621 against F; the portal's 0.580 is on different boards, and the two intervals still overlap.)
Whatever O does well, our sparring pool does not contain it yet.

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
| `v03_search` | v01 | v01's value function plus search: random-outcome moves (roll, robber, buying a development card) scored as their exact expected value instead of one sample, and the top-k moves extended with our own same-turn follow-ups (trade then build, and so on). Budget 20 ms per decision (40 ms early), at most 30% of `cpu_left`, measured with `process_time`. |

## 3. Against F (the anchor that counts for strength)

| Version | Judge, 1,000 games (seed 990000) | Quick, 400 games (seed 100000) | Mean CPU / worst (judge) |
|---|---|---|---|
| v00_f_copy | 0.489 ± 0.031 | 0.518 ± 0.049 | 182 / 480 ms |
| **v01_catan_fixes** | **0.553 ± 0.031** | 0.560 ± 0.049 | 183 / 470 ms |
| v02_openings | 0.554 ± 0.031 | 0.558 ± 0.049 | 175 / 470 ms |
| v03_search | 0.556 ± 0.031 | 0.578 ± 0.048 | 282 / 570 ms |
| **v04_tuned** | **0.621 ± 0.030** | 0.598 ± 0.048 | 179 / 420 ms |
| v05_expect_relative | 0.439 ± 0.031 | 0.440 ± 0.049 | 184 / 540 ms |
| x1_v03_budget (vj) | 0.567 ± 0.031 | 0.570 ± 0.049 | 305 / 620 ms |
| x2_v01_road (vj) | 0.562 ± 0.031 | 0.573 ± 0.049 | 194 / 500 ms |

- **v01 vs v00: +6.4 points on the judge, larger than the ci95. A real improvement.** The baseline
  sits at about 50%, as an exact copy of F should.
- **v02 vs v01: +0.1 points. No measurable difference.**
- **v03 vs v01: +0.3 points. No measurable difference**, at about 100 ms more CPU per game.
- **v04 vs v01: +6.8 points. Measurably better.** Same one-move lookahead and CPU as v01; only the
  weights differ (tuned by evolution strategy against F, road_army_f, card_hoarder and v01).
- **v05 vs v01: −11.4 points. Measurably worse.**
- **x1 vs v01: +1.4, x2 vs v01: +0.9. No measurable difference.**

## 4. Against the opponent pool (robustness)

400 games each, seed0 100000. Robustness is scored on the opponents we do worst against, so the lowest
number in each row matters most.

| Version | road_army_f | card_hoarder | greedy_builder (new) | greedy_builder_old | random |
|---|---|---|---|---|---|
| v00_f_copy | 0.440 | 0.650 | 0.760 | 0.583 | — |
| v01_catan_fixes | 0.488 | 0.713 | 0.795 | 0.638 | 1.000 |
| v02_openings | 0.508 | 0.685 | 0.808 | 0.610 | 1.000 |
| v03_search | 0.480 | 0.693 | 0.793 | — | 1.000 |
| **v04_tuned** | **0.533** | 0.713 | — | — | — |
| v05_expect_relative | 0.340 | 0.680 | — | — | — |

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
| v03_search vs v01_catan_fixes | 0.495 ± 0.049 | no measurable difference |
| **v04_tuned vs v01_catan_fixes** | **0.560 ± 0.049** | **better** (lower bound 0.511) |
| v05_expect_relative vs v01_catan_fixes | 0.380 ± 0.048 | worse |

**Opponent strength against F** (each opponent as the measured agent, 400 games, seed0 100000):
road_army_f 0.560 ± 0.049 (just above F), card_hoarder 0.348 ± 0.047, greedy_builder 0.230 ± 0.041.

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
3. **Tuning the weights on win rate is what works (v04, +6.8).** It is the only change since v01
   that moved the judge outside the margin, at no CPU cost. Search (v03, x1), hand-made features
   (v02, v05, x2) and a learned predictor (vj01, vj02) did not.
4. **More search at this budget did not help (v03).** Exact expectations over dice, robber and
   development cards plus a greedy same-turn lookahead changed nothing measurable, against F, against
   the pool or head to head. Since v03 still uses under 30% of the allowance (about 280 ms of about
   1,000 ms), the open question is whether more budget would help, or whether the one-move value
   function is the limit. A run of v03 with a larger per-decision budget would separate the two.
5. **For robustness, the weak spot was a Longest Road racer** (v04 is the first version above 50%
   against it, 0.533). A version that contests the road (or
   blocks it) should be tested against road_army_f first.

## 8. Side experiments in `vj/` (Jainam)

None of these is a team version. Laptop runs give valid win rates (identical games on both machines)
but not valid CPU numbers.

**x1_v03_budget: is search budget the limit?** v03 with 3× the budget (60 ms per decision, 50% of
`cpu_left`): 0.567 on the judge, +1.4 over v01, inside the margin, at 305 ms per game. **No: more
search on the same scoring barely helps.**

**x2_v01_road: is road_army_f's road weight the secret?** v01 with road_army_f's road bonus (3e7 per
segment, uncapped, 10× v01's): 0.562, +0.9, inside the margin. **No.**

**Teacher check: is a slow catanatron searcher worth imitating?** AlphaBeta depth 2 against F with
**no clock**, perfect information: 21/42 = 0.50 ± 0.15. SameTurnAlphaBeta depth 2: 0.31 ± 0.14. **No:
deeper search on F's value function is not stronger than F,** so distilling it would not help.

**vj01 / vj02: a learned value function.** Logistic regression on 1.16 million positions from 10,000
self-play games (v01 vs F, v01 vs v01, F vs F, 10% random moves, seeds 200000+), about 108
board-independent features (production, reachability, VPs, road/army, hands, ports). catanatron's
614-number `create_sample_vector` was rejected: most of it is per-node and per-edge ownership tied to
one board, and it contains no production feature.

| Variant (vs F, 400 games, seed0 300000, laptop) | vj01 | vj02 |
|---|---|---|
| BLEND 0 (= v01's choices) | 0.530 | 0.530 |
| small blend (1e-6 to 0.25) | 0.060 | 0.488 to 0.510 |
| learned value only | 0.065 | 0.223 |
| validation: predicts the winner | 77.3% | 76.4% |

**It predicts well and plays badly, and the reason is clear.** The fit spreads credit across features
that move together. vj01 weighted `SETTLEMENTS_LEFT` +0.27 (its largest weight) and resources in hand
+0.15: building lowers both, so the agent stopped building. vj02 removed those bookkeeping features
and recovered to about v01's level when blended, but then weighted public VPs −1.45 and actual VPs
+1.24, so a normal victory point still scores −0.21. **A model fitted to predict outcomes is not a
model of which move is better.** Fixing it needs a decision-level target (imitation, or tuning on
win rate), which is what v04 does.

**vj04: evolution strategy over v01's weights against F (laptop, stopped at 15:25).** Same idea as
v04 but fitness against F only. Estimate after 4 generations: 0.603 ± 0.055 (perfect-information
games). It moved weights the same way v04's tuner did (production up about 10×, opponent production
down about 10×). Stopped in favour of continuing v04's own tuner.

**Teacher check 2: is search on v04's tuned value a teacher?** AlphaBeta depth 2 on v04's value,
perfect information, no clock: 0.429 ± 0.106 against v04 itself. No: distillation is not viable.

**vj06_vpcards: F's value is blind to Victory Point cards.** F scores points with the public count
(`P0_VICTORY_POINTS`); a VP development card only raises `ACTUAL_VICTORY_POINTS`, so to F (and every
version built on it) a VP card is worth nothing, and buying a development card (about 0.2 points on
average) is valued at `hand_devs` = 10 instead of about 6e13. vj06 = #3 plus (1) our hidden VP cards
counted at K × one public point and (2) buying a development card scored as its exact expectation over
the unseen cards (`execute_spectrum`). Against F: judge 0.623 (= #3), head to head 0.500. F hardly
buys development cards, so this cannot show against F; it is aimed at O, and only the portal can tell.

**x3_v04c: v04 tuned further against stronger opponents.** Sanyam's tuner, 34 more generations from
v04's weights, opponents F, road_army_f and v04 itself: judge 0.636 ± 0.030 (v04 0.621).

**vj07_ensemble: three tuned value functions vote.** #3 (Vivaan), v04 (Sanyam) and x3's weights, each
with vj06's VP-card fix; every move is played once, each member votes for its best move, a majority
wins, otherwise #3's choice. Judge **0.650 ± 0.030**, the highest so far; head to head with #3 0.508;
273 ms per game. Each tuning run is partly luck fitted to its own boards and opponents; the vote keeps
the choices that independent runs agree on.

## 9. Suggested next steps

*Update 15:20:* upload v04_tuned (zip `agent.py` **and** `weights.json`: without the json it falls
back to v01's weights silently). The most promising next step is more tuning from v04's weights.
The older suggestions below date from 13:35.

- **Sanyam:** keep v01 as the candidate for upload; treat the v02 opening as optional. Next ideas
  with room in the budget: average over 3 to 5 sampled worlds; respond to an opponent's road race.
- **Vivaan:** loss analysis on v01 against road_army_f (seed0 100000) to see where the road race wins
  games; the tables above can go straight into the report.
- **Jainam:** run every new version through the same set (quick, judge, pool, head-to-head against
  the current best) and update this file.
