"""Does each opponent actually play differently from F? Count what it builds and plays.

Plays each agent against F with the organisers' harness and prints, per agent, the average per game of
the things that define its style (cities, settlements, roads, development cards bought, knights
played, longest road at the end, victory points, game length in turns).
F against F is the control: an opponent is only a different style if its row differs from F's row by
more than F's own game-to-game noise.

    cd ~/catan-agent-hackathon && source .venv/bin/activate
    python ~/Seed-404/report/analysis/style_check.py --games 30

One core, about a minute. Uses the harness as it is (catan_kit.match); the only addition is to keep
a handle on each finished Game so its action history can be counted.
"""
import os
import sys

sys.path.insert(0, os.getcwd())          # find catan_kit when started from the kit folder

from catan_kit._patch import ensure_hash_seed  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ensure_hash_seed()          # may restart this process with PYTHONHASHSEED=0
    import argparse

    import catan_kit
    from catan_kit import match
    from catanatron.models.enums import ActionType as AT
    from catanatron.state_functions import get_longest_road_length, get_played_dev_cards

    kit = os.path.dirname(os.path.dirname(os.path.abspath(catan_kit.__file__)))
    f_path = os.path.join(kit, "examples", "f_agent.py")

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--games", type=int, default=30)
    p.add_argument("--seed0", type=int, default=100000)
    p.add_argument("--repo", default=REPO, help="the Seed-404 folder (default: the one this file is in)")
    args = p.parse_args()

    agents = [("F (control)", f_path)]
    opp_dir = os.path.join(os.path.expanduser(args.repo), "opponents")
    for name in sorted(os.listdir(opp_dir)):
        if name.endswith(".py") and not name.startswith("_") and name != "run_pool.py":
            agents.append((name[:-3], os.path.join(opp_dir, name)))

    last = {}
    original_game = match.Game

    class RecordingGame(original_game):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            last["game"] = self

    match.Game = RecordingGame

    columns = ["win", "turns", "vps", "cities", "settlements", "roads", "dev_bought",
               "knights", "longest_road"]
    print(f"{'agent (vs F)':<18}" + "".join(f"{c:>13}" for c in columns))
    for name, path in agents:
        a, b = match.AgentProcess(path), match.AgentProcess(f_path)
        seat_a, seat_b = match.Seat(match.COLORS[0], a), match.Seat(match.COLORS[1], b)
        totals = dict.fromkeys(columns, 0.0)
        try:
            for gi in range(args.games):
                winner, turns = match.play_game(seat_a, seat_b, args.seed0 + gi // 2, gi)
                st = last["game"].state
                me = seat_a.color
                kinds = [r.action.action_type for r in st.action_records if r.action.color == me]
                totals["win"] += winner == me
                totals["turns"] += turns
                totals["vps"] += st.player_state[f"P{st.color_to_index[me]}_ACTUAL_VICTORY_POINTS"]
                totals["cities"] += kinds.count(AT.BUILD_CITY)
                totals["settlements"] += kinds.count(AT.BUILD_SETTLEMENT)
                totals["roads"] += kinds.count(AT.BUILD_ROAD)
                totals["dev_bought"] += kinds.count(AT.BUY_DEVELOPMENT_CARD)
                totals["knights"] += get_played_dev_cards(st, me, "KNIGHT")
                totals["longest_road"] += get_longest_road_length(st, me)
        finally:
            a.stop()
            b.stop()
        print(f"{name:<18}" + "".join(f"{totals[c] / args.games:>13.2f}" for c in columns), flush=True)


if __name__ == "__main__":
    main()
