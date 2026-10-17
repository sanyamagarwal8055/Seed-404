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
| v01_catan_fixes | F + port bonus (2:1 → 3e7×prod_r, 3:1 → 1e7×total prod), road progress 3e6×min(len,8), army progress 3e6×min(knights,4), reachable_production_0 = 1e4 | pushed (8569d2b), waiting for Jainam's test |

Prototype numbers (Claude's own workspace, 200 games vs F, seed0 100000, NOT in results.csv,
do not quote in the report): ports 52.5%, road 55.0%, army 53.5%, r0 54.5% (all ±6.9%);
same-turn lookahead on F's score 52% ± 7% (seed0 990000).

### Roadmap (adjust to Jainam's results; ask Sanyam before changing order)
1. **v02_openings**: use the 300 ms base for setup. Score settlement *pairs* with the snake order
   (we pick, opponent picks twice, we pick last): production (pips/36), resource diversity
   (no player trading!), ports, complement between our two settlements, expected opponent picks.
2. **v03_expected**: average the value of random-outcome moves (BUY_DEVELOPMENT_CARD, MOVE_ROBBER
   steals, ROLL vs PLAY_KNIGHT before rolling) over several samples instead of one.
3. **v04_lookahead**: same-turn lookahead within budget (trade → build, road building →
   settlement): expand top-k actions, follow our own deterministic follow-ups until END_TURN,
   score the final state; random-outcome actions end the line.
4. **v05_tuned**: write `tools/tune.py` (Jainam runs it): evolution strategy / CMA-ES over the
   weights in **log scale** (multiply, never add), keep public_vps fixed, mutate 1 to 3 weights at a
   time, score by win rate vs F on `--seed0 200000+` only, at least 200 games per candidate,
   parallel processes with one thread each, log every candidate to a CSV.
5. **v06_learned**: learned value function: generate games, record
   `catanatron.features.create_sample_vector(game, color)` (614 numbers) + winner, fit logistic
   regression (scikit-learn), ship coefficients as a .npy file, blend with F's score.
6. **v07_final**: combine only what measurably helped, plus endgame rules (win immediately if any
   action reaches 10 VP; treat opponent's unplayed dev cards as possible hidden VP).

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
