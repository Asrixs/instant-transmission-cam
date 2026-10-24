import numpy as np
import pytest

from itcam.effects import EFFECTS, TeleportEffect, create_effect, next_effect_name, random_for_slot
from itcam.vanish import hide_person

HEIGHT, WIDTH = 72, 128


@pytest.fixture
def scene():
    rng = np.random.default_rng(3)
    background = rng.integers(30, 120, size=(HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame = background.copy()
    frame[10:70, 40:90] = (90, 60, 160)  # de persoon
    mask = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
    mask[8:72, 36:94] = 1.0
    return frame, background, mask


@pytest.mark.parametrize("name", list(EFFECTS))
def test_start_shows_frame_and_end_shows_empty_room(name, scene):
    frame, background, mask = scene
    effect = create_effect(name)
    assert (effect.render(frame, background, mask, 0.0, now=1.0) == frame).all()
    assert (effect.render(frame, background, mask, 1.0, now=1.0) == hide_person(frame, background, mask, 1.0)).all()


@pytest.mark.parametrize("name", list(EFFECTS))
def test_room_outside_mask_stays_untouched(name, scene):
    frame, background, mask = scene
    effect = create_effect(name)
    outside = mask == 0
    for hidden in np.linspace(0.05, 0.95, 19):
        for now in (0.0, 0.31, 1.7):
            output = effect.render(frame, background, mask, float(hidden), now)
            assert output.shape == frame.shape and output.dtype == np.uint8
            assert (output[outside] == frame[outside]).all(), (hidden, now)


def test_teleport_flickers_halfway(scene):
    frame, background, mask = scene
    effect = TeleportEffect()
    person_pixel = []
    for step in range(60):
        output = effect.render(frame, background, mask, 0.5, now=step / 30)
        person_pixel.append(tuple(output[40, 60]))
    # Soms is de persoon er, soms (bijna) weg: er moeten duidelijk verschillende beelden zijn.
    reds = [pixel[2] for pixel in person_pixel]
    assert max(reds) - min(reds) > 60


def test_teleport_flashes_before_vanishing(scene):
    frame, background, mask = scene
    output = TeleportEffect().render(frame, background, mask, 0.7, now=1.0)
    assert output[40, 60].mean() > 220  # fel licht op de plek van de persoon
    assert output[40, 60].mean() > frame[40, 60].mean() + 80


def test_random_for_slot_is_repeatable_and_spread():
    values = [random_for_slot(slot) for slot in range(1000)]
    assert values == [random_for_slot(slot) for slot in range(1000)]
    assert 0.0 <= min(values) and max(values) < 1.0
    assert 0.4 < float(np.mean(values)) < 0.6


def test_effect_names_cycle():
    names = list(EFFECTS)
    assert names[0] == "teleport"
    current = names[0]
    seen = []
    for _ in names:
        seen.append(current)
        current = next_effect_name(current)
    assert sorted(seen) == sorted(names)
    assert current == names[0]
