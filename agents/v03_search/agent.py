"""v03_search (parent: v01_catan_fixes).

Same value function as v01; spends the spare CPU on search instead of one sample per move.
  1. Random-outcome moves are scored as their exact expected value: ROLL over the 11 dice sums,
     MOVE_ROBBER over the victim's (known) hand, BUY_DEVELOPMENT_CARD over the deck's card types.
     v01/F score each of these on one random outcome.
  2. The top-k deterministic moves are extended greedily with our own deterministic same-turn
     follow-ups (trade -> build, road building -> settlement, knight -> robber) and scored on
     the final position, so moves that only pay off one step later are no longer undervalued.
Budget per decision: 20 ms (40 ms in the first turns), never more than 30% of obs.cpu_left;
past the deadline it falls back to v01's one-sample scoring and returns the best found so far.
"""
import random
import time

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES, ActionType
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards, player_key

try:
    from catanatron.models.enums import ActionRecord
except Exception:
    ActionRecord = None

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4

PORT2 = 3e7   # x our production of the resource a 2:1 port we own trades
PORT3 = 1e7   # x our total production, if we own a 3:1 port
ROAD = 3e6    # x our longest road length, capped at 8
ARMY = 3e6    # x knights we have played, capped at 4

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)

# Search settings
TOP_K = 4            # deterministic root moves extended with same-turn follow-ups
MAX_DEPTH = 3        # follow-up moves per line
CAP = 0.020          # s per decision
OPENING_CAP = 0.040  # s per decision while obs.turn < OPENING_TURNS
OPENING_TURNS = 10
CPU_SHARE = 0.3      # never more than this share of obs.cpu_left in one decision

RANDOM_TYPES = {getattr(ActionType, n) for n in
                ("ROLL", "BUY_DEVELOPMENT_CARD", "MOVE_ROBBER", "DISCARD", "DISCARD_RESOURCE")
                if hasattr(ActionType, n)}
# One dice pair per sum, with the number of ways (out of 36) to roll that sum
DICE = [((1, 1), 1), ((1, 2), 2), ((1, 3), 3), ((1, 4), 4), ((1, 5), 5), ((1, 6), 6),
        ((2, 6), 5), ((3, 6), 4), ((4, 6), 3), ((5, 6), 2), ((6, 6), 1)]


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


def after(world, action):
    """Copy of world with action played (random outcome drawn by the engine)."""
    s = world.copy()
    s.execute(action)
    return s


def forced(world, action, result, me):
    """Value after action with its random outcome fixed to result."""
    s = world.copy()
    s.execute(action, validate_action=False, action_record=ActionRecord(action, result))
    return value(s, me)


def expected(world, action, me):
    """Exact expected value of a random-outcome move; one engine sample if that fails."""
    t = action.action_type
    try:
        if ActionRecord is not None:
            if t == ActionType.ROLL:
                return sum(w * forced(world, action, d, me) for d, w in DICE) / 36
            if t == ActionType.MOVE_ROBBER and action.value[1] is not None:
                key = player_key(world.state, action.value[1])
                hand = [(r, world.state.player_state[f"{key}_{r}_IN_HAND"]) for r in RESOURCES]
                total = sum(n for _, n in hand)
                if total > 0:
                    return sum(n * forced(world, action, r, me) for r, n in hand if n) / total
            if t == ActionType.BUY_DEVELOPMENT_CARD:
                deck = world.state.development_listdeck
                if deck:
                    return sum(deck.count(c) * forced(world, action, c, me)
                               for c in set(deck)) / len(deck)
    except Exception:
        pass
    return value(after(world, action), me)


def legal(game):
    acts = getattr(game, "playable_actions", None)
    return acts if acts is not None else game.state.playable_actions


def follow(s, v, me, deadline):
    """Greedy line of our own deterministic same-turn moves from s; value at its end."""
    for _ in range(MAX_DEPTH):
        if time.process_time() > deadline or s.winning_color() is not None:
            break
        if s.state.current_color() != me:
            break
        acts = legal(s)
        if acts and all(a.action_type == ActionType.MOVE_ROBBER for a in acts):
            # forced robber move (e.g. after a knight): best expected placement ends the line
            return max(expected(s, a, me) for a in acts)
        best_s, best_v = None, v
        for a in acts:
            if a.action_type in RANDOM_TYPES or a.action_type == ActionType.END_TURN:
                continue
            if time.process_time() > deadline:
                break
            try:
                n = after(s, a)
            except Exception:
                continue
            nv = value(n, me)
            if nv > best_v:
                best_s, best_v = n, nv
        if best_s is None:
            break
        s, v = best_s, best_v
    return v


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        best_i = 0
        try:
            start = time.process_time()
            turn = getattr(obs, "turn", None)
            budget = OPENING_CAP if turn is not None and turn < OPENING_TURNS else CAP
            if obs.cpu_left is not None:
                budget = min(budget, CPU_SHARE * obs.cpu_left)
            deadline = start + budget
            me = obs.me
            world = obs.sample_world(self.rng)

            # 1. score every move: exact expectation for random outcomes, one step otherwise
            scores, states = {}, {}
            for i, action in enumerate(playable_actions):
                try:
                    if action.action_type in RANDOM_TYPES and time.process_time() < deadline:
                        scores[i] = expected(world, action, me)
                    else:
                        s = after(world, action)
                        if s.winning_color() == me:
                            return i
                        scores[i] = value(s, me)
                        if action.action_type not in RANDOM_TYPES:
                            states[i] = s
                except Exception:
                    continue
                if best_i not in scores or scores[i] > scores[best_i]:
                    best_i = i

            # 2. extend the top-k deterministic moves with our same-turn follow-ups
            top = sorted((i for i in states
                          if playable_actions[i].action_type != ActionType.END_TURN),
                         key=lambda i: scores[i], reverse=True)[:TOP_K]
            for i in top:
                if time.process_time() > deadline:
                    break
                try:
                    v = follow(states[i], scores[i], me, deadline)
                except Exception:
                    continue
                if v > scores[i]:
                    scores[i] = v
                    if v > scores[best_i]:
                        best_i = i
            return best_i
        except Exception:
            return best_i
