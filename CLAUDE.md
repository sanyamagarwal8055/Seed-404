# CLAUDE.md: Sanyam's agent-building sessions (team Seed 404)

> **Check first:** this file is for sessions with **Sanyam (the brain)**. If you are working with
> Jainam or Vivaan, ignore this file and follow their section of README.md (8 or 9).

You are Sanyam's coding partner in the Hyde x WnCC Catan AI hackathon, 17 Oct 2026, IIT Bombay.
**Last upload 17:00 IST. Report due 17:30 IST.** Time is the scarcest resource: be fast, be correct,
don't over-explain. Sanyam prefers short, to-the-point answers unless he asks for detail.

Read `README.md` in this repo (team plan) once. The organisers' problem statement is at
https://github.com/lyric-hyde/catan-hackathon-agent/blob/main/PROBLEM_STATEMENT.md.

---

## 1. Your job (and only your job)

Sanyam owns `agents/` and `tools/`. For every new idea you:
1. Create a **new** folder `agents/vNN_<short_name>/agent.py` (next free number).
2. Write the agent (rules in section 4), self-contained.
3. Check it (section 6).
4. Commit and push (section 7).
5. Print a copy-paste message for Jainam (section 8).

**Never** edit: `results/` (Jainam), `opponents/` and `report/` (Vivaan), any already-pushed
`agents/vNN_*` folder (frozen), or anything from the organisers' kit (`catan_kit/`).
**Never upload** to the organisers. Sanyam uploads himself from the team machine.
**Never** write tokens, passwords or API keys into any file.

---

## 2. The problem in brief

- 2-player Catan on the **catanatron** engine (pinned, patched build), 10 VP to win, **no trading
  between players**, bank and port trades allowed. Official spiral board, random board per seed.
- We submit a folder with `agent.py` containing:
  ```python
  class Agent:
      def __init__(self): ...                          # free: not charged to the clock (60 s max)
      def decide(self, obs, playable_actions) -> int:  # return an INDEX into playable_actions
  ```
- Opponents: **F** = catanatron's `ValueFunctionPlayer` (1-move lookahead, 13-feature weighted sum;
  its code is `examples/f_agent.py` in the kit), **O** = Hyde's trained bot (beats F), and other teams.
- Scoring: strength = 0.5·winrate(F) + 0.5·winrate(O) on private boards; robustness = mean win rate
  vs the worse half of our group (top 30 only); plus report and presentation (about half the marks).

### CPU limit (the hard constraint)
- Per game: **300 ms + 12.5 ms per decision, at most 1.5 s** (about 1 s per average game), ONE core.
- Over the limit → the rest of that game is **random moves**. One decision > 3 s → killed.
- `obs.cpu_left` = seconds of allowance left (includes this decision's 12.5 ms). May be `None`
  in local tests → treat as plenty.
- F uses about 158 ms per game (2.9 ms per decision). We have about 6× that.
- No threads/multiprocessing benefit (one core); `multiprocessing` is refused inside the harness.
- Forced moves (one legal action) never reach the agent.

### What the agent sees (`obs`)
`obs.board`, `obs.my_resources`, `obs.my_devs`, `obs.my_public_vps`, `obs.my_actual_vps`,
`obs.bank`, `obs.opp_resources` (exact), `obs.opp_dev_count` (count only), `obs.opp_public_vps`,
`obs.played_devs`, `obs.turn`, `obs.me` (our Color), `obs.cpu_left`.
Hidden: which dev cards the opponent holds. `obs.sample_world(rng)` returns a full catanatron
`Game` consistent with what we see (opponent dev cards redrawn at random). Search on that.

### Submission constraints
Python only (no compiled files, no starting other programs). Imports allowed: standard library,
numpy, scipy, scikit-learn, torch (CPU; call `torch.set_num_threads(1)`), catanatron.
Load data files with `os.path.join(os.path.dirname(__file__), "file")`. The folder is read-only on
their machine; temp files go to `tempfile.gettempdir()`. Max 100 MB.
**>2% of decisions raising or returning an illegal index = disqualified.**

---

## 3. Engine cheat sheet (pinned catanatron 3.3.0)

```python
from catanatron.players.value import DEFAULT_WEIGHTS, CONTENDER_WEIGHTS, base_fn, get_value_fn
from catanatron.features import build_production_features, reachability_features, resource_hand_features
from catanatron.models.enums import ActionType, ActionPrompt, RESOURCES, SETTLEMENT, CITY
from catanatron.state_functions import (get_longest_road_length, get_played_dev_cards,
    player_key, player_num_dev_cards, player_num_resource_cards)

world = obs.sample_world(rng)          # full Game
s = world.copy(); s.execute(action)    # simulate (wrap in try/except)
s.playable_actions                     # legal actions in s
s.state.current_color()                # whose decision it is
s.winning_color()                      # None if no winner yet
s.state.is_initial_build_phase         # setup phase flag
s.state.board.get_player_port_resources(color)   # set of port resources (None = 3:1)
s.state.board.buildable_node_ids(color)
s.state.board.map.adjacent_tiles[node]           # tiles around a node
s.state.player_state[f"{player_key(s.state, color)}_VICTORY_POINTS"]
```
Action types: ROLL, MOVE_ROBBER, DISCARD_RESOURCE, BUILD_ROAD, BUILD_SETTLEMENT, BUILD_CITY,
BUY_DEVELOPMENT_CARD, PLAY_KNIGHT_CARD, PLAY_YEAR_OF_PLENTY, PLAY_MONOPOLY, PLAY_ROAD_BUILDING,
MARITIME_TRADE, END_TURN. `action.action_type`, `action.value`.

**F's value function** (`base_fn(DEFAULT_WEIGHTS)`), weights: public_vps 3e14, production 1e8,
enemy_production −1e8, num_tiles 1, reachable_production_0 **0**, reachable_production_1 1e4,
buildable_nodes 1e3, longest_road 10 (only when no buildable nodes, else 0.1), hand_synergy 1e2,
hand_resources 1, discard_penalty −5, hand_devs 10, army_size 10.1. Production values are
probabilities (a 6 tile ≈ 0.139 per roll), so production terms are about 1e7 to 1e8.

**Measured costs** (2-core cloud box, slower than the scoring machine): value function ≈ 0.07 ms,
`copy()` ≈ 0.04 ms, `copy()+execute()` ≈ 0.06 ms. So about 0.13 ms per evaluated move: roughly
80 to 100 evaluations per decision fit the average 12.5 ms budget. Budget with `time.process_time()`.

---

## 4. Rules for every agent version

- Folder `agents/vNN_<name>/` with `agent.py` at its top; everything it loads sits beside it.
  No imports from other version folders.
- Docstring on line 1: `"""vNN_name (parent: vMM_name). <2-3 lines: what changed and why>"""`.
- `decide` must **never raise**: wrap the whole body in `try/except` and fall back to a safe index
  (best found so far, else 0). Wrap every `execute` in `try/except: continue`.
- Respect the clock: read `obs.cpu_left`, set a per-decision deadline with `time.process_time()`,
  stop searching at the deadline and return the best move so far. Spend extra only in the opening
  (`obs.turn` small) and on decisions with many options. Keep a safety reserve (e.g. never use
  more than ~30% of `cpu_left` in one decision).
- Heavy setup (tables, weights) goes in `__init__` or module level, not in the first `decide`.
- **One idea per version**, so each result shows what that change did. Build on the best measured
  version so far (ask Sanyam which one if unsure).

---

## 5. Strategy knowledge and roadmap

### Versions so far
| Version | What | Status |
|---|---|---|
| v00_f_copy | exact copy of F | baseline |
| v01_catan_fixes | F + port bonus (2:1 → 3e7×prod_r, 3:1 → 1e7×total prod), road progress 3e6×min(len,8), army progress 3e6×min(knights,4), reachable_production_0 = 1e4 | **current best**; uploaded |
| v02_openings | v01 + pair-aware snake-order setup settlements and roads | neutral: no measurable gain over v01 |
| v03_search | v01 + exact expectation for random moves + greedy same-turn follow-ups (top-4) | neutral: judge 55.6%, h2h vs v01 49.5%; 0 over budget, ~280 ms/game |
| v04_tuned | v01 with all weights tuned against the pool (tools/tune.py) + road_race and opp_vps features | **best so far locally**: h2h vs v01 61.0% ± 5.5, better than v01 vs every pool opponent; waiting for Jainam's kit runs |
| v05_expect_relative | (other session) v01 + exact chance expectation via execute_spectrum + pruning + relative road/army races | pushed (faaf711), untested |

v04_tuned local validation (Sanyam's laptop, catanatron 3.3.0 from GitHub, `sample_world` = exact
copy, 300 games per opponent, seeds 400000+, never used in tuning; ci95 ≈ ±5.5):
F 60.3% (v01 58.0%), road_army_f 53.0% (49.0%), card_hoarder 73.0% (68.3%), greedy_builder 86.3%
(83.0%), v01 61.0%. Local reads about 3 points above the kit for v01 vs F (58.0% vs judge 55.3%).
Biggest tuned change: enemy_production −1e8 → −2.6e9 (deny the opponent's income).

Measured results (from `results/results.csv`; judge = 1000 games seed0 990000, ci95 ≈ ±3.1;
pool and head-to-head = 400 games seed0 100000, ci95 ≈ ±4 to 5):

| Version | F judge | F quick | road_army_f | card_hoarder | greedy_builder (new) | vs previous best | mean / worst CPU (judge) |
|---|---|---|---|---|---|---|---|
| v00_f_copy | 48.9% | 51.8% | 44.0% | 65.0% | 76.0% | n/a | 182 / 480 ms |
| v01_catan_fixes | **55.3%** | 56.0% | 48.8% | 71.3% | 79.5% | n/a (= F judge) | 183 / 470 ms |
| v02_openings | 55.4% | 55.8% | 50.8% | 68.5% | 80.8% | 47.5% vs v01 | 175 / 470 ms |

- v01 beats v00 by +6.4 points on the judge (> ci95): measurably better. **Build on v01.**
- v02 is neutral: build on v01, keep v02's opening code only if a later test shows it helps.
- Weakest matchup for every version: **road_army_f** (a road racer, longest road avg 8.4 vs F's 5.3).
- CPU: about 175 to 200 ms per game of a ~1000 ms allowance. We use under 20% of our compute.

Prototype numbers (Claude's own workspace, 200 games vs F, seed0 100000, NOT in results.csv,
do not quote in the report): ports 52.5%, road 55.0%, army 53.5%, r0 54.5% (all ±6.9%);
same-turn lookahead on F's score 52% ± 7% (seed0 990000).

### Goal from now on: robustness, not just beating F
Robustness is scored as our mean win rate vs the **worse half** of our group, so we optimise our
worst matchups. Generalisation rules for every version:
- Judge each version on the whole pool (F, road_army_f, card_hoarder, greedy_builder, previous best),
  not only F. A version is better only if it improves the pool's worst half without measurably
  losing to F.
- Prefer reasoning (search over the actual position) over hand-tuned special cases: search adapts to
  unseen opponents, special cases overfit.
- Any tuning uses a mixed-opponent fitness (mean win rate over the pool, or mean of the worst half),
  seeds 200000+ only, multiplicative (log-scale) small steps. Never tune on 100000 or 990000.
- Keep it simple and explainable: one idea per version, every result goes in the report.

### Roadmap (adjust to Jainam's results; ask Sanyam before changing order)
Changed 14:10 IST: weight tuning moved up into v04 (Sanyam: v04 must make a big jump possible);
the old v04_road_defense is folded into v04 as a tunable `road_race` feature.
1. **v03_search** (measured: neutral, no gain over v01): v01 + exact expected value of random moves
   (roll over 11 dice sums, robber steal over the victim's hand, dev card over the deck) + greedy
   same-turn follow-ups for the top-4 moves. Lesson: more search on the same value function does
   not help; the value function (weights) is the lever.
2. **v04_tuned** (this is the "big change"): v01's 1-move agent with EVERY weight tunable
   (F's 12 + v01's 4) plus two relative features, `road_race` (our longest road minus theirs once
   theirs >= 4) and `opp_vps` (penalty per opponent public VP). Weights live in
   `agents/v04_tuned/weights.json`, found by `tools/tune.py`: (1+λ) evolution strategy, 1 to 3
   weights multiplied by exp(N(0, 0.7)) per mutant, all candidates on the same fresh seeds, a winner
   must also win a second confirmation block, fitness = mean win rate over F + road_army_f +
   card_hoarder + v01, seeds 200000+. Tuned on Sanyam's laptop (catanatron 3.3.0 from GitHub).
   Write-up: `v04_tuned.pdf` at the repo root (source `v04_tuned.tex`).
3. **Next (v06)**: keep tuning. Continue from `agents/v04_tuned/weights.json` on the team machine
   (`--start agents/v04_tuned/weights.json --seed0 300000`), and/or put v04's weights into
   v05_expect_relative if v05 measures better than v01. Upload v04 if the kit confirms the local
   numbers (judge vs F >= v01's 55.3%, h2h vs v01 > 50% outside the ci).
4. **v06_adaptive**: the same Agent object plays many games in a row against one opponent (allowed
   by the rules). Detect the opponent's style (road length growth, dev cards bought, knights played)
   and shift weights (e.g. more `road_race` vs a road racer). Must stay safe if detection is wrong.
5. **v07_final**: combine only what measurably helped, plus endgame rules (win immediately if any
   action reaches 10 VP; treat the opponent's unplayed dev cards as possible hidden VP).

### Tuning (`tools/tune.py`, needs only catanatron, runs from the repo root)
```
python tools/tune.py --agent agents/v04_tuned/agent.py --minutes 40 --workers 7 \
    --start agents/v04_tuned/weights.json --seed0 300000
```
Logs every candidate to `tools/tune_log.csv`, writes the incumbent to `tools/tune_best.json`.
Use a seed0 not used before (the v04 run used 200000 to 200800; validation used 400000+). Never 100000 or 990000.
The agent must accept `Agent(weights=dict)`.

Catan facts to use: pips = ways to roll (6/8 = 5, 5/9 = 4, 4/10 = 3, 3/11 = 2, 2/12 = 1);
cities double production and cannot be blocked; Longest Road / Largest Army are 4-point swings in
1v1; with no player trading, resource diversity and ports matter more than in normal Catan;
keep hand ≤ 7 (discard on a 7, rolled 1/6 of the time); put the robber on the opponent's best hex
that we don't touch.

---

## 6. Checking a version before pushing

Always: syntax check.
```
python -c "import ast; ast.parse(open('agents/vNN_x/agent.py').read()); print('syntax ok')"
```
If the organisers' kit is installed locally (ask Sanyam for the path; Python 3.11+ venv with
`pip install -r requirements.txt`), run a **10-game smoke test** only to confirm 0 errors and
0 games over budget. Don't log it; real numbers come from Jainam:
```
python -m catan_kit.evaluate --a <full path>/agents/vNN_x/agent.py --b examples/f_agent.py --games 10
```
(run from the kit folder). If the kit isn't available, do the syntax check plus a careful read-through.

---

## 7. Commit and push (Windows, PowerShell, repo root)

```
git add agents/vNN_x
git commit -m "vNN_x: <one-line summary>"
git pull --rebase
git push
```
Teammates push often (results, opponents), so always `git pull --rebase` before `git push`.
Only stage our own folder; never `git add -A`.

---

## 8. Hand-off message for Jainam (print this at the end of every version)

```
vNN_x is pushed (<commit hash>). Parent: vMM_y. Change: <one line>.
Please git pull, then quick check:
python -m catan_kit.evaluate --a ~/Seed-404/agents/vNN_x/agent.py --b examples/f_agent.py --seed0 100000 --games 400
Compare with vMM_y on the same seeds. Send win rate ± ci95, mean/worst CPU, games over budget, errors.
```

---

## 9. Uploading (Sanyam does it himself, on the team machine; for reference only)

Only after a clean 1000-game judge (seed0 990000) with 0 errors and 0 games over budget:
```
cd ~/Seed-404/agents/vNN_x && python -m zipfile -c ~/vNN_x.zip . && cd -
~/upload.sh ~/vNN_x.zip
```
`agent.py` at the top level of the zip. 7 scored uploads (10 total including failures); keep at
least 2 for after 15:30. Log each one in `results/uploads.csv`.
