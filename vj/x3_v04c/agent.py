"""v04_tuned (parent: v01_catan_fixes).

v01's one-move lookahead with EVERY weight tunable (F's 12 weights + v01's 4 Catan fixes) plus two
new relative features that let the tuner react to the opponent: road_race (our longest road minus
theirs, once theirs is >= 4: contests road racers) and opp_vps (penalty per opponent public VP:
values taking Longest Road / Largest Army away from them). Weights come from weights.json beside
this file, found by tools/tune.py (evolution strategy, log-scale steps, fitness = mean win rate over
F + road_army_f + card_hoarder + v01, seeds 200000+). Missing/broken weights.json -> v01 defaults.
"""
import json
import os
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards, player_key

# v01's weights; the starting point for tuning and the fallback if weights.json is missing
DEFAULTS = dict(DEFAULT_WEIGHTS)
DEFAULTS["reachable_production_0"] = 1e4
DEFAULTS.update({
    "port2": 3e7,      # x our production of the resource a 2:1 port we own trades
    "port3": 1e7,      # x our total production, if we own a 3:1 port
    "road": 3e6,       # x our longest road length, capped at 8
    "army": 3e6,       # x knights we have played, capped at 4
    "road_race": 1e6,  # x (our longest road - theirs), clipped to +-5, once theirs is >= 4
    "opp_vps": 3e13,   # x opponent public VPs (subtracted); our own VP is 3e14
})
EXTRA = ("port2", "port3", "road", "army", "road_race", "opp_vps")

PROD = build_production_features(True)


def load_weights():
    w = dict(DEFAULTS)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.json")) as f:
            for k, v in json.load(f).items():
                if k in w and k != "public_vps":
                    w[k] = float(v)
    except Exception:
        pass
    return w


class Value:
    def __init__(self, w):
        self.w = w
        self.base = base_fn({k: v for k, v in w.items() if k not in EXTRA})

    def __call__(self, game, color):
        w = self.w
        state = game.state
        v = self.base(game, color)
        ports = state.board.get_player_port_resources(color)
        if ports:
            sample = PROD(game, color)
            for r in ports:
                if r is None:
                    v += w["port3"] * sum(sample[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
                else:
                    v += w["port2"] * sample[f"EFFECTIVE_P0_{r}_PRODUCTION"]
        mine = get_longest_road_length(state, color)
        v += w["road"] * min(mine, 8)
        v += w["army"] * min(get_played_dev_cards(state, color, "KNIGHT"), 4)
        for opp in state.colors:
            if opp == color:
                continue
            theirs = get_longest_road_length(state, opp)
            if theirs >= 4:
                v += w["road_race"] * max(-5, min(5, mine - theirs))
            v -= w["opp_vps"] * state.player_state[f"{player_key(state, opp)}_VICTORY_POINTS"]
        return v


class Agent:
    def __init__(self, weights=None):
        self.rng = random.Random(0)
        w = load_weights()
        if weights:
            w.update({k: float(v) for k, v in weights.items() if k in w and k != "public_vps"})
        self.value = Value(w)

    def decide(self, obs, playable_actions) -> int:
        try:
            world = obs.sample_world(self.rng)
            best_i, best_v = 0, None
            for i, action in enumerate(playable_actions):
                s = world.copy()
                try:
                    s.execute(action)
                except Exception:
                    continue
                v = self.value(s, obs.me)
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return 0
