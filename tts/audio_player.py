"""Audio player for streaming output to VB-Audio Cable or default speaker."""
from __future__ import annotations

import soundfile as sf
import sounddevice as sd
import numpy as np
from pathlib import Path
from pydub import AudioSegment
import tempfile
import winsound
from utils.logger import logger


def play_audio(file_path: Path, device_id: int | None = None, blocking: bool = True) -> bool:
    """
    Play an audio file to specified device (or default).

    Args:
        file_path: Path to audio file (wav, mp3, flac, etc.)
        device_id: Audio device ID (None = default). Use 10 for VB-Audio CABLE Input.
        blocking: If True, wait for playback to finish; if False, start and return immediately.

    Returns:
        True if successful, False otherwise.
    """
    try:
        if not file_path.exists():
            logger.error(f"Audio file not found: {file_path}")
            return False

        # If WAV, read directly using soundfile
        if file_path.suffix.lower() == ".wav":
            try:
                logger.info(f"Playing WAV file: {file_path}")
                audio, sr = sf.read(str(file_path))
                
                # Ensure stereo (duplicate mono if needed for VB-Audio compatibility)
                if len(audio.shape) == 1:
                    # Mono to stereo: duplicate the channel
                    audio = np.column_stack((audio, audio))
                    logger.info(f"Converted mono to stereo for playback")
                
                if device_id is not None:
                    logger.info(f"Playing on device {device_id}")
                    sd.play(audio, sr, device=device_id, blocking=blocking)
                else:
                    logger.info(f"Playing on default device")
                    sd.play(audio, sr, blocking=blocking)
                if blocking:
                    sd.wait()
                return True
            except Exception as exc:
                logger.error(f"Failed to play WAV: {exc}")
                return False

        # If MP3, try pydub first
        if file_path.suffix.lower() == ".mp3":
            try:
                logger.info(f"Converting MP3 to WAV for playback: {file_path}")
                audio_segment = AudioSegment.from_mp3(str(file_path))
                # Export to temporary WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_wav = tmp.name
                audio_segment.export(tmp_wav, format="wav")
                # Read temporary WAV for playback
                audio, sr = sf.read(tmp_wav)
                Path(tmp_wav).unlink()  # Clean up temp file
                
                # Ensure stereo (duplicate mono if needed for VB-Audio compatibility)
                if len(audio.shape) == 1:
                    audio = np.column_stack((audio, audio))
                    logger.info(f"Converted mono to stereo for playback")
                
                if device_id is not None:
                    logger.info(f"Playing on device {device_id}")
                    sd.play(audio, sr, device=device_id, blocking=blocking)
                else:
                    logger.info(f"Playing on default device")
                    sd.play(audio, sr, blocking=blocking)
                if blocking:
                    sd.wait()
                return True
            except Exception as exc:
                logger.warning(f"pydub conversion failed: {exc} - trying winsound fallback")
                # Fallback: try winsound (Windows built-in, no conversion)
                try:
                    logger.info(f"Playing MP3 via winsound (no conversion): {file_path}")
                    winsound.PlaySound(str(file_path), winsound.SND_FILENAME)
                    return True
                except Exception as ws_exc:
                    logger.error(f"winsound playback also failed: {ws_exc}")
                    return False

        # Other formats: try soundfile directly
        try:
            logger.info(f"Playing audio file: {file_path}")
            audio, sr = sf.read(str(file_path))
            
            # Ensure stereo (duplicate mono if needed for VB-Audio compatibility)
            if len(audio.shape) == 1:
                audio = np.column_stack((audio, audio))
                logger.info(f"Converted mono to stereo for playback")
            
            if device_id is not None:
                logger.info(f"Playing on device {device_id}")
                sd.play(audio, sr, device=device_id, blocking=blocking)
            else:
                logger.info(f"Playing on default device")
                sd.play(audio, sr, blocking=blocking)
            if blocking:
                sd.wait()
            return True
        except Exception as exc:
            logger.error(f"Failed to play audio file: {exc}")
            return False

    except Exception as exc:
        logger.error(f"Audio playback failed: {exc}")
        return False


def get_available_devices() -> dict:
    """
    Get list of audio devices with names and IDs.

    Returns:
        Dict with device_id: device_name pairs.
    """
    devices = {}
    try:
        for i, device in enumerate(sd.query_devices()):
            # Focus on output devices (max_output_channels > 0)
            if device["max_output_channels"] > 0:
                devices[i] = device["name"]
    except Exception as exc:
        logger.error(f"Failed to query audio devices: {exc}")
    return devices


def find_vb_audio_device() -> int | None:
    """
    Try to find VB-Audio CABLE Input device automatically.

    Returns:
        Device ID if found, None otherwise.
    """
    devices = get_available_devices()
    # Look for CABLE Input device (common VB-Audio name)
    for dev_id, dev_name in devices.items():
        if "CABLE Input" in dev_name and "VB-Audio" in dev_name:
            logger.info(f"Found VB-Audio device: {dev_id} ({dev_name})")
            return dev_id
    # Fallback: look for any CABLE device
    for dev_id, dev_name in devices.items():
        if "CABLE" in dev_name:
            logger.info(f"Found CABLE device: {dev_id} ({dev_name})")
            return dev_id
    return None
