"""v05_expect_relative (parent: v01_catan_fixes).

v01's one-move lookahead and value function, with three cheap changes (CPU stays close to v01):
  1. Exact expectation for random moves. Rolling, buying a development card and robbing are scored
     as the probability-weighted average over every outcome (11 dice sums, the unseen dev-card pile,
     the 5 possible stolen resources) using catanatron's execute_spectrum, instead of one random draw.
  2. Move pruning from catanatron's list_prunned_actions: keep only the most damaging robber tile,
     drop 4:1 trades when we own a 3:1 port, drop opening spots touching a single tile.
  3. Relative races. Longest Road and Largest Army progress count as (ours - opponent's), so the
     agent also values stopping a road racer, not only racing itself. Targets our worst matchup
     (road_army_f).
Public code used: catanatron (github.com/bcollazo/catanatron), players/tree_search_utils.py.
"""
import random
import time

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES, ActionType
from catanatron.players.tree_search_utils import execute_spectrum, list_prunned_actions
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4

PORT2 = 3e7   # x our production of the resource a 2:1 port we own trades
PORT3 = 1e7   # x our total production, if we own a 3:1 port
ROAD = 3e6    # x (our - opponent's) longest road length, each capped at 8
ARMY = 3e6    # x (our - opponent's) knights played, each capped at 4

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)

CHANCE = {ActionType.ROLL, ActionType.BUY_DEVELOPMENT_CARD, ActionType.MOVE_ROBBER}


def value(game, color):
    st = game.state
    v = BASE(game, color)
    ports = st.board.get_player_port_resources(color)
    if ports:
        sample = PROD(game, color)
        for r in ports:
            if r is None:
                v += PORT3 * sum(sample[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
            else:
                v += PORT2 * sample[f"EFFECTIVE_P0_{r}_PRODUCTION"]
    opp = next(c for c in st.colors if c != color)
    v += ROAD * (min(get_longest_road_length(st, color), 8) - min(get_longest_road_length(st, opp), 8))
    v += ARMY * (min(get_played_dev_cards(st, color, "KNIGHT"), 4) - min(get_played_dev_cards(st, opp, "KNIGHT"), 4))
    return v


def action_value(world, action, me):
    """Expected value of playing `action` in `world`."""
    if action.action_type in CHANCE:
        outcomes = execute_spectrum(world, action)
        total, mass = 0.0, 0.0
        for g, p in outcomes:
            total += p * value(g, me)
            mass += p
        if mass > 0:
            return total / mass
    s = world.copy()
    s.execute(action)
    return value(s, me)


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        best_i = 0
        try:
            t0 = time.process_time()
            left = obs.cpu_left if obs.cpu_left is not None else 1.0
            deadline = t0 + max(0.002, min(0.30 * left, 0.020))
            world = obs.sample_world(self.rng)
            me = obs.me

            try:
                keep = list_prunned_actions(world)
                cand = [i for i, a in enumerate(playable_actions) if a in keep] or list(range(len(playable_actions)))
            except Exception:
                cand = list(range(len(playable_actions)))

            best_v = None
            for i in cand:
                a = playable_actions[i]
                try:
                    if time.process_time() > deadline and best_v is not None:
                        # out of time: fall back to a plain one-sample evaluation
                        s = world.copy()
                        s.execute(a)
                        v = value(s, me)
                    else:
                        v = action_value(world, a, me)
                except Exception:
                    continue
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return best_i
