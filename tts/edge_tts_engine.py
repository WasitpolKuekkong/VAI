from __future__ import annotations

from pathlib import Path
from gtts import gTTS

from typing import Literal

SpeakerName = Literal["normal", "high", "low", "chipmunk", "deep"]


def _parse_speed_multiplier(rate_str: str) -> float:
    rate_str = rate_str.strip().rstrip('%')
    try:
        percent = float(rate_str)
        return 1.0 + (percent / 100.0)
    except ValueError:
        return 1.0


def _pitch_shift(audio, semitones: float):
    """Shift pitch by semitones without changing duration using frame_rate trick."""
    if semitones == 0:
        return audio
    factor = 2.0 ** (semitones / 12.0)
    new_rate = int(audio.frame_rate * factor)
    shifted = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
    return shifted.set_frame_rate(audio.frame_rate)


def _apply_speaker_preset(audio, speaker: SpeakerName):
    from pydub import AudioSegment

    presets = {
        "normal": 0.0,
        "high": 3.0,
        "low": -3.0,
        "chipmunk": 7.0,
        "deep": -6.0,
    }
    semitones = presets.get(speaker, 0.0)
    return _pitch_shift(audio, semitones)


async def synthesize_speech(
    text: str,
    output_path: Path,
    voice: str = "th",
    rate: str = "+0%",
    volume: str = "+0%",
    speaker: SpeakerName = "normal",
    pitch_semitones: float = 0.0,
) -> Path:
    """
    Synthesize speech using Google Text-to-Speech (gTTS) with speed and pitch controls.

    - `speaker` selects a preset timbre (implemented via pitch shift).
    - `pitch_semitones` applies additional pitch shift in semitones.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        tts = gTTS(text=text, lang=voice, slow=False)
        mp3_path = output_path.with_suffix(".mp3")
        tts.save(str(mp3_path))

        # Load and process audio
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(str(mp3_path))

        # Apply speed adjustment
        speed_mult = _parse_speed_multiplier(rate)
        if speed_mult != 1.0:
            audio = audio.speedup(playback_speed=speed_mult)

        # Apply speaker preset pitch
        audio = _apply_speaker_preset(audio, speaker)

        # Apply additional pitch shift if requested
        if pitch_semitones:
            audio = _pitch_shift(audio, pitch_semitones)

        audio.export(str(mp3_path), format="mp3")
        return mp3_path
    except Exception as exc:
        raise RuntimeError(f"TTS synthesis failed with language '{voice}': {exc}") from exc