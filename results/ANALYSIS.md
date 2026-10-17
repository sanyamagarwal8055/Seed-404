# Analysis for building the next version

Read this before starting a version. `RESULTS.md` has the numbers; this says what they mean and what to
try. Only Vivaan's sessions edit this file. Updated 17 Oct 2026, 14:30 IST.

Sources: `results/results.csv`, `results/uploads.csv`, per-game data in `report/analysis/data/`.
Findings are associations, not proven causes, unless marked tested.

## 1. Status
- v01 on the portal: 0.541 vs F, **0.393 vs O**, strength 0.467. O is the bottleneck: a point against
  O is worth as much as a point against F, and there is far more room there.
- The local judge predicts the portal for F (0.553 local, 0.541 portal), so rank versions locally.
- We use under 20% of our CPU (about 190 ms of about 1,000 ms per game).
- O cannot be tested locally. Upload only versions that already beat the current best on the judge.
- Default test pool: **F and road_army_f** (a road racer, our weakest matchup; v01 wins 49% of those).

## 2. What worked and what did not
- **v01 over v00: +6.4 points** on the judge. Which of its four changes matter is untested.
- **v02 (openings): no gain.** It gets more opening production than v01 (22.75 vs 21.61 pips) but less
  resource variety (4.43 vs 4.90), and opening production barely predicts winning (r = 0.05, 600 games).
  Do not spend more time on opening pips.
- **Searching the opponent's reply does not help with F's evaluation.** A budgeted depth-2 expectimax
  (our move, dice, their reply) scored with F's or the engine's tuned weights was no stronger than F
  (v01 beat it 66 to 70%, F 55%). O's edge over F probably comes from a better evaluation, not deeper
  search: tune or learn the evaluation (v05, v06) before any opponent-reply search. v03 only searches
  our own same-turn moves, so this does not affect it.

## 3. Where we lose (v01 and v02 against F, 300 games each, boards 300000+)
1. **Longest Road decides a large share of games.** We win 74.5% of games when we end holding it and
   7.2% when F does. F ends with it in 28% of all games and in 58% of our losses. Flipping a quarter of
   those games would be worth about 5 points (an upper bound, if the link is causal).
   **Try:** value the road race relative to F (our length minus theirs) and reward cutting their road.
2. **We lose by runaway, not near misses.** 41% of our losses end at 5 VP or fewer, 32% at 8 or more. In
   losses F builds 5.7 settlements to our 3.9. The games are lost in the middle, when our expansion
   stalls. **Try:** find what blocks our expansion in lost games (missing brick or wood, no free spot,
   robber on our best tile).
3. **Not worth effort:** F's hidden victory points (19% of our losses vs 16% of all games), which seat
   we play, and the clock (0 games over budget).

## 4. Queued
- **Which of v01's four changes matter:** four copies of v01, one change removed each, judged on F.
- **Where losses start:** record points turn by turn in lost games.
