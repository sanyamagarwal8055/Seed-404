"""v02_turn_rollout_counter_F_winfix: the pasted agent with only the win/loss values fixed (1e14 -> 1e18).
(parent: v01_tuned_roadrace).
Upgrades over v01_tuned_roadrace:
  1. Intra-turn greedy rollout lookahead: evaluates trades (2:1, 3:1, 4:1) and dev-card
     plays (Monopoly, Year of Plenty, Road Building, Knight) by simulating the follow-up
     builds within the same turn before scoring the board state.
  2. Multi-sample expected value for stochastic actions (BUY_DEVELOPMENT_CARD, MOVE_ROBBER)
     so the agent isn't baited by a lucky single-sample VP draw or unlucky Knight draw.
  3. 1v1 Zero-Sum VP, Longest Road, and Largest Army relative swing terms against F.
  4. Resource diversity / Ore-Wheat city synergy & >7 card anti-robber discard protection.
(Vivaan's session: removed `get_Largest_Army` from the imports; it does not exist in the pinned
engine, is not used below, and made the whole file fail to load. Nothing else changed.)
"""
import random

from catanatron.features import build_production_features
from catanatron.models.enums import RESOURCES
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import (
    get_actual_victory_points,
    get_dev_cards_in_hand,
    get_longest_road_color,
    get_longest_road_length,
    get_played_dev_cards,
    get_player_buildings,
    player_key,
    player_num_resource_cards,
)

MULT = {
    "production": 1.32,
    "enemy_production": 2.15,
    "buildable_nodes": 0.92,
    "hand_synergy": 1.65,
    "hand_resources": 0.28,
    "hand_devs": 3.25,
    "ROAD": 0.08,
    "ROAD_REL": 12000000.0,
}

WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1.2e4
for _k in (
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
    WEIGHTS[_k] = WEIGHTS[_k] * MULT.get(_k, 1.0)

PORT2 = 3.2e7
PORT3 = 1.15e7
ROAD = 3e6 * MULT.get("ROAD", 1.0)
ARMY = 3.5e6
ROAD_REL = float(MULT.get("ROAD_REL", 1.2e7))
ARMY_REL = 1.1e7
OPP_VP_PENALTY = 1.1e8  # Strongly penalize opponent VPs (especially Longest Road / Largest Army steals)
DIVERSITY_BONUS = 8.5e6
OWS_SYNERGY = 1.4e7
OVER_7_PENALTY = 1.8e7  # Penalty per card over 7 when ending turn (anti-7 discard protection)

BASE = base_fn(WEIGHTS)
PROD = build_production_features(True)


def value(game, color):
    state = game.state
    opp = next(c for c in state.colors if c != color)

    # Terminal win/loss check: massive priority on immediate victory or preventing immediate loss
    try:
        my_vp = get_actual_victory_points(state, color)
        opp_vp = get_actual_victory_points(state, opp)
        if my_vp >= 10:
            return 1e18 + my_vp * 1e10      # above any non-winning state (VPs are worth 3e14 each)
        if opp_vp >= 10:
            return -1e18
    except Exception:
        my_vp, opp_vp = 0, 0

    v = BASE(game, color)

    # 1. Zero-sum Opponent VP suppression (blocks F from getting Longest Road / Army / Cities)
    v -= OPP_VP_PENALTY * opp_vp

    # 2. Production, Port Synergy, Diversity & Ore-Wheat-Sheep / Wood-Brick Synergy
    sample = PROD(game, color)
    my_prods = {r: sample[f"EFFECTIVE_P0_{r}_PRODUCTION"] for r in RESOURCES}

    ports = state.board.get_player_port_resources(color)
    if ports:
        total_prod = sum(my_prods.values())
        for r in ports:
            if r is None:
                v += PORT3 * total_prod
            else:
                v += PORT2 * my_prods[r]

    # Reward having distinct resource types producing (> 0)
    active_types = sum(1 for p in my_prods.values() if p > 0)
    v += DIVERSITY_BONUS * active_types

    # Reward City + Dev Card engine (Ore + Wheat synergy) and Early Road/Settlement (Wood + Brick)
    ore_p, wheat_p, sheep_p = my_prods["ORE"], my_prods["WHEAT"], my_prods["SHEEP"]
    wood_p, brick_p = my_prods["WOOD"], my_prods["BRICK"]
    v += OWS_SYNERGY * min(ore_p, wheat_p)
    v += 0.6 * OWS_SYNERGY * min(ore_p, wheat_p, sheep_p)
    v += 0.5 * OWS_SYNERGY * min(wood_p, brick_p)

    # 3. Road Race & Longest Road Crown Control
    my_road = get_longest_road_length(state, color)
    opp_road = get_longest_road_length(state, opp)
    v += ROAD * min(my_road, 8)
    if ROAD_REL:
        gap = my_road - opp_road
        v += ROAD_REL * max(-5, min(5, gap))
        # Extra urgency when fighting near the >=5 Longest Road threshold
        if my_road >= 4 or opp_road >= 4:
            v += 0.75 * ROAD_REL * max(-3, min(3, gap))

    # 4. Knight Race & Largest Army Crown Control
    my_knights = get_played_dev_cards(state, color, "KNIGHT")
    opp_knights = get_played_dev_cards(state, opp, "KNIGHT")
    v += ARMY * min(my_knights, 5)
    k_gap = my_knights - opp_knights
    v += ARMY_REL * max(-4, min(4, k_gap))

    # 5. Anti-7 Discard Protection: penalize holding >7 cards when about to pass turn
    try:
        num_cards = player_num_resource_cards(state, color)
        if num_cards > 7:
            v -= OVER_7_PENALTY * (num_cards - 7)
    except Exception:
        pass

    return v


def _action_type_name(action) -> str:
    at = getattr(action, "action_type", None)
    return getattr(at, "name", str(at))


def _greedy_finish_turn(sim_game, color, max_steps=3):
    """If an action (like MARITIME_TRADE or playing a Dev Card) keeps it our turn,
    greedily roll out up to `max_steps` follow-up deterministic actions so trades
    and dev cards are judged by the buildings they unlock."""
    for _ in range(max_steps):
        try:
            if sim_game.winning_color() is not None:
                break
            if sim_game.state.current_color() != color:
                break
            playable = getattr(sim_game.state, "playable_actions", None)
            if not playable:
                break
            # Stop rollout if the only action is ROLL or END_TURN
            if len(playable) == 1:
                aname = _action_type_name(playable[0])
                if "ROLL" in aname or "END_TURN" in aname:
                    break

            best_sub_a = None
            best_sub_v = None
            for sub_a in playable:
                sub_name = _action_type_name(sub_a)
                if "ROLL" in sub_name:
                    continue
                g2 = sim_game.copy()
                g2.execute(sub_a)
                sv = value(g2, color)
                if best_sub_v is None or sv > best_sub_v:
                    best_sub_v = sv
                    best_sub_a = sub_a

            if best_sub_a is None or "END_TURN" in _action_type_name(best_sub_a):
                break
            sim_game.execute(best_sub_a)
        except Exception:
            break


class Agent:
    def __init__(self):
        self.rng = random.Random(0)

    def decide(self, obs, playable_actions) -> int:
        try:
            if len(playable_actions) <= 1:
                return 0

            me = obs.me
            # Sample 3 worlds to smooth hidden-information variance (dev deck + opponent hand)
            worlds = [obs.sample_world(self.rng) for _ in range(3)]
            primary_world = worlds[0]

            # Enable intra-turn rollout whenever we have trades or resource-generating dev cards
            has_combo_moves = any(
                any(k in _action_type_name(a) for k in ("TRADE", "MONOPOLY", "YEAR_OF_PLENTY", "ROAD_BUILDING"))
                for a in playable_actions
            )

            best_i, best_v = 0, None
            for i, action in enumerate(playable_actions):
                aname = _action_type_name(action)
                is_stochastic = any(k in aname for k in ("BUY_DEVELOPMENT_CARD", "MOVE_ROBBER"))

                # Average across 3 worlds for stochastic actions (dev card draw / robber steal)
                eval_worlds = worlds if is_stochastic else (primary_world,)
                total_v = 0.0
                valid_runs = 0

                for w in eval_worlds:
                    s = w.copy()
                    try:
                        s.execute(action)
                        if has_combo_moves and "END_TURN" not in aname and "ROLL" not in aname:
                            _greedy_finish_turn(s, me, max_steps=2)
                        total_v += value(s, me)
                        valid_runs += 1
                    except Exception:
                        continue

                if valid_runs == 0:
                    continue
                avg_v = total_v / valid_runs
                if best_v is None or avg_v > best_v:
                    best_i, best_v = i, avg_v

            return best_i
        except Exception:
            return 0
