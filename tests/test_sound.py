import sys
import types
import wave

import numpy as np
import pytest

from itcam.sound import FLASH_AT, SAMPLE_RATE, SoundPlayer, load_wav, save_wav, teleport_sound


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
    loaded, rate = load_wav(path)
    assert rate == SAMPLE_RATE
    assert np.abs(loaded - sound).max() < 1e-3


def test_stereo_wav_becomes_mono(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(np.array([16384, -16384] * 100, dtype=np.int16).tobytes())
    loaded, rate = load_wav(path)
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


def test_custom_wav_plays_forward_both_times(monkeypatch, tmp_path):
    device = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", device)
    path = tmp_path / "eigen.wav"
    save_wav(path, teleport_sound(0.2), 22050)
    player = SoundPlayer(0.8, volume=1.0, path=path)
    player.play_vanish()
    player.play_appear()
    assert device.played[0][1] == 22050
    assert (device.played[0][0] == device.played[1][0]).all()


def test_unreadable_custom_wav_gives_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="Kan het geluidsbestand"):
        SoundPlayer(0.8, volume=1.0, path=tmp_path / "bestaat-niet.wav")
