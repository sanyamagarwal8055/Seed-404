# Seed 404: analysis (why the numbers are what they are)

**Read this before starting a new version.** `RESULTS.md` (Jainam) lists the numbers; this file
explains them and says what to try next, so nobody has to re-derive it. Maintained by Vivaan's
sessions; only they edit this file. Last updated 17 Oct 2026, 14:15 IST.

Every number here comes from a run in `results/results.csv`, `results/uploads.csv` or the per-game
data in `report/analysis/data/`. Findings are associations, not proven causes, unless marked tested.

---

## 1. Where we stand (14:15)

| | vs F | vs O | Strength |
|---|---|---|---|
| v01_catan_fixes, upload #1 (portal) | 0.541 +-0.031 | **0.393 +-0.030** | 0.467 |

- **O is the bottleneck.** O beats v01 61-39; F is about even. A point against O is worth exactly as
  much as a point against F, and there is far more room there.
- **The local judge is trustworthy for F:** it said 0.553, the portal said 0.541 (intervals overlap).
- **We use under 20% of our CPU** (about 190 ms of a ~1,000 ms allowance per game). There is room for
  real search; that is what v03_search is for.
- We cannot test against O locally yet. Section 4 is building a stand-in.

## 2. What each version taught us

| Version | Result | Why (best explanation) |
|---|---|---|
| v01_catan_fixes | +6.4 pts over v00 on the judge (0.553 vs 0.489): **real gain** | four value-function fixes at once; which of the four matter is untested (section 5, idea B) |
| v02_openings | 0.554 vs v01's 0.553 on the judge, 47.5% head to head: **no gain** | its openings do produce more (22.75 vs 21.61 pips, t = 9.9) but have less resource variety (4.43 vs 4.90 kinds), and opening production barely predicts winning (r = 0.05 over 600 games). The opening is not where these games are decided. |
| v03_search | not tested yet | |

**Weakest matchup for every version: road_army_f** (v01 48.8%, v02 50.8%), the road racer. That
fits finding 3.1 below.

## 3. Loss analysis (v01 and v02 against F, 300 games each, boards 300000+)

### 3.1 Longest Road decides a large share of games
| Who ends the game holding Longest Road | Our win rate (600 games) | Share of games |
|---|---|---|
| we do | 0.745 +-0.041 | 72% |
| F does | 0.072 +-0.039 | 28% |

F ends with the card in 58% of our losses (155 of 267). If even a quarter of the games F ends with
it went our way instead, that is worth about 5 points (an upper-bound guess, assuming cause).
**Try:** value the road race relative to the opponent (our length minus theirs), and reward cutting
their road. (Sanyam's roadmap already has this as v04_road_defense.)

### 3.2 We lose by runaway, not by near misses
41% of our losses end with us at 5 VP or fewer; 32% end at 8 or more. In losses F builds 5.7
settlements to our 3.9; in wins we build 5.2 to F's 4.1. **The game is lost in the middle, when our
expansion stalls**, not in the endgame.

### 3.3 Not the problem
- F's hidden victory points: present in 19% of our losses and 16% of all games. Minor.
- Seat: first 0.577, second 0.533 (300 games each), inside the margin.
- The clock: 0 games over budget, 0 random moves.
- Ports in the opening: F never takes one (0 of 300), v02 never does, v01 in 12 of 300.

## 4. Opponent pool

| Opponent | Style | Status |
|---|---|---|
| greedy_builder | builds only, never buys cards | in the pool; weak (v01 wins 79.5%) |
| card_hoarder | buys and plays many development cards | in the pool (v01 wins 71.3%) |
| road_army_f | road racer (longest road 8.4 vs F's 5.3) | in the pool; **our weakest matchup** |
| alphabeta_f | expectimax search with a CPU budget, F's weights | **being calibrated as an O stand-in** |
| alphabeta_contender | same search, catanatron's CONTENDER_WEIGHTS | **being calibrated as an O stand-in** |
| contender_f | F's greedy play, CONTENDER_WEIGHTS | **being calibrated as an O stand-in** |

Validation of the first three: `report/analysis/opponent_validation.md`. A candidate becomes the O
stand-in if v01 scores near its real 0.393 against it; it is confirmed only if it also predicts the
next upload's O score.

## 5. Ideas queued, with the evidence for each

- **A. Road race (3.1):** see above; strongest signal we have.
- **B. Which parts of v01 matter:** four ablations of v01, one fix removed each, 1,000 games. Tells
  us what to keep and gives the report its "why each choice" evidence.
- **C. Where losses start (3.2):** record points turn by turn to find when lost games turn.
