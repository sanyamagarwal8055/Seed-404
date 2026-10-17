"""v06_hidden_vp (parent: v04_tuned).

v04's tuned value function and one-move lookahead, plus the one change that measurably helped in
testing (see EXPERIMENTS.md): use information F throws away.
  1. Hidden victory-point cards count. F scores only PUBLIC victory points, so it never values the
     victory-point cards in its own hand, and buying a development card looks worthless to it.
     Here our hidden VP cards are worth the same as public VP (we know our own hand exactly, and
     the engine wins on actual VP).
  2. Exact expectation for random moves. Buying a development card, moving the robber with a steal
     and rolling are scored as the probability-weighted average over every outcome (unseen
     dev-card pile, 5 resources, 11 dice sums) with catanatron's execute_spectrum, instead of one
     random draw. Without this, (1) would make buying a card look great or useless at random.
Tested vs F (300 games each, paired boards): +2.0 and +6.7 points over v04 on two board sets.
Rejected in the same tests: stronger robber pressure, same-turn lookahead, blocking the opponent's
expansion, stronger own expansion, discard penalty, stronger army/production weights, and an
adaptive ensemble with Vivaan's tuned weights (weaker against F).
Public code used: catanatron (github.com/bcollazo/catanatron): base_fn, features, execute_spectrum.
"""
import json
import os
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES, ActionType
from catanatron.players.tree_search_utils import execute_spectrum
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards, player_key

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRA_KEYS = ("port2", "port3", "road", "army", "road_race", "opp_vps", "hidden_vp")

# v04's tuned weights (tools/tune.py -> agents/v04_tuned/weights.json) + hidden_vp
WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS.update({
    "production": 99867842.36405808, "enemy_production": -2611929245.8642206,
    "num_tiles": 2.249526825358086, "reachable_production_0": 23816.572635493212,
    "reachable_production_1": 10000.0, "buildable_nodes": 1000.0, "longest_road": 10.0,
    "hand_synergy": 100.0, "hand_resources": 0.4887008481569078,
    "discard_penalty": -27.098869880319167, "hand_devs": 10.0, "army_size": 17.39151918387456,
    "port2": 13724363.32831911, "port3": 4621750.856883445, "road": 3000000.0,
    "army": 3000000.0, "road_race": 1000000.0, "opp_vps": 11158384176611.244,
    "hidden_vp": 3e14,
})

PROD = build_production_features(True)
CHANCE = {ActionType.BUY_DEVELOPMENT_CARD, ActionType.MOVE_ROBBER, ActionType.ROLL}


def load_weights():
    """Weights used by this agent (tools/tune.py starts from these). weights.json beside this file,
    if present, overrides them."""
    w = dict(WEIGHTS)
    try:
        with open(os.path.join(HERE, "weights.json")) as f:
            for k, v in json.load(f).items():
                if k in w and k != "public_vps":
                    w[k] = float(v)
    except Exception:
        pass
    return w


class Value:
    def __init__(self, w):
        self.w = w
        self.base = base_fn({k: v for k, v in w.items() if k not in EXTRA_KEYS})

    def __call__(self, game, color):
        w = self.w
        st = game.state
        ps = st.player_state
        v = self.base(game, color)
        ports = st.board.get_player_port_resources(color)
        if ports:
            s = PROD(game, color)
            for r in ports:
                if r is None:
                    v += w["port3"] * sum(s[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
                else:
                    v += w["port2"] * s[f"EFFECTIVE_P0_{r}_PRODUCTION"]
        mine = get_longest_road_length(st, color)
        v += w["road"] * min(mine, 8)
        v += w["army"] * min(get_played_dev_cards(st, color, "KNIGHT"), 4)
        key = player_key(st, color)
        v += w["hidden_vp"] * (ps[f"{key}_ACTUAL_VICTORY_POINTS"] - ps[f"{key}_VICTORY_POINTS"])
        for opp in st.colors:
            if opp == color:
                continue
            theirs = get_longest_road_length(st, opp)
            if theirs >= 4:
                v += w["road_race"] * max(-5, min(5, mine - theirs))
            v -= w["opp_vps"] * ps[f"{player_key(st, opp)}_VICTORY_POINTS"]
        return v


class Agent:
    def __init__(self, weights=None):
        self.rng = random.Random(0)
        w = load_weights()
        if weights:                                   # tools/tune.py passes candidate weights
            w.update({k: float(v) for k, v in weights.items() if k in w and k != "public_vps"})
        self.value = Value(w)

    def _action_value(self, world, a, me, exact):
        if exact and a.action_type in CHANCE:
            tot = m = 0.0
            for g, p in execute_spectrum(world, a):
                tot += p * self.value(g, me)
                m += p
            if m > 0:
                return tot / m
        s = world.copy()
        s.execute(a)
        return self.value(s, me)

    def decide(self, obs, playable_actions) -> int:
        best_i = 0
        try:
            left = obs.cpu_left if obs.cpu_left is not None else 1.0
            exact = left > 0.10                        # emergency: skip averaging if nearly out of CPU
            world = obs.sample_world(self.rng)
            me = obs.me
            best_v = None
            for i, a in enumerate(playable_actions):
                try:
                    v = self._action_value(world, a, me, exact)
                except Exception:
                    continue
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return best_i
