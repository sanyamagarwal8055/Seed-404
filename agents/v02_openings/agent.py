"""v02_openings (parent: v01_catan_fixes).

Same as v01 after setup. Only the initial settlements and roads change: F scores each spot alone
with its 1-move value function. Here a hand-made node score (pips x resource weight, diversity,
ports, same-number penalty) picks settlement PAIRS under the 2-player snake order (P1, P2, P2, P1):
for our first settlement we assume the opponent then takes its best spots and plan our second one;
the second settlement adds a complement bonus for resources the first lacks. Initial roads point
toward the best free node two roads away. Setup capped at ~35 ms per decision; falls back to v01.
"""
import random
import time

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES, ActionType
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4

PORT2 = 3e7   # x our production of the resource a 2:1 port we own trades
PORT3 = 1e7   # x our total production, if we own a 3:1 port
ROAD = 3e6    # x our longest road length, capped at 8
ARMY = 3e6    # x knights we have played, capped at 4

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)

# Opening node score (units: production per roll, a 6 tile = 5/36 = 0.139)
PIPS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
RES_W = {"WHEAT": 1.1, "ORE": 1.05, "WOOD": 1.0, "BRICK": 1.0, "SHEEP": 0.85}
DIVERSITY = 0.02     # per distinct resource at the node
OPEN_PORT2 = 0.04    # 2:1 port on a resource the node produces
OPEN_PORT3 = 0.02    # 3:1 port
SAME_NUMBER = 0.02   # per pair of adjacent tiles sharing a number
COMPLEMENT = 0.03    # per resource the second settlement adds that the first lacks
TOP_K = 10           # first-settlement candidates searched
OPENING_BUDGET = 0.035  # s per setup decision (4 decisions -> ~140 ms)


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


class Opening:
    """Static node scores and node adjacency for one board."""

    def __init__(self, board):
        m = board.map
        self.nbrs = {}
        for tile in m.land_tiles.values():
            for a, b in tile.edges.values():
                self.nbrs.setdefault(a, set()).add(b)
                self.nbrs.setdefault(b, set()).add(a)
        port_of = {}
        for r, nodes in m.port_nodes.items():
            for n in nodes:
                port_of[n] = r
        self.res = {}
        self.score = {}
        for n in m.land_nodes:
            prod, res, numbers = 0.0, set(), []
            for t in m.adjacent_tiles.get(n, []):
                if t.resource is None or t.number is None:
                    continue
                prod += PIPS.get(t.number, 0) / 36 * RES_W.get(t.resource, 1.0)
                res.add(t.resource)
                numbers.append(t.number)
            s = prod + DIVERSITY * len(res)
            s -= SAME_NUMBER * (len(numbers) - len(set(numbers)))
            if n in port_of:
                r = port_of[n]
                if r is None:
                    s += OPEN_PORT3
                elif r in res:
                    s += OPEN_PORT2
            self.res[n] = res
            self.score[n] = s

    def blocked(self, n):
        return {n} | self.nbrs.get(n, set())

    def pair_bonus(self, first, n):
        return COMPLEMENT * len(self.res.get(n, set()) - self.res.get(first, set()))

    def best_second(self, first, legal):
        return max(legal, key=lambda n: self.score.get(n, 0) + self.pair_bonus(first, n),
                   default=None)


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def opening(self, world, obs, playable_actions, deadline):
        """Index of our setup move, or None to use v01's choice."""
        board = world.state.board
        op = Opening(board)
        me = obs.me
        mine = [n for n, (c, _) in board.buildings.items() if c == me]
        n_opp = len(board.buildings) - len(mine)

        settles = [(i, a.value) for i, a in enumerate(playable_actions)
                   if a.action_type == ActionType.BUILD_SETTLEMENT]
        if settles:
            legal = {n for _, n in settles}
            if mine:  # second settlement
                pick = op.best_second(mine[0], legal)
            else:     # first settlement: we are P1 if the opponent has not placed yet
                opp_picks = 2 if n_opp == 0 else 0
                cands = sorted(legal, key=lambda n: op.score.get(n, 0), reverse=True)[:TOP_K]
                pick, best = None, None
                for a in cands:
                    if time.process_time() > deadline:
                        break
                    rest = legal - op.blocked(a)
                    for _ in range(opp_picks):
                        if not rest:
                            break
                        o = max(rest, key=lambda n: op.score.get(n, 0))
                        rest -= op.blocked(o)
                    b = op.best_second(a, rest)
                    v = op.score.get(a, 0)
                    if b is not None:
                        v += op.score.get(b, 0) + op.pair_bonus(a, b)
                    if best is None or v > best:
                        pick, best = a, v
            for i, n in settles:
                if n == pick:
                    return i
            return None

        roads = [(i, a.value) for i, a in enumerate(playable_actions)
                 if a.action_type == ActionType.BUILD_ROAD]
        free = set(board.board_buildable_ids)
        best_i, best = None, None
        for i, (a, b) in roads:
            if time.process_time() > deadline:
                break
            owner = board.buildings.get(a)
            x = b if owner is not None and owner[0] == me else a
            far = (op.nbrs.get(x, set()) & free) - {a, b}
            if not far:
                continue
            v = max(op.score.get(n, 0) for n in far)
            if best is None or v > best:
                best_i, best = i, v
        return best_i

    def decide(self, obs, playable_actions) -> int:
        try:
            start = time.process_time()
            world = obs.sample_world(self.rng)
            if world.state.is_initial_build_phase:
                try:
                    budget = OPENING_BUDGET
                    if obs.cpu_left is not None:
                        budget = min(budget, 0.3 * obs.cpu_left)
                    i = self.opening(world, obs, playable_actions, start + budget)
                    if i is not None and time.process_time() <= start + budget:
                        return i
                except Exception:
                    pass
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
