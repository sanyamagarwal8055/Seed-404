"""vj04_tuned (parent: v01_catan_fixes). Jainam's experiment: v01 with every weight tuned
on win rate against F by an evolution strategy (tune_es.py, seeds 500000 and up,
perfect-information games). Only the numbers below differ from v01.
Tuner's own estimate for these weights: 0.643 over 300 games against F.
"""
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["production"] = 13103063829.652002
WEIGHTS["enemy_production"] = -53096758.58703757
WEIGHTS["num_tiles"] = 0.40096269347911606
WEIGHTS["reachable_production_0"] = 468.81170141373036
WEIGHTS["reachable_production_1"] = 1096.3861243972735
WEIGHTS["buildable_nodes"] = 849.7140536182883
WEIGHTS["longest_road"] = 4.129760072823081
WEIGHTS["hand_synergy"] = 111.40908291729576
WEIGHTS["hand_resources"] = 0.12677782071208898
WEIGHTS["discard_penalty"] = -5937.884210982386
WEIGHTS["hand_devs"] = 25.385658821177046
WEIGHTS["army_size"] = 98.76922967860878

PORT2 = 16514263.99679654   # x our production of the resource a 2:1 port we own trades
PORT3 = 87631.77195672184   # x our total production, if we own a 3:1 port
ROAD = 1174891.971801412    # x our longest road length, capped at 8
ARMY = 573301.9792643741    # x knights we have played, capped at 4

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
