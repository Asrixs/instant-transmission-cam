import numpy as np
import pytest

from itcam.vanish import (
    BackgroundCapture,
    BrightnessMatcher,
    Visibility,
    difference_mask,
    hide_person,
    person_fraction,
    prepare_mask,
)

RNG = np.random.default_rng(1)


def room(height=90, width=160) -> np.ndarray:
    """Een 'lege kamer' met wat structuur."""
    return RNG.integers(40, 200, size=(height, width, 3), dtype=np.uint8)


def with_person(background: np.ndarray, color=(230, 230, 230)) -> np.ndarray:
    frame = background.copy()
    frame[20:80, 60:100] = color
    noise = RNG.integers(-4, 5, size=frame.shape)
    return np.clip(frame.astype(int) + noise, 0, 255).astype(np.uint8)


class TestMasks:
    def test_difference_mask_finds_person_and_ignores_noise(self):
        background = room()
        mask = difference_mask(with_person(background), background)
        assert mask[50, 80] == pytest.approx(1.0)
        assert mask[5, 5] == 0.0
        assert mask[85, 150] == 0.0

    def test_prepare_mask_grows_and_scales_to_output(self):
        confidence = np.zeros((90, 160), dtype=np.float32)
        confidence[20:80, 60:100] = 1.0
        mask = prepare_mask(confidence, (320, 180))
        assert mask.shape == (180, 320)
        assert mask[100, 160] == pytest.approx(1.0)
        assert mask[100, 118] > 0.5  # net buiten de persoon: randen vallen ook weg
        assert mask[10, 10] == 0.0

    def test_prepare_mask_includes_difference(self):
        confidence = np.zeros((90, 160), dtype=np.float32)
        difference = np.zeros((90, 160), dtype=np.float32)
        difference[30:60, 20:40] = 1.0  # bijvoorbeeld een witte trui tegen een witte muur
        mask = prepare_mask(confidence, (160, 90), difference)
        assert mask[45, 30] == pytest.approx(1.0)

    def test_person_fraction(self):
        confidence = np.zeros((10, 10), dtype=np.float32)
        confidence[:5, :2] = 0.9
        assert person_fraction(confidence) == pytest.approx(0.1)


class TestHidePerson:
    def setup_method(self):
        self.frame = np.full((4, 4, 3), 200, dtype=np.uint8)
        self.background = np.full((4, 4, 3), 50, dtype=np.uint8)
        self.mask = np.zeros((4, 4), dtype=np.float32)
        self.mask[:, :2] = 1.0

    def test_visible_returns_frame(self):
        assert hide_person(self.frame, self.background, self.mask, 0.0) is self.frame

    def test_fully_hidden_shows_background_only_where_person_is(self):
        output = hide_person(self.frame, self.background, self.mask, 1.0)
        assert (output[:, :2] == 50).all()
        assert (output[:, 2:] == 200).all()

    def test_halfway_blends(self):
        output = hide_person(self.frame, self.background, self.mask, 0.5)
        assert output[0, 0, 0] == pytest.approx(125, abs=2)


def test_brightness_matcher_follows_camera_exposure():
    background = room()
    frame = np.clip(background.astype(np.float32) * 1.2, 0, 255).astype(np.uint8)
    no_person = np.zeros(background.shape[:2], dtype=np.float32)
    matcher = BrightnessMatcher()
    for _ in range(60):
        matcher.update(frame, background, no_person)
    assert matcher.gain == pytest.approx([1.2, 1.2, 1.2], abs=0.03)
    corrected = matcher.apply(background).astype(int)
    assert np.abs(corrected - frame.astype(int)).mean() < 4


class TestBackgroundCapture:
    def test_waits_for_countdown(self):
        capture = BackgroundCapture(countdown_seconds=4.0, frames_needed=3)
        capture.start(0.0)
        assert capture.status(1.2).phase == "countdown"
        assert capture.status(1.2).seconds_left == pytest.approx(2.8)
        assert not capture.needs_check(3.9)
        assert capture.update(room(), 0.0, 3.9) is None

    def test_waits_until_person_has_left(self):
        capture = BackgroundCapture(countdown_seconds=1.0, frames_needed=2)
        capture.start(0.0)
        background = room()
        assert capture.update(background, 0.0, 1.1) is None
        assert capture.update(with_person(background), 0.3, 1.2) is None
        assert capture.status(1.2).phase == "waiting"
        # De beelden van vóór het in beeld komen tellen niet meer mee.
        assert capture.update(background, 0.0, 1.3) is None
        assert capture.status(1.3).phase == "sampling"
        assert capture.update(background, 0.0, 1.4) is not None
        assert not capture.active

    def test_gives_up_waiting_after_a_while(self):
        # Bijvoorbeeld een poster met een persoon erop: niet eindeloos blijven wachten.
        capture = BackgroundCapture(countdown_seconds=1.0, frames_needed=2, max_wait_seconds=10.0)
        capture.start(0.0)
        background = room()
        assert capture.update(background, 0.05, 5.0) is None
        assert capture.status(5.0).phase == "waiting"
        assert capture.update(background, 0.05, 11.1) is None
        assert capture.update(background, 0.05, 11.2) is not None

    def test_median_removes_flicker(self):
        capture = BackgroundCapture(countdown_seconds=0.0, frames_needed=3)
        capture.start(0.0)
        background = room()
        flicker = np.full_like(background, 255)
        capture.update(background, 0.0, 0.1)
        capture.update(flicker, 0.0, 0.2)
        result = capture.update(background, 0.0, 0.3)
        assert (result == background).all()


class TestVisibility:
    def test_starts_visible(self):
        visibility = Visibility(transition_seconds=0.5)
        assert visibility.update(0.0) == 0.0

    def test_vanishes_smoothly_and_comes_back(self):
        visibility = Visibility(transition_seconds=0.5)
        visibility.update(0.0)
        visibility.toggle()
        assert visibility.update(0.25) == pytest.approx(0.5)
        assert visibility.update(0.5) == pytest.approx(1.0)
        assert visibility.update(2.0) == pytest.approx(1.0)
        visibility.toggle()
        assert visibility.update(2.5) == pytest.approx(0.0)

    def test_show_now_is_instant(self):
        visibility = Visibility(transition_seconds=0.5)
        visibility.update(0.0)
        visibility.toggle()
        visibility.update(1.0)
        visibility.show_now()
        assert visibility.update(1.01) == 0.0
