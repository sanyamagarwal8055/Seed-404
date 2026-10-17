"""Play one agent against F (or another agent) and write one row of facts per game to a CSV.

    cd ~/catan-agent-hackathon && source .venv/bin/activate
    python ~/Seed-404/report/analysis/collect_games.py --a ~/Seed-404/agents/v02_openings/agent.py \
        --games 300 --out ~/v02_vs_F.csv

Then compare wins with losses on any machine (standard library only):

    python report/analysis/summarise_losses.py v02_vs_F.csv

One core. Uses the organisers' harness (catan_kit.match) and the same boards, seats and dice as
catan_kit.evaluate, so a game here is the game evaluate would play. Default seeds start at 300000:
a range kept apart from tuning (200000+), quick checks (100000) and judging (990000).

Columns: a_* is the agent being studied, b_* its opponent. open_pips is the sum of the dice
probabilities (in 36ths) of the tiles around the first two settlements, open_kinds how many different
resources those tiles give, open_port how many of the two sit on a port. hidden_vp is the victory
points the player held in unplayed cards at the end (actual minus public).
"""
import os
import sys

sys.path.insert(0, os.getcwd())          # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402

COLUMNS = ["game", "board_seed", "a_first", "win", "turns",
           "a_vps", "b_vps", "b_hidden_vp", "a_hidden_vp",
           "a_cities", "a_settlements", "a_roads", "a_dev_bought", "a_knights", "a_longest_road",
           "a_has_army", "a_has_road", "a_robber_moves",
           "b_cities", "b_settlements", "b_roads", "b_dev_bought", "b_knights", "b_longest_road",
           "b_has_army", "b_has_road", "b_robber_moves",
           "a_open_pips", "b_open_pips", "a_open_kinds", "b_open_kinds", "a_open_port", "b_open_port",
           "a_over_budget", "a_random_moves"]


def main():
    ensure_hash_seed()          # may restart this process with PYTHONHASHSEED=0
    import argparse
    import csv

    import catan_kit
    from catan_kit import match
    from catanatron.models.enums import ActionType as AT
    from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

    kit = os.path.dirname(os.path.dirname(os.path.abspath(catan_kit.__file__)))

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--a", required=True, help="the agent being studied")
    p.add_argument("--b", default=os.path.join(kit, "examples", "f_agent.py"), help="opponent (default F)")
    p.add_argument("--games", type=int, default=300)
    p.add_argument("--seed0", type=int, default=300000)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    last = {}
    original_game = match.Game

    class RecordingGame(original_game):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            last["game"] = self

    match.Game = RecordingGame

    def opening(state, color):
        """Pips, resource kinds and port count of the first two settlements of `color`."""
        nodes = [r.action.value for r in state.action_records
                 if r.action.color == color and r.action.action_type == AT.BUILD_SETTLEMENT][:2]
        pips, kinds, ports = 0, set(), 0
        port_nodes = state.board.map.port_nodes
        port_sets = port_nodes.values() if hasattr(port_nodes, "values") else [port_nodes]
        for n in nodes:
            for tile in state.board.map.adjacent_tiles[n]:
                num = getattr(tile, "number", None)
                if num is not None:
                    pips += 6 - abs(7 - num)
                if getattr(tile, "resource", None) is not None:
                    kinds.add(tile.resource)
            ports += any(n in s for s in port_sets)
        return pips, len(kinds), ports

    def side(state, color, prefix):
        i = state.color_to_index[color]
        ps = state.player_state
        kinds = [r.action.action_type for r in state.action_records if r.action.color == color]
        pips, nkinds, ports = opening(state, color)
        return {
            f"{prefix}_vps": ps[f"P{i}_ACTUAL_VICTORY_POINTS"],
            f"{prefix}_hidden_vp": ps[f"P{i}_ACTUAL_VICTORY_POINTS"] - ps[f"P{i}_VICTORY_POINTS"],
            f"{prefix}_cities": kinds.count(AT.BUILD_CITY),
            f"{prefix}_settlements": kinds.count(AT.BUILD_SETTLEMENT),
            f"{prefix}_roads": kinds.count(AT.BUILD_ROAD),
            f"{prefix}_dev_bought": kinds.count(AT.BUY_DEVELOPMENT_CARD),
            f"{prefix}_knights": get_played_dev_cards(state, color, "KNIGHT"),
            f"{prefix}_longest_road": get_longest_road_length(state, color),
            f"{prefix}_has_army": int(bool(ps[f"P{i}_HAS_ARMY"])),
            f"{prefix}_has_road": int(bool(ps[f"P{i}_HAS_ROAD"])),
            f"{prefix}_robber_moves": kinds.count(AT.MOVE_ROBBER),
            f"{prefix}_open_pips": pips,
            f"{prefix}_open_kinds": nkinds,
            f"{prefix}_open_port": ports,
        }

    a_proc, b_proc = match.AgentProcess(os.path.abspath(os.path.expanduser(args.a))), \
        match.AgentProcess(os.path.abspath(os.path.expanduser(args.b)))
    seat_a, seat_b = match.Seat(match.COLORS[0], a_proc), match.Seat(match.COLORS[1], b_proc)
    out = os.path.abspath(os.path.expanduser(args.out))
    try:
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            for gi in range(args.games):
                seed = args.seed0 + gi // 2
                winner, turns = match.play_game(seat_a, seat_b, seed, gi)
                st = last["game"].state
                row = {"game": gi, "board_seed": seed, "a_first": int(gi % 2 == 0),
                       "win": int(winner == seat_a.color), "turns": turns,
                       "a_over_budget": int(seat_a.over is not None),
                       "a_random_moves": seat_a.random_moves}
                row.update(side(st, seat_a.color, "a"))
                row.update(side(st, seat_b.color, "b"))
                w.writerow(row)
                fh.flush()
                if (gi + 1) % 50 == 0:
                    print(f"{gi + 1}/{args.games} games", flush=True)
    finally:
        a_proc.stop()
        b_proc.stop()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
