"""Opponent: greedy builder. Always takes the most expensive build it can afford.

Priority: city, then settlement, then road, then development card, then everything else; ending the
turn comes last and bank trades never. Among moves of the same kind (for example which spot to put a
settlement on) it picks by F's value function, so it places well but never saves resources.

A fixed sparring partner, not a submission. Style: fast expansion, no card play planning.
"""
import random

from catanatron.models.enums import ActionType as AT
from catanatron.players.value import DEFAULT_WEIGHTS, get_value_fn

VALUE_FN = get_value_fn("base_fn", DEFAULT_WEIGHTS)

RANK = {
    AT.BUILD_CITY: 0,
    AT.BUILD_SETTLEMENT: 1,
    AT.BUILD_ROAD: 2,
    AT.BUY_DEVELOPMENT_CARD: 3,
    AT.PLAY_KNIGHT_CARD: 4,
    AT.PLAY_YEAR_OF_PLENTY: 4,
    AT.PLAY_MONOPOLY: 4,
    AT.PLAY_ROAD_BUILDING: 4,
    AT.END_TURN: 8,
    AT.MARITIME_TRADE: 9,
}
DEFAULT_RANK = 5        # ROLL, MOVE_ROBBER, DISCARD_RESOURCE: a forced kind of choice


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        try:
            return self._decide(obs, playable_actions)
        except Exception:
            return self.rng.randrange(len(playable_actions))

    def _decide(self, obs, actions):
        rank = [RANK.get(a.action_type, DEFAULT_RANK) for a in actions]
        best = min(rank)
        candidates = [i for i, r in enumerate(rank) if r == best]
        if len(candidates) == 1:
            return candidates[0]
        world = obs.sample_world(self.rng)
        best_i, best_v = candidates[0], None
        for i in candidates:
            successor = world.copy()
            try:
                successor.execute(actions[i])
            except Exception:
                continue
            v = VALUE_FN(successor, obs.me)
            if best_v is None or v > best_v:
                best_i, best_v = i, v
        return best_i
