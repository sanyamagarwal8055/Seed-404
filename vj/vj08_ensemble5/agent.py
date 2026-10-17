"""vj08_ensemble5 (parent: vj07_ensemble). Jainam's experiment: four tuned value functions vote.

As vj07, plus a fourth member D = member_v04.py with weights_v04b.json (v04 tuned 20 more
generations on the laptop against F, road_army_f, card_hoarder and v01). Plurality vote: the move
with the most votes is played; ties go to the move A voted for.

vj07 header follows.

Members (copied into this folder, unchanged):
  A  member_v3.py   Vivaan's v01_tuned_roadrace (upload #3, best on the portal so far)
  B  member_v04.py  Sanyam's v04_tuned with its weights.json
  C  member_v04.py  the same value class with weights_v04c.json (v04 tuned further against
                    F, road_army_f and v04 itself, 34 generations)
Each member also gets vj06's fix: our hidden VP cards count as points, and buying a development
card is scored as the exact expectation over the cards we cannot see (execute_spectrum).

Every legal move is played once on one sampled world; each member scores the results and votes for
its best move. A move with at least two votes is played; if all three disagree, A's choice is played.
Each tuning run is partly luck (fitted to its own boards and opponents); a vote keeps only the
choices that independent runs agree on. Falls back to A alone when the clock runs low.
"""
import importlib.util
import json
import os
import random

from catanatron.models.enums import ActionType
from catanatron.players.tree_search_utils import execute_spectrum
from catanatron.state_functions import player_key

HERE = os.path.dirname(os.path.abspath(__file__))
VPCARD = 0.5 * 3e14      # one hidden VP card, in F's units (vj06, K = 0.5)
LOW_CLOCK = 0.15         # s of cpu_left below which only member A is used


def _load(name):
    spec = importlib.util.spec_from_file_location(f"vj08_{name}", os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _with_vp_cards(fn):
    def value(game, color):
        ps = game.state.player_state
        key = player_key(game.state, color)
        return fn(game, color) + VPCARD * (ps[f"{key}_ACTUAL_VICTORY_POINTS"] - ps[f"{key}_VICTORY_POINTS"])
    return value


class Agent:
    def __init__(self):
        self.rng = random.Random(0)
        a = _load("member_v3")
        b = _load("member_v04")
        wc = dict(b.DEFAULTS)
        with open(os.path.join(HERE, "weights_v04c.json")) as f:
            for k, v in json.load(f).items():
                if k in wc and k != "public_vps":
                    wc[k] = float(v)
        wd = dict(b.DEFAULTS)
        with open(os.path.join(HERE, "weights_v04b.json")) as f:
            for k, v in json.load(f).items():
                if k in wd and k != "public_vps":
                    wd[k] = float(v)
        self.members = [_with_vp_cards(a.value),
                        _with_vp_cards(b.Value(b.load_weights())),
                        _with_vp_cards(b.Value(wc)),
                        _with_vp_cards(b.Value(wd))]

    def decide(self, obs, playable_actions) -> int:
        try:
            members = self.members
            if obs.cpu_left is not None and obs.cpu_left < LOW_CLOCK:
                members = members[:1]
            world = obs.sample_world(self.rng)
            me = obs.me
            n = len(members)
            best = [None] * n          # (value, index) per member
            for i, action in enumerate(playable_actions):
                try:
                    if action.action_type == ActionType.BUY_DEVELOPMENT_CARD:
                        outs = execute_spectrum(world, action)
                        vals = [sum(p * m(g, me) for g, p in outs) for m in members]
                    else:
                        s = world.copy()
                        s.execute(action)
                        vals = [m(s, me) for m in members]
                except Exception:
                    continue
                for j, v in enumerate(vals):
                    if best[j] is None or v > best[j][0]:
                        best[j] = (v, i)
            picks = [b[1] for b in best if b is not None]
            if not picks:
                return 0
            top = max(picks.count(i) for i in picks)
            if picks.count(picks[0]) == top:
                return picks[0]
            return next(i for i in picks if picks.count(i) == top)
        except Exception:
            return 0
