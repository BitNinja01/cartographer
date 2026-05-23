import pytest
from cartographer.stats import (
    calc_fairway_misses, calc_gir_misses, calc_benchmark, calc_penalties,
)


# --- calc_fairway_misses ---

def test_fairway_misses_par_3(make_round):
    rounds = [make_round() for _ in range(3)]
    assert calc_fairway_misses(rounds, 4, 3) == "N/A"


def test_fairway_misses_few_rounds(make_round):
    rounds = [make_round() for _ in range(2)]
    assert calc_fairway_misses(rounds, 1, 4) == "L: \u00b7 R:"


def test_fairway_misses_empty_rounds(make_round):
    assert calc_fairway_misses([], 1, 4) == "L: \u00b7 R:"


def test_fairway_misses_all_hits(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        rnd["holes"]["1"]["fairway"] = "H"
    assert calc_fairway_misses(rounds, 1, 4) == "L: \u00b7 R:"


def test_fairway_misses_mixed(make_round):
    rounds = [make_round() for _ in range(5)]
    for i, rnd in enumerate(rounds):
        rnd["holes"]["1"]["fairway"] = "L" if i < 3 else "R"
    assert calc_fairway_misses(rounds, 1, 4) == "L 60% · R 40%"


def test_fairway_misses_missing_hole_key(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        del rnd["holes"]["1"]
    assert calc_fairway_misses(rounds, 1, 4) == "L: \u00b7 R:"


# --- calc_gir_misses ---

def test_gir_misses_few_rounds(make_round):
    rounds = [make_round() for _ in range(2)]
    assert calc_gir_misses(rounds, 1) == "S: \u00b7 LO: \u00b7 L: \u00b7 R:"


def test_gir_misses_empty_rounds(make_round):
    assert calc_gir_misses([], 1) == "S: \u00b7 LO: \u00b7 L: \u00b7 R:"


def test_gir_misses_all_hits(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        rnd["holes"]["1"]["gir"] = "H"
    assert calc_gir_misses(rounds, 1) == "S: \u00b7 LO: \u00b7 L: \u00b7 R:"


def test_gir_misses_mixed(make_round):
    rounds = [make_round() for _ in range(4)]
    for rnd, code in zip(rounds, ["S", "S", "LO", "L"]):
        rnd["holes"]["1"]["gir"] = code
    assert calc_gir_misses(rounds, 1) == "S 50% · LO 25% · L 25%"


def test_gir_misses_missing_hole_key(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        del rnd["holes"]["1"]
    assert calc_gir_misses(rounds, 1) == "S: \u00b7 LO: \u00b7 L: \u00b7 R:"


# --- calc_benchmark ---

def test_benchmark_few_rounds(make_round):
    rounds = [make_round() for _ in range(2)]
    assert calc_benchmark(rounds, 1, 4, 15.0, 10) == "Avg: \u00b7 Exp:"


def test_benchmark_empty_rounds(make_round):
    assert calc_benchmark([], 1, 4, 15.0, 10) == "Avg: \u00b7 Exp:"


def test_benchmark_normal(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        rnd["holes"]["1"]["score"] = "4"
    rounds[0]["holes"]["1"]["score"] = "5"
    assert calc_benchmark(rounds, 1, 4, 5.0, 3) == "Avg: 4.3 · Exp: 4.8"


def test_benchmark_missing_score_field(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        rnd["holes"]["1"].pop("score", None)
    assert calc_benchmark(rounds, 1, 4, 15.0, 10) == "Avg: \u00b7 Exp:"


def test_benchmark_empty_score(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        rnd["holes"]["1"]["score"] = ""
    assert calc_benchmark(rounds, 1, 4, 15.0, 10) == "Avg: \u00b7 Exp:"


# --- calc_penalties ---

def test_penalties_few_rounds(make_round):
    rounds = [make_round() for _ in range(2)]
    assert calc_penalties(rounds, 1) == "Avg:"


def test_penalties_empty_rounds(make_round):
    assert calc_penalties([], 1) == "Avg:"


def test_penalties_normal(make_round):
    rounds = [
        make_round(penalties=1),
        make_round(penalties=0),
        make_round(penalties=0),
    ]
    assert calc_penalties(rounds, 1) == "0.3 avg"


def test_penalties_no_penalties(make_round):
    rounds = [make_round(penalties=0) for _ in range(3)]
    assert calc_penalties(rounds, 1) == "0.0 avg"


def test_penalties_missing_field(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        del rnd["holes"]["1"]["penalties"]
    assert calc_penalties(rounds, 1) == "0.0 avg"


def test_penalties_missing_hole_key(make_round):
    rounds = [make_round() for _ in range(3)]
    for rnd in rounds:
        del rnd["holes"]["1"]
    assert calc_penalties(rounds, 1) == "Avg:"
