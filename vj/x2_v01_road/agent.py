"""x2_v01_road (parent: v01_catan_fixes). Jainam's experiment: v01 with road_army_f's road bonus.

Only change: road bonus 3e6 per segment capped at 8 -> 3e7 per segment, no cap (road_army_f's size).
road_army_f beats or ties every version we have; this tests whether its road weight is the reason.
"""
"""v01_catan_fixes (parent: v00_f_copy).

F's one-move lookahead and F's 13-feature value function, plus four Catan fixes F is missing:
  1. Ports: F has no port feature. Bonus for owning a 2:1 port on a resource we produce, and a
     3:1 port scaled by our total production.
  2. Longest Road progress: F only counts road length once there is nowhere left to build.
     Small always-on bonus per road segment (capped at 8).
  3. Largest Army progress: F weights played knights at 10.1, almost nothing. Bonus per knight
     played (capped at 4).
  4. reachable_production_0: production at spots we can build on right now. F weights it 0;
     here 1e4, the same as F's weight for spots one road away.
Quick checks (200 games each vs F, seed0 100000, prototype runs, not yet in results.csv):
ports 52.5%, road 55.0%, army 53.5%, reachable_production_0 54.5%, all +-6.9%.
"""
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4

PORT2 = 3e7   # x our production of the resource a 2:1 port we own trades
PORT3 = 1e7   # x our total production, if we own a 3:1 port
ROAD = 3e7    # x our longest road length, no cap (road_army_f size)
ARMY = 3e6    # x knights we have played, capped at 4

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
    v += ROAD * get_longest_road_length(game.state, color)
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
