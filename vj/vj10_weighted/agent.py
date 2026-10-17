"""vj10_weighted. Jainam's last experiment: four tuned value functions, weighted vote.

Voters (vote weight), ordered by how they did on the portal and the local judge:
  A  member_v3.py   Vivaan's v01_tuned_roadrace (upload #3)            1.5
  B  member_v04.py  Sanyam's v04_tuned, weights.json                   1.0
  C  member_v04.py  weights_v04c.json (v04 tuned 34 more generations)  1.25
  D  member_v04.py  weights_v04b.json (Vivaan's v04 tuning)            0.75
Each member gets vj06's fix (hidden VP cards count; buying a development card is the exact
expectation over unseen cards). Every legal move is played once on one sampled world; each member
votes for its best move with its weight; the highest total wins, ties go to A's pick.
Falls back to A alone when the clock runs low.
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
VOTE = [1.5, 1.0, 1.25, 0.75]   # A, B, C, D


def _load(name):
    spec = importlib.util.spec_from_file_location(f"vj10_{name}", os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _with_vp_cards(fn):
    def value(game, color):
        ps = game.state.player_state
        key = player_key(game.state, color)
        return fn(game, color) + VPCARD * (ps[f"{key}_ACTUAL_VICTORY_POINTS"] - ps[f"{key}_VICTORY_POINTS"])
    return value


def _weights(b, fname):
    w = dict(b.DEFAULTS)
    with open(os.path.join(HERE, fname)) as f:
        for k, v in json.load(f).items():
            if k in w and k != "public_vps":
                w[k] = float(v)
    return w


class Agent:
    def __init__(self):
        self.rng = random.Random(0)
        a = _load("member_v3")
        b = _load("member_v04")
        self.members = [_with_vp_cards(a.value),
                        _with_vp_cards(b.Value(b.load_weights())),
                        _with_vp_cards(b.Value(_weights(b, "weights_v04c.json"))),
                        _with_vp_cards(b.Value(_weights(b, "weights_v04b.json")))]

    def decide(self, obs, playable_actions) -> int:
        try:
            members = self.members
            if obs.cpu_left is not None and obs.cpu_left < LOW_CLOCK:
                members = members[:1]
            world = obs.sample_world(self.rng)
            me = obs.me
            best = [None] * len(members)          # (value, index) per member
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
            tally = {}
            for j, bj in enumerate(best):
                if bj is not None:
                    tally[bj[1]] = tally.get(bj[1], 0.0) + VOTE[j]
            if not tally:
                return 0
            top = max(tally.values())
            if best[0] is not None and tally[best[0][1]] == top:
                return best[0][1]
            return max(tally, key=tally.get)
        except Exception:
            return 0
