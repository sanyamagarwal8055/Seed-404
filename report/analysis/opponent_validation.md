# Opponent pool validation, 2026-10-17

Checks that each opponent in `opponents/` plays a different style from F and stays inside the clock.
All runs on the team machine, one core, with the opponent files as committed alongside this note.

## Style: averages per game, each agent against F

`python report/analysis/style_check.py --games 60 --seed0 150000` (60 games per agent, seats alternated)

| agent (vs F) | win | turns | vps | cities | settlements | roads | dev_bought | knights | longest_road |
|---|---|---|---|---|---|---|---|---|---|
| F (control) | 0.53 | 64.80 | 7.83 | 2.03 | 4.55 | 8.85 | 1.13 | 0.68 | 5.32 |
| card_hoarder | 0.38 | 73.18 | 7.33 | 0.75 | 3.18 | 8.78 | 6.60 | 3.53 | 5.22 |
| greedy_builder | 0.28 | 68.98 | 6.57 | 2.02 | 3.98 | 7.55 | 0.00 | 0.00 | 4.53 |
| road_army_f | 0.57 | 67.03 | 8.10 | 1.93 | 4.53 | 9.30 | 0.97 | 0.55 | 8.42 |

An earlier run with 30 games on seed0 100000 gave the same pattern.

Reading: card_hoarder buys about 6 times F's development cards and plays 5 times its knights;
greedy_builder buys none; road_army_f builds a longest road of 8.4 against F's 5.3 but plays no more
knights than F, so in practice it is a road racer, not an army player.

## Clock and faults: each opponent as the measured agent against F

`python opponents/run_pool.py --a opponents/<name>.py --only F --games 40 --seed0 150000`

| opponent | win rate vs F | +-95% | mean CPU ms/game | worst ms | games over budget | faults |
|---|---|---|---|---|---|---|
| greedy_builder | 0.300 | 0.142 | 136 | 290 | 0 | 0 |
| card_hoarder | 0.425 | 0.153 | 139 | 250 | 0 | 0 |
| road_army_f | 0.550 | 0.154 | 180 | 430 | 0 | 0 |

The team machine was running other evaluations at the same time (load about 2 of 8 cores), so CPU
numbers may read slightly high. All three are far inside the allowance of about 1,000 ms per game.

## History

The first greedy_builder bought development cards whenever it could not build (5.1 per game over 30
games), which made it too close to card_hoarder. It was changed to never buy them; the tables above
are for the changed version.
