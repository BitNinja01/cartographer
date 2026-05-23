"""Stat computation for hole-specific PDF stats panel."""
from __future__ import annotations


def calc_fairway_misses(rounds: list[dict], hole_num: int, par: int) -> str:
    if par == 3:
        return "N/A"

    if len(rounds) < 3:
        return "L: \u00b7 R:"

    fairway_left = 0
    fairway_right = 0

    for rnd in rounds:
        holes = rnd.get("holes", {})
        hole_key = str(hole_num)
        if hole_key not in holes:
            continue
        hole_data = holes[hole_key]
        fairway_code = hole_data.get("fairway", "")
        if fairway_code in ["L", "OBL"]:
            fairway_left += 1
        elif fairway_code in ["R", "OBR"]:
            fairway_right += 1

    total_misses = fairway_left + fairway_right
    if total_misses == 0:
        return "L: \u00b7 R:"

    left_pct = round(fairway_left / total_misses * 100)
    right_pct = round(fairway_right / total_misses * 100)

    return f"L {left_pct}% \u00b7 R {right_pct}%"


def calc_gir_misses(rounds: list[dict], hole_num: int) -> str:
    if len(rounds) < 3:
        return "S: \u00b7 LO: \u00b7 L: \u00b7 R:"

    short = 0
    long = 0
    left = 0
    right = 0

    for rnd in rounds:
        holes = rnd.get("holes", {})
        hole_key = str(hole_num)
        if hole_key not in holes:
            continue
        hole_data = holes[hole_key]
        gir_code = hole_data.get("gir", "")
        if gir_code in ["S", "OBS"]:
            short += 1
        elif gir_code in ["LO", "OBLO"]:
            long += 1
        elif gir_code in ["L", "OBL"]:
            left += 1
        elif gir_code in ["R", "OBR"]:
            right += 1

    total_misses = short + long + left + right
    if total_misses == 0:
        return "S: \u00b7 LO: \u00b7 L: \u00b7 R:"

    s_pct = round(short / total_misses * 100)
    lo_pct = round(long / total_misses * 100)
    l_pct = round(left / total_misses * 100)
    r_pct = round(right / total_misses * 100)

    parts = []
    if s_pct > 0:
        parts.append(f"S {s_pct}%")
    if lo_pct > 0:
        parts.append(f"LO {lo_pct}%")
    if l_pct > 0:
        parts.append(f"L {l_pct}%")
    if r_pct > 0:
        parts.append(f"R {r_pct}%")

    return " \u00b7 ".join(parts) if parts else "S: \u00b7 LO: \u00b7 L: \u00b7 R:"


def calc_benchmark(rounds: list[dict], hole_num: int, par: int,
                   handicap_index: float, hole_handicap_index: int) -> str:
    if len(rounds) < 3:
        return "Avg: \u00b7 Exp:"

    scores = []
    for rnd in rounds:
        holes = rnd.get("holes", {})
        hole_key = str(hole_num)
        if hole_key not in holes:
            continue
        hole_data = holes[hole_key]
        score_str = hole_data.get("score", "")
        if score_str:
            try:
                scores.append(int(score_str))
            except ValueError:
                pass

    if not scores:
        return "Avg: \u00b7 Exp:"

    your_avg = sum(scores) / len(scores)
    expected = par + (handicap_index / 18) * hole_handicap_index

    return f"Avg: {your_avg:.1f} \u00b7 Exp: {expected:.1f}"


def calc_penalties(rounds: list[dict], hole_num: int) -> str:
    if len(rounds) < 3:
        return "Avg:"

    penalties = []
    for rnd in rounds:
        holes = rnd.get("holes", {})
        hole_key = str(hole_num)
        if hole_key not in holes:
            continue
        hole_data = holes[hole_key]
        penalty_str = hole_data.get("penalties", "0")
        try:
            penalties.append(int(penalty_str))
        except ValueError:
            penalties.append(0)

    if not penalties:
        return "Avg:"

    avg_penalties = sum(penalties) / len(penalties)
    return f"{avg_penalties:.1f} avg"
