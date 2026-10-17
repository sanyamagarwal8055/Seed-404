"""vj06_vpcards (parent: v01_tuned_roadrace, upload #3). Jainam's experiment.

F's value function (and every version built on it) scores victory points with the PUBLIC count,
P0_VICTORY_POINTS. A Victory Point development card only raises ACTUAL_VICTORY_POINTS
(catanatron state_functions.py), so to F a VP card is worth nothing, and buying a development card
(5 of the 25 are VP cards: about 0.2 points each) is valued at hand_devs = 10 instead of ~6e13.
Two changes, nothing else:
  1. Our hidden VP cards count as points: + VPCARD * (actual VPs - public VPs), VPCARD = K x 3e14.
  2. BUY_DEVELOPMENT_CARD is scored as its exact expectation over the cards we cannot see
     (catanatron's execute_spectrum), not on one random draw.
"""
"""v01_tuned_roadrace (parent: v01_catan_fixes). Vivaan's tuning run, 17 Oct 2026.

v01's value function with tuned weights plus one new term:
  1. Weights from an evolution strategy (6 rounds, 200 games vs F + 120 vs road_army_f per candidate,
     boards 200000+): enemy production x2, own production x1.24, development cards held x3.4,
     hand close to a build (hand_synergy) x1.54, raw hand size x0.28, buildable spots x0.87,
     road-length bonus x0.06.
  2. Road race: +1e7 per segment our longest road leads the opponent's (capped at +-5).
Fresh boards 700000+ (never used for tuning), same 300 games vs F and 180 vs road_army_f for both:
  v01 0.570 vs F, 0.472 vs road_army_f; this version 0.620 vs F, 0.567 vs road_army_f.
Not yet judged on 990000 and not yet seen by the portal (O unknown).
"""
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.models.enums import ActionType
from catanatron.players.tree_search_utils import execute_spectrum
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards, player_key

MULT = {
    "production": 1.244515,
    "enemy_production": 1.995262,
    "buildable_nodes": 0.86896,
    "hand_synergy": 1.5417,
    "hand_resources": 0.275423,
    "hand_devs": 3.372873,
    "ROAD": 0.060954,
    "ROAD_REL": 10000000.0
}

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

K = 0.5             # value of one hidden VP card, as a fraction of a public victory point
VPCARD = K * 3e14

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)


def value(game, color):
    v = BASE(game, color)
    key = player_key(game.state, color)
    ps = game.state.player_state
    v += VPCARD * (ps[f"{key}_ACTUAL_VICTORY_POINTS"] - ps[f"{key}_VICTORY_POINTS"])
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
                try:
                    if action.action_type == ActionType.BUY_DEVELOPMENT_CARD:
                        v = sum(p * value(g, obs.me) for g, p in execute_spectrum(world, action))
                    else:
                        s = world.copy()
                        s.execute(action)
                        v = value(s, obs.me)
                except Exception:
                    continue
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return 0
