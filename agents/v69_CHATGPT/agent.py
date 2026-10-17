"""v06_expect_tuned (parent: v01_tuned_roadrace).
Keep the latest empirically strongest weight/road-race policy, but evaluate stochastic
actions by expected value and recognize actual terminal wins. Uses a strict per-decision
CPU budget and a cheap fallback so every legal action remains eligible.
"""

import random
import time

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES, ActionType
from catanatron.players.tree_search_utils import execute_spectrum
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

# Frozen values from tuning/v01_tuned_roadrace/agent.py, which scored 62.3% vs F
# over 1,000 organiser-kit games and 58.5% vs road_army_f over 400 games.
MULT = {
    "production": 1.244515,
    "enemy_production": 1.995262,
    "buildable_nodes": 0.86896,
    "hand_synergy": 1.5417,
    "hand_resources": 0.275423,
    "hand_devs": 3.372873,
    "ROAD": 0.060954,
    "ROAD_REL": 10_000_000.0,
}

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4
for _key in (
    "production",
    "enemy_production",
    "num_tiles",
    "reachable_production_0",
    "reachable_production_1",
    "buildable_nodes",
    "hand_synergy",
    "hand_resources",
    "hand_devs",
):
    WEIGHTS[_key] *= MULT.get(_key, 1.0)

BASE_VALUE = base_fn(WEIGHTS)
PRODUCTION_FEATURES = build_production_features(True)
PORT_2_TO_1 = 3e7
PORT_3_TO_1 = 1e7
ROAD_WEIGHT = 3e6 * MULT["ROAD"]
ARMY_WEIGHT = 3e6
ROAD_RACE_WEIGHT = MULT["ROAD_REL"]
WIN_SCORE = 1e30

# Only these action types require chance enumeration in the pinned Catanatron build.
CHANCE_ACTIONS = {
    ActionType.ROLL,
    ActionType.BUY_DEVELOPMENT_CARD,
    ActionType.MOVE_ROBBER,
}


def position_value(game, color, terminal=True):
    """Evaluate a successor state from our perspective."""
    if terminal:
        try:
            winner = game.winning_color()
            if winner is not None:
                return WIN_SCORE if winner == color else -WIN_SCORE
        except Exception:
            # A scoring fallback is safer than crashing if the engine state is unusual.
            pass

    state = game.state
    score = BASE_VALUE(game, color)

    # Ports have value only to the extent that we can actually produce their resource.
    ports = state.board.get_player_port_resources(color)
    if ports:
        production = PRODUCTION_FEATURES(game, color)
        for resource in ports:
            if resource is None:  # generic 3:1 port
                score += PORT_3_TO_1 * sum(
                    production[f"EFFECTIVE_P0_{r}_PRODUCTION"] for r in RESOURCES
                )
            else:  # specific 2:1 port
                score += PORT_2_TO_1 * production[
                    f"EFFECTIVE_P0_{resource}_PRODUCTION"
                ]

    mine = get_longest_road_length(state, color)
    score += ROAD_WEIGHT * min(mine, 8)
    score += ARMY_WEIGHT * min(get_played_dev_cards(state, color, "KNIGHT"), 4)

    # This is the feature that helped the road-racer matchup: a relative, capped race
    # is much more useful than valuing only our own road length.
    opponent = next((c for c in state.colors if c != color), None)
    if opponent is not None:
        theirs = get_longest_road_length(state, opponent)
        gap = max(-5, min(5, mine - theirs))
        score += ROAD_RACE_WEIGHT * gap

    return score


def _sampled_action_value(world, action, color):
    """Fast one-sample fallback; never treats a lucky sampled VP draw as certain."""
    successor = world.copy()
    successor.execute(action)
    return position_value(
        successor,
        color,
        terminal=action.action_type not in CHANCE_ACTIONS,
    )


def _expected_action_value(world, action, color):
    """Expected score across the engine's enumerated random outcomes."""
    outcomes = execute_spectrum(world, action)
    total = 0.0
    mass = 0.0
    for successor, probability in outcomes:
        p = float(probability)
        if p <= 0.0:
            continue
        total += p * position_value(successor, color, terminal=True)
        mass += p
    if mass <= 0.0:
        raise ValueError("execute_spectrum returned no positive-probability outcomes")
    return total / mass


class Agent:
    def __init__(self):
        self.rng = random.Random(404)

    def decide(self, obs, playable_actions) -> int:
        # The harness normally hides forced moves, but stay safe if called with one.
        if not playable_actions:
            return 0
        if len(playable_actions) == 1:
            return 0

        best_index = 0
        try:
            world = obs.sample_world(self.rng)
            color = obs.me

            # At most 12 ms of detailed work per call: below the 12.5 ms increment.
            # We spend it first on stochastic actions, whose single sampled outcome is noisy.
            cpu_left = getattr(obs, "cpu_left", None)
            if cpu_left is None:
                cpu_left = 1.0
            budget = min(0.012, max(0.001, 0.20 * max(float(cpu_left), 0.0)))
            deadline = time.process_time() + budget

            scores = [None] * len(playable_actions)

            # Exact expectation for chance actions while budget remains. These are few;
            # they can include a rare instant win (e.g. drawing the final VP card).
            for i, action in enumerate(playable_actions):
                if action.action_type not in CHANCE_ACTIONS:
                    continue
                if time.process_time() >= deadline:
                    break
                try:
                    scores[i] = _expected_action_value(world, action, color)
                except Exception:
                    # Keep it eligible; the inexpensive fallback scores it below.
                    scores[i] = None

            # Score every unscored legal action, even after the detailed budget expires.
            # This avoids accidentally biasing decisions toward early entries in the action list.
            best_score = float("-inf")
            for i, action in enumerate(playable_actions):
                if scores[i] is None:
                    try:
                        scores[i] = _sampled_action_value(world, action, color)
                    except Exception:
                        scores[i] = float("-inf")
                score = scores[i]
                if score > best_score:
                    best_score = score
                    best_index = i

            return best_index
        except Exception:
            # The submission must never raise or return an illegal index.
            return best_index if 0 <= best_index < len(playable_actions) else 0
