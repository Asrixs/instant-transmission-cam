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


def smooth_room(height=90, width=160) -> np.ndarray:
    """Een kamer met zachte overgangen (muur, kast), zoals een echte achtergrond."""
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    base = 120 + 60 * np.sin(x / 25) * np.cos(y / 30)
    return np.clip(np.stack([base, base * 0.95, base * 1.05], axis=2), 0, 255).astype(np.uint8)


class TestBrightnessMatcher:
    def test_follows_camera_exposure(self):
        background = smooth_room()
        frame = np.clip(background.astype(np.float32) * 1.2, 0, 255).astype(np.uint8)
        no_person = np.zeros(background.shape[:2], dtype=np.float32)
        matcher = BrightnessMatcher()
        for _ in range(30):
            matcher.update(frame, background, no_person)
        corrected = matcher.apply(background).astype(int)
        assert np.abs(corrected - frame.astype(int)).mean() < 3

    def test_fills_in_the_person_area_from_the_surroundings(self):
        # De foto is te licht (camera was nog niet ingesteld); op jouw plek mag dat niet te zien zijn.
        room_now = smooth_room()
        photo = np.clip(room_now.astype(np.float32) * 1.25, 0, 255).astype(np.uint8)
        frame = room_now.copy()
        frame[20:90, 60:100] = (60, 40, 30)  # jij, in een donker shirt
        mask = np.zeros(frame.shape[:2], dtype=np.float32)
        mask[18:90, 56:104] = 1.0
        matcher = BrightnessMatcher()
        for _ in range(30):
            matcher.update(frame, photo, mask)
        corrected = matcher.apply(photo).astype(int)
        person_area = mask > 0
        error_before = np.abs(photo.astype(int) - room_now.astype(int))[person_area].mean()
        error_after = np.abs(corrected - room_now.astype(int))[person_area].mean()
        assert error_before > 20
        assert error_after < 4

    def test_handles_different_correction_for_dark_and_light_parts(self):
        # Webcams belichten donker en licht niet even sterk bij: links (donker) +40%, rechts (licht) -10%.
        background = smooth_room()
        frame = background.astype(np.float32)
        frame[:, :80] *= 1.4
        frame[:, 80:] *= 0.9
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        no_person = np.zeros(background.shape[:2], dtype=np.float32)
        matcher = BrightnessMatcher()
        for _ in range(30):
            matcher.update(frame, background, no_person)
        corrected = matcher.apply(background).astype(int)
        assert np.abs(corrected[:, :60] - frame[:, :60].astype(int)).mean() < 5
        assert np.abs(corrected[:, 100:] - frame[:, 100:].astype(int)).mean() < 5

    def test_ignores_overexposed_pixels(self):
        background = smooth_room()
        frame = background.copy()
        frame[:, :20] = 255  # uitgebrand stuk: zegt niets over de belichting
        no_person = np.zeros(background.shape[:2], dtype=np.float32)
        matcher = BrightnessMatcher()
        matcher.update(frame, background, no_person)
        assert np.abs(matcher.gain[:, 60:] - 1.0).max() < 0.05

    def test_without_measurement_leaves_background_alone(self):
        background = smooth_room()
        assert BrightnessMatcher().apply(background) is background


class TestBackgroundCapture:
    def test_waits_for_countdown(self):
        capture = BackgroundCapture(countdown_seconds=4.0, frames_needed=3)
        capture.start(0.0)
        assert capture.status(1.2).phase == "countdown"
        assert capture.status(1.2).seconds_left == pytest.approx(2.8)
        assert not capture.needs_check(3.9)
        assert capture.update(room(), 0.0, 3.9) is None

    def test_waits_until_person_has_left(self):
        capture = BackgroundCapture(countdown_seconds=1.0, frames_needed=2, settle_seconds=0.0)
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
        capture = BackgroundCapture(countdown_seconds=1.0, frames_needed=2, max_wait_seconds=10.0, settle_seconds=0.0)
        capture.start(0.0)
        background = room()
        assert capture.update(background, 0.05, 5.0) is None
        assert capture.status(5.0).phase == "waiting"
        assert capture.update(background, 0.05, 11.1) is None
        assert capture.update(background, 0.05, 11.2) is not None

    def test_waits_for_camera_to_settle_after_you_left(self):
        capture = BackgroundCapture(countdown_seconds=1.0, frames_needed=2, settle_seconds=1.5)
        capture.start(0.0)
        background = room()
        assert capture.update(with_person(background), 0.3, 1.1) is None
        assert capture.update(background, 0.0, 2.0) is None  # net weg: camera past zich nog aan
        assert capture.status(2.5).phase == "settling"
        assert capture.update(background, 0.0, 3.0) is None
        assert capture.update(background, 0.0, 3.6) is None  # 1.6 s later: eerste beeld telt
        assert capture.status(3.6).phase == "sampling"
        assert capture.update(background, 0.0, 3.7) is not None

    def test_coming_back_restarts_the_settle_time(self):
        capture = BackgroundCapture(countdown_seconds=0.0, frames_needed=1, settle_seconds=1.0)
        capture.start(0.0)
        background = room()
        capture.update(background, 0.0, 0.1)
        capture.update(with_person(background), 0.3, 0.8)  # toch nog even in beeld
        assert capture.update(background, 0.0, 1.0) is None
        assert capture.update(background, 0.0, 1.5) is None
        assert capture.update(background, 0.0, 2.1) is not None

    def test_median_removes_flicker(self):
        capture = BackgroundCapture(countdown_seconds=0.0, frames_needed=3, settle_seconds=0.0)
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
