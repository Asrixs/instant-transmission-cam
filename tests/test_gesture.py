import numpy as np
import pytest

from itcam.gesture import GestureHold, GestureMeasurement, GestureSettings, measure_hand

SETTINGS = GestureSettings()
FOREHEAD = np.array([640.0, 200.0])
EYE_DISTANCE = 100.0

# Basisposities (in meters) van de knokkels; vingers wijzen omhoog (negatieve y).
MCP_X = {"index": -0.02, "middle": 0.0, "ring": 0.02, "pinky": 0.04}
FINGERS = {"thumb": 1, "index": 5, "middle": 9, "ring": 13, "pinky": 17}


def make_hand(extended: set[str], tip_gap_m: float = 0.015) -> np.ndarray:
    """Bouw 21x3 wereldcoördinaten voor een hand met de gegeven gestrekte vingers."""
    world = np.zeros((21, 3), dtype=np.float32)
    world[1:5] = [[-0.03, -0.02 - 0.015 * i, 0.0] for i in range(4)]
    for name, x in MCP_X.items():
        base = FINGERS[name]
        mcp = np.array([x, -0.085, 0.0])
        if name in extended:
            # Gestrekt: kootjes recht in het verlengde, omhoog.
            joints = [mcp, mcp + [0, -0.04, 0], mcp + [0, -0.065, 0], mcp + [0, -0.085, 0]]
        else:
            # Ingevouwen: kootjes krullen terug naar de handpalm.
            joints = [mcp, mcp + [0, -0.03, -0.02], mcp + [0, -0.01, -0.04], mcp + [0, 0.02, -0.03]]
        world[base:base + 4] = joints
    if {"index", "middle"} <= extended:
        world[8, 0] = -tip_gap_m / 2
        world[12, 0] = tip_gap_m / 2
    return world


def hand_px_at(tip_position: np.ndarray) -> np.ndarray:
    hand_px = np.zeros((21, 2), dtype=np.float32)
    hand_px[8] = tip_position + [-5, 0]
    hand_px[12] = tip_position + [5, 0]
    return hand_px


def measure(world, tip_position=FOREHEAD):
    return measure_hand(world, hand_px_at(np.asarray(tip_position, dtype=np.float32)), FOREHEAD, EYE_DISTANCE)


def test_two_fingers_on_forehead_matches():
    assert measure(make_hand({"index", "middle"})).matches(SETTINGS)


def test_hand_away_from_forehead_does_not_match():
    assert not measure(make_hand({"index", "middle"}), FOREHEAD + [0, 300]).matches(SETTINGS)


def test_spread_v_sign_does_not_match():
    assert not measure(make_hand({"index", "middle"}, tip_gap_m=0.06)).matches(SETTINGS)


def test_open_hand_does_not_match():
    assert not measure(make_hand({"index", "middle", "ring", "pinky"})).matches(SETTINGS)


def test_single_finger_does_not_match():
    assert not measure(make_hand({"index"})).matches(SETTINGS)


def test_fist_does_not_match():
    assert not measure(make_hand(set())).matches(SETTINGS)


def test_measurement_is_independent_of_hand_rotation():
    world = make_hand({"index", "middle"})
    angle = np.radians(70)
    rotation = np.array([
        [np.cos(angle), -np.sin(angle), 0],
        [np.sin(angle), np.cos(angle), 0],
        [0, 0, 1],
    ])
    rotated = world @ rotation.T
    assert measure(rotated).matches(SETTINGS)
    assert measure(rotated).index_ratio == pytest.approx(measure(world).index_ratio, rel=1e-4)


class TestGestureHold:
    def test_triggers_once_after_hold_time(self):
        hold = GestureHold(hold_seconds=1.0, grace_seconds=0.25)
        assert not hold.update(True, 0.0).triggered
        assert hold.update(True, 0.5).progress == pytest.approx(0.5)
        assert hold.update(True, 1.0).triggered
        assert not hold.update(True, 1.5).triggered

    def test_short_dropout_keeps_progress(self):
        hold = GestureHold(hold_seconds=1.0, grace_seconds=0.25)
        hold.update(True, 0.0)
        hold.update(True, 0.6)
        assert hold.update(False, 0.7).progress == pytest.approx(0.6)
        assert hold.update(True, 1.0).triggered

    def test_long_dropout_resets(self):
        hold = GestureHold(hold_seconds=1.0, grace_seconds=0.25)
        hold.update(True, 0.0)
        hold.update(True, 0.6)
        assert hold.update(False, 1.0).progress == 0.0
        assert not hold.update(True, 1.1).triggered
        assert not hold.update(True, 1.9).triggered
        assert hold.update(True, 2.1).triggered

    def test_needs_release_before_triggering_again(self):
        hold = GestureHold(hold_seconds=1.0, grace_seconds=0.25)
        hold.update(True, 0.0)
        assert hold.update(True, 1.0).triggered
        assert not hold.update(True, 3.0).triggered
        hold.update(False, 3.5)
        hold.update(True, 4.0)
        assert hold.update(True, 5.0).triggered


def recorded(index, middle, ring, pinky, gap, forehead) -> GestureMeasurement:
    return GestureMeasurement(index, middle, ring, pinky, gap, forehead, np.zeros(2))


# Meetwaarden uit een echte test op Windows (--debug), terwijl het gebaar werd gemaakt.
@pytest.mark.parametrize("values", [
    (1.32, 1.23, 0.88, 0.88, 0.19, 0.09),
    (1.48, 1.40, 1.09, 1.06, 0.17, 0.17),
    (1.31, 1.35, 0.94, 0.91, 0.28, 0.09),
    (1.23, 1.19, 0.84, 0.84, 0.17, 0.07),  # werd eerst gemist: middelvinger net onder 1.2
    (1.41, 1.47, 1.06, 1.07, 0.48, 0.33),  # werd eerst gemist: vingers iets uit elkaar
    (1.32, 1.11, 0.88, 0.83, 0.44, 0.27),  # werd eerst gemist: middelvinger 1.11
])
def test_recorded_gestures_match(values):
    assert recorded(*values).matches(SETTINGS)


# Meetwaarden van dezelfde test terwijl de hand weg bewoog of open was.
@pytest.mark.parametrize("values", [
    (1.13, 1.21, 1.23, 1.25, 0.18, 0.99),
    (1.16, 1.17, 1.23, 1.30, 0.20, 0.73),
    (1.03, 0.99, 1.06, 1.26, 0.21, 2.08),
    (1.34, 0.96, 0.83, 0.85, 0.77, 0.42),  # alleen wijsvinger
])
def test_recorded_non_gestures_do_not_match(values):
    assert not recorded(*values).matches(SETTINGS)


def test_half_curled_hand_does_not_match():
    measurement = recorded(1.12, 1.12, 1.10, 1.08, 0.2, 0.1)
    assert measurement.problems(SETTINGS) == ["hand half gekromd"]


def test_problems_explain_what_is_missing():
    measurement = recorded(1.34, 0.96, 0.83, 0.85, 0.77, 0.42)
    assert measurement.problems(SETTINGS) == ["middelvinger niet gestrekt", "vingers niet tegen elkaar"]


def test_hidden_middle_finger_is_not_reported_as_half_curled():
    # Middelvinger verstopt achter de wijsvinger: alleen die oorzaak noemen.
    measurement = recorded(1.21, 0.85, 0.80, 0.80, 0.51, 0.56)
    assert measurement.problems(SETTINGS) == ["middelvinger niet gestrekt"]
