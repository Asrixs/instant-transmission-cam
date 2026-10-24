import numpy as np
import pytest

from itcam.gesture import GestureHold, GestureSettings, measure_hand

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
