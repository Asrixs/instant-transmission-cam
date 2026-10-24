import sys
import types
import wave

import numpy as np
import pytest
import soundfile

import itcam.sound
from itcam.sound import (
    FLASH_AT,
    SAMPLE_RATE,
    SoundPlayer,
    align_peak,
    find_custom_sound,
    load_sound,
    peak_time,
    prepare_custom_sound,
    save_wav,
    teleport_sound,
    trim_silence,
)


@pytest.fixture(autouse=True)
def no_local_sounds(monkeypatch, tmp_path):
    """Tests mogen niet afhangen van een eigen geluid in de map sounds/."""
    monkeypatch.setattr(itcam.sound, "SOUNDS_DIR", tmp_path / "geen-sounds")


def bang(rate=22050, silence=0.3, length=0.5, peak_at=0.2) -> np.ndarray:
    """Testgeluid: stilte, dan een zachte toon met een harde klap op peak_at."""
    t = np.arange(int(length * rate)) / rate
    tone = 0.2 * np.sin(2 * np.pi * 440 * t)
    tone[int(peak_at * rate):int((peak_at + 0.03) * rate)] *= 4.5
    pad = np.zeros(int(silence * rate))
    return np.concatenate([pad, tone, pad]).astype(np.float32)


def test_teleport_sound_matches_transition():
    sound = teleport_sound(0.8)
    assert sound.dtype == np.float32
    assert len(sound) == int(0.8 * SAMPLE_RATE)
    assert np.abs(sound).max() <= 1.0
    # De klap valt samen met de flits in het beeld.
    loudest = np.abs(sound).argmax() / SAMPLE_RATE
    assert loudest == pytest.approx(FLASH_AT * 0.8, abs=0.02)
    # Zacht begin en einde, geen klik.
    assert abs(sound[0]) < 0.01 and abs(sound[-1]) < 0.01


def test_teleport_sound_builds_up_before_the_flash():
    sound = np.abs(teleport_sound(1.0))
    quiet_start = sound[: SAMPLE_RATE // 10].max()
    just_before_flash = sound[int(0.5 * SAMPLE_RATE): int(0.6 * SAMPLE_RATE)].max()
    assert just_before_flash > 5 * quiet_start


def test_wav_round_trip(tmp_path):
    path = tmp_path / "test.wav"
    sound = teleport_sound(0.3)
    save_wav(path, sound)
    loaded, rate = load_sound(path)
    assert rate == SAMPLE_RATE
    assert np.abs(loaded - sound).max() < 1e-3


def test_mp3_can_be_loaded(tmp_path):
    path = tmp_path / "teleport.mp3"
    soundfile.write(str(path), bang(rate=44100), 44100, format="MP3")
    loaded, rate = load_sound(path)
    assert rate == 44100
    assert np.abs(loaded).max() > 0.5


def test_stereo_wav_becomes_mono(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(np.array([16384, -16384] * 100, dtype=np.int16).tobytes())
    loaded, rate = load_sound(path)
    assert rate == 22050
    assert len(loaded) == 100
    assert np.allclose(loaded, 0.0)


class FakeSoundDevice(types.ModuleType):
    def __init__(self, fail=False):
        super().__init__("sounddevice")
        self.fail = fail
        self.played = []

    def check_output_settings(self, **kwargs):
        if self.fail:
            raise OSError("PortAudio library not found")

    def play(self, data, rate):
        self.played.append((data, rate))


def test_player_plays_vanish_and_reversed_appear(monkeypatch):
    device = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", device)
    player = SoundPlayer(0.8, volume=0.5)
    player.play_vanish()
    player.play_appear()
    (vanish, rate), (appear, _) = device.played
    assert rate == SAMPLE_RATE
    assert np.abs(vanish).max() == pytest.approx(0.45, abs=0.01)
    assert (appear == vanish[::-1]).all()


def test_player_can_be_muted(monkeypatch):
    device = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", device)
    player = SoundPlayer(0.8, volume=0.8)
    assert player.toggle() is False
    player.play_vanish()
    assert device.played == []
    assert player.toggle() is True


def test_player_without_audio_keeps_working(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "sounddevice", FakeSoundDevice(fail=True))
    player = SoundPlayer(0.8, volume=0.8)
    assert not player.enabled
    player.play_vanish()  # geen fout
    assert "Geen geluid mogelijk" in capsys.readouterr().out


def test_trim_silence_removes_quiet_edges():
    sound = bang(silence=0.3, length=0.5)
    trimmed = trim_silence(sound)
    assert len(trimmed) == pytest.approx(0.5 * 22050, abs=50)
    assert trim_silence(np.zeros(100, dtype=np.float32)).size == 100


def test_peak_time_finds_the_bang():
    assert peak_time(bang(silence=0.0, peak_at=0.2), 22050) == pytest.approx(0.215, abs=0.02)


def test_align_peak_delays_sound_until_the_flash():
    sound = bang(silence=0.0, peak_at=0.1)
    aligned = align_peak(sound, 22050, at_seconds=0.5)
    assert peak_time(aligned, 22050) == pytest.approx(0.5, abs=0.02)
    # Valt de klap al later dan de flits, dan begint het geluid gewoon meteen.
    assert align_peak(sound, 22050, at_seconds=0.0) is sound


def test_custom_sound_bang_lands_on_the_flash_both_ways():
    vanish, appear = prepare_custom_sound(bang(peak_at=0.1), 22050, transition_seconds=0.8)
    assert peak_time(vanish, 22050) == pytest.approx(FLASH_AT * 0.8, abs=0.02)
    assert peak_time(appear, 22050) == pytest.approx((1 - FLASH_AT) * 0.8, abs=0.02)
    assert np.abs(vanish).max() == pytest.approx(0.9, abs=0.01)


def test_find_custom_sound(tmp_path):
    assert find_custom_sound(tmp_path) is None
    (tmp_path / "teleport.wav").write_bytes(b"")
    assert find_custom_sound(tmp_path) == tmp_path / "teleport.wav"
    (tmp_path / "teleport.mp3").write_bytes(b"")
    assert find_custom_sound(tmp_path) == tmp_path / "teleport.mp3"  # MP3 heeft voorrang


def test_sound_in_sounds_folder_is_used_automatically(monkeypatch, tmp_path):
    device = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", device)
    monkeypatch.setattr(itcam.sound, "SOUNDS_DIR", tmp_path)
    soundfile.write(str(tmp_path / "teleport.mp3"), bang(rate=44100), 44100, format="MP3")
    player = SoundPlayer(0.8, volume=1.0)
    assert player.description == "eigen geluid teleport.mp3"
    player.play_vanish()
    player.play_appear()
    (vanish, rate), (appear, _) = device.played
    assert rate == 44100
    assert peak_time(vanish, rate) > peak_time(appear, rate)  # beide op de flits, niet achterstevoren


def test_builtin_sound_is_used_without_custom_file(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", FakeSoundDevice())
    assert SoundPlayer(0.8, volume=1.0).description == "ingebouwd teleportgeluid"


def test_unreadable_custom_wav_gives_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="Kan het geluidsbestand"):
        SoundPlayer(0.8, volume=1.0, path=tmp_path / "bestaat-niet.wav")
