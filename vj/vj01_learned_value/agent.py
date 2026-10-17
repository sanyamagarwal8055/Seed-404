"""vj01_learned_value (parent: v01_catan_fixes). Jainam's experiment, not a team version yet.

Same one-move lookahead as v01, but each candidate position is scored by a learned value function:
logistic regression to "we win", fitted on self-play games (gen_data.py, train.py; seeds 200000 and
up). weights.npz holds the weights with the feature scaling folded in, so scoring is one dot product.

Features (feature_dict below, about 110 numbers, the same for training and play): catanatron's player,
hand and bank features, both players' production with and without the robber, production reachable
with 0/1/2 roads, buildable spots, tiles touched, and ports weighted by our production. Every one of
them means the same thing on any board. catanatron's 614-number create_sample_vector was not used:
most of it is per-node and per-edge ownership tied to one board layout, and it has no production
feature at all, so a linear model cannot learn production from it.

MODE "learned": score = learned logit. MODE "blend": v01's score in victory points plus
BLEND x learned logit. An immediate win always scores highest. If weights.npz is missing or its
feature names do not match, the agent falls back to v01's scoring.
"""
import os
import random

import numpy as np
from catanatron.features import (build_production_features, game_features, player_features,
                                 reachability_features, resource_hand_features)
from catanatron.models.enums import RESOURCES, SETTLEMENT, CITY
from catanatron.players.value import DEFAULT_WEIGHTS, base_fn
from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

MODE = "learned"     # "learned" or "blend"
BLEND = 1.0          # blend only: victory points per unit of learned logit
WIN = 1e18

PROD_ROBBER = build_production_features(True)
PROD_TOTAL = build_production_features(False)

# v01's value function, copied so this folder is self-contained
WEIGHTS = dict(DEFAULT_WEIGHTS)
WEIGHTS["reachable_production_0"] = 1e4
PORT2, PORT3, ROAD, ARMY = 3e7, 1e7, 3e6, 3e6
VP = 3e14            # F's weight on one public victory point
BASE = base_fn(WEIGHTS)


def v01_value(game, color):
    v = BASE(game, color)
    ports = game.state.board.get_player_port_resources(color)
    if ports:
        sample = PROD_ROBBER(game, color)
        for r in ports:
            if r is None:
                v += PORT3 * sum(sample[f"EFFECTIVE_P0_{x}_PRODUCTION"] for x in RESOURCES)
            else:
                v += PORT2 * sample[f"EFFECTIVE_P0_{r}_PRODUCTION"]
    v += ROAD * min(get_longest_road_length(game.state, color), 8)
    v += ARMY * min(get_played_dev_cards(game.state, color, "KNIGHT"), 4)
    return v


def feature_dict(game, color):
    """Board-independent features of `game` from `color`'s point of view (P0 = color, P1 = opponent)."""
    d = {}
    d.update(player_features(game, color))
    d.update(resource_hand_features(game, color))
    d.update(game_features(game, color))
    prod = PROD_ROBBER(game, color)
    d.update(prod)
    d.update(PROD_TOTAL(game, color))
    d.update(reachability_features(game, color, 2))
    board = game.state.board
    for tag, c in (("P0", color), ("P1", next(x for x in game.state.colors if x != color))):
        b = game.state.buildings_by_color[c]
        tiles = set()
        for n in b[SETTLEMENT] + b[CITY]:
            tiles.update(board.map.adjacent_tiles[n])
        d[f"X_{tag}_NUM_TILES"] = len(tiles)
        d[f"X_{tag}_BUILDABLE_NODES"] = len(board.buildable_node_ids(c))
        ports = board.get_player_port_resources(c)
        d[f"X_{tag}_PORT_3TO1"] = 1.0 if None in ports else 0.0
        for r in RESOURCES:
            d[f"X_{tag}_PORT_{r}_X_PROD"] = prod[f"EFFECTIVE_{tag}_{r}_PRODUCTION"] if r in ports else 0.0
    return d


def feature_vector(game, color, names):
    d = feature_dict(game, color)
    return np.array([float(d[n]) for n in names], dtype=np.float64)


class Agent:
    def __init__(self):
        self.rng = random.Random(0)
        self.names, self.w, self.b = None, None, 0.0
        try:
            d = np.load(os.path.join(os.path.dirname(__file__), "weights.npz"))
            self.names, self.w, self.b = list(d["names"]), d["w"].astype(np.float64), float(d["b"])
        except Exception:
            self.w = None

    def score(self, game, color):
        if game.winning_color() == color:
            return WIN
        if self.w is None:
            return v01_value(game, color)
        try:
            logit = float(np.dot(self.w, feature_vector(game, color, self.names))) + self.b
        except KeyError:
            self.w = None
            return v01_value(game, color)
        if MODE == "blend":
            return v01_value(game, color) / VP + BLEND * logit
        return logit

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
                v = self.score(s, obs.me)
                if best_v is None or v > best_v:
                    best_i, best_v = i, v
            return best_i
        except Exception:
            return 0
