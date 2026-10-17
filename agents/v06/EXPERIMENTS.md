# v06_hidden_vp: experiments behind it

All runs: organisers' harness (`catan_kit.match.play_chunk`, clocked, both seats, same dice per board),
300 games vs F, Claude's workspace (2 cores, Python 3.13, pinned catanatron d3f4ad0). Same seed0 = same
boards and dice, so rows with the same seed0 are paired comparisons. Margin at 300 games: about ±5.6 points.
Not yet in results/results.csv: Jainam should rerun the chosen version on the team machine.

## Calibration
| Agent | seed0 | Win vs F | Note |
|---|---|---|---|
| v04_tuned (baseline) | 100000 | 0.597 | team machine got 0.5975 on the same seeds: local runs reproduce |
| v04_tuned (baseline) | 101000 | 0.573 | fresh boards |

## Single changes on top of v04 (seed0 100000 unless noted)
| Change | Win vs F | vs baseline | Kept? |
|---|---|---|---|
| Hidden VP cards valued like public VP (3e14) + exact odds for dev card / robber / roll (catanatron execute_spectrum) | 0.617 | +2.0 | yes |
| same, fresh boards (seed0 101000) | 0.640 | +6.7 | yes (+4.4 over 600 paired games) |
| same + discard penalty −3e7 | 0.613 | +1.6 | no (discard adds nothing) |
| Discard penalty −3e7 alone | 0.603 | +0.6 | no |
| Robber pressure: enemy_production ×3 | 0.597 | 0.0 | no (already saturated by v04's tuning) |
| Same-turn lookahead (top-3 moves, 2 own follow-ups) | 0.533 | −6.4 | no (hurts) |
| Block opponent: their buildable spots −1e4, reach-1 −1e4 | 0.603 | +0.6 | no |
| Block opponent: −3e6 / −3e7 | 0.570 | −2.7 | no |
| Block opponent: reach-0/1 −1e8 | 0.500 | −9.7 | no (hurts badly) |
| Own expansion: reach-0/1 3e7, buildable 3e6 | 0.577 | −2.0 | no |

Reading: the value function was already near a local optimum on robber and expansion terms; the one
real gain came from information F throws away (our hidden victory-point cards, and averaging random
outcomes instead of sampling one). Search on top of this value function hurt, as v03 had suggested.

## On top of the hidden-VP version (seed0 101000; hidden-VP alone = 0.640 there)
| Change | Win vs F | Kept? |
|---|---|---|
| Army progress 3e7 | 0.637 | no (no gain) |
| Army progress 1e8 | 0.623 | no |
| Production 2e8 | 0.620 | no |
| Production 5e8 | 0.637 | no |
| Production 1e9 | 0.647 | no (inside noise, untested on a second board set) |

## Adaptive ensemble (rejected)
One Agent plays many games vs one opponent, so we tried Thompson sampling over two weight sets
(v04 + hidden VP, and Vivaan's v01_tuned_roadrace from tuning/), tracking our own wins exactly.
| Version | Opponent | seed0 | Win |
|---|---|---|---|
| ensemble, equal priors | F | 100000 | 0.630 |
| ensemble, equal priors | F | 101000 | 0.570 |
| ensemble, equal priors | road_army_f | 100000 | 0.597 (v04: 0.5325 on the team machine) |
| ensemble, strong prior on main arm | F | 101000 | 0.577 |
It helps against the road racer but costs about 6 points against F on the fresh boards (hidden-VP
alone: 0.640), so it was dropped. Insight for the report: exploration across arms is expensive when
one arm is clearly best against the anchor, and 1,000 games per opponent is too few to recover it.
