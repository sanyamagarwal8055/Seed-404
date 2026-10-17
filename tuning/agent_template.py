"""v01_catan_fixes with its weights read from weights.json beside this file (for tuning only).

With weights.json holding {"mult": {}} (or missing) this plays exactly like v01. Each entry of "mult"
is a factor applied to one of v01's weights.
"""
import json
import os
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.json")) as fh:
        MULT = json.load(fh).get("mult", {})
except Exception:
    MULT = {}

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4
for _k in ("production", "enemy_production", "num_tiles", "reachable_production_0",
           "reachable_production_1", "buildable_nodes", "hand_synergy", "hand_resources", "hand_devs"):
    WEIGHTS[_k] = WEIGHTS[_k] * MULT.get(_k, 1.0)

PORT2 = 3e7 * MULT.get("PORT2", 1.0)
PORT3 = 1e7 * MULT.get("PORT3", 1.0)
ROAD = 3e6 * MULT.get("ROAD", 1.0)
ARMY = 3e6 * MULT.get("ARMY", 1.0)
#: absolute weight (not a factor) on (our longest road - opponent's), capped at +-5; 0 = off, as in v01
ROAD_REL = float(MULT.get("ROAD_REL", 0.0))

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)


def value(game, color):
    v = BASE(game, color)
    ports = game.state.board.get_player_port_resources(color)
    if ports:
        sample = PROD(game, color)
        for r in ports:
            if r is None:
                v += PORT3 * sum(sample[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
            else:
                v += PORT2 * sample[f"EFFECTIVE_P0_{r}_PRODUCTION"]
    v += ROAD * min(get_longest_road_length(game.state, color), 8)
    v += ARMY * min(get_played_dev_cards(game.state, color, "KNIGHT"), 4)
    if ROAD_REL:
        opp = next(c for c in game.state.colors if c != color)
        gap = get_longest_road_length(game.state, color) - get_longest_road_length(game.state, opp)
        v += ROAD_REL * max(-5, min(5, gap))
    return v


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

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
                v = value(s, obs.me)
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return 0
