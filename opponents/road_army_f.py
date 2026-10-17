"""Opponent: F with a taste for Longest Road and Largest Army.

F's value function plus a bonus per road segment in our longest road and per knight we have played.
F itself nearly ignores both: its road term is 0.1 per segment while any spot is still buildable,
and its knight term is 10.1. (Passing other weights to get_value_fn("base_fn", ...) changes nothing,
it always uses the defaults, so the bonus is added here instead.)

The two bonus sizes are a guess on F's scale (one victory point is 3e14, one production point 1e8).
A fixed sparring partner, not a submission. Style: contests the two bonus cards F neglects.
"""
import random

from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

BASE = base_fn(DEFAULT_WEIGHTS)
ROAD_BONUS = 3e7        # per segment of our longest road
ARMY_BONUS = 3e7        # per knight played, on top of F's own 10.1


def value(game, color):
    return (BASE(game, color)
            + ROAD_BONUS * get_longest_road_length(game.state, color)
            + ARMY_BONUS * get_played_dev_cards(game.state, color, "KNIGHT"))


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        try:
            return self._decide(obs, playable_actions)
        except Exception:
            return self.rng.randrange(len(playable_actions))

    def _decide(self, obs, actions):
        world = obs.sample_world(self.rng)
        best_i, best_v = 0, None
        for i, action in enumerate(actions):
            successor = world.copy()
            try:
                successor.execute(action)
            except Exception:
                continue
            v = value(successor, obs.me)
            if best_v is None or v > best_v:
                best_i, best_v = i, v
        return best_i
