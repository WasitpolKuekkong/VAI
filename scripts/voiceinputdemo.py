from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import sounddevice as sd
import soundfile as sf
import speech_recognition as sr

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
	sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import load_settings
from utils.logger import logger


def list_input_devices() -> list[tuple[int, str, int]]:
	devices: list[tuple[int, str, int]] = []
	for index, device in enumerate(sd.query_devices()):
		input_channels = int(device.get("max_input_channels", 0))
		if input_channels > 0:
			devices.append((index, str(device.get("name", "Unknown")), input_channels))
	return devices


def resolve_input_device_by_name(device_name: str) -> int | None:
	if not device_name.strip():
		return None
	device_name_lower = device_name.strip().lower()
	for index, name, _ in list_input_devices():
		if device_name_lower in name.lower():
			return index
	return None


def choose_input_device(default_device: int | None) -> int | None:
	devices = list_input_devices()
	if not devices:
		print("No input devices found. Using default input device.")
		return default_device

	print("Available input devices:")
	for index, name, input_channels in devices:
		print(f"{index}: {name} (in: {input_channels})")

	prompt_default = "default" if default_device is None else str(default_device)
	choice = input(f"Select input device index [default={prompt_default}]: ").strip()
	if not choice:
		return default_device
	try:
		selected = int(choice)
		return selected if selected >= 0 else None
	except ValueError:
		print("Invalid input device index, using default device.")
		return default_device


def record_audio(sample_rate: int, channels: int, duration_seconds: float, device: int | None) -> Path:
	frames = int(sample_rate * duration_seconds)
	logger.info(
		"Recording audio: sample_rate=%s channels=%s duration=%.2fs device=%s",
		sample_rate,
		channels,
		duration_seconds,
		device,
	)
	audio = sd.rec(
		frames,
		samplerate=sample_rate,
		channels=channels,
		dtype="float32",
		device=device,
	)
	sd.wait()

	if channels == 1:
		audio_to_save = audio.reshape(-1)
	else:
		audio_to_save = audio

	temp_dir = Path(tempfile.gettempdir())
	wav_path = temp_dir / "voiceinputdemo_recording.wav"
	sf.write(str(wav_path), audio_to_save, sample_rate)
	return wav_path


def transcribe_audio(audio_path: Path, language: str) -> str:
	recognizer = cast(Any, sr.Recognizer())
	with sr.AudioFile(str(audio_path)) as source:
		audio_data = recognizer.record(source)

	try:
		return recognizer.recognize_google(audio_data, language=language)
	except sr.UnknownValueError:
		return "[ไม่สามารถถอดเสียงได้]"
	except sr.RequestError as exc:
		return f"[STT error: {exc}]"


def main() -> None:
	parser = argparse.ArgumentParser(description="Voice input demo: record from mic and transcribe to text")
	parser.add_argument("--seconds", type=float, default=None, help="Recording duration in seconds")
	parser.add_argument("--language", type=str, default=None, help="Recognition language code, e.g. th-TH")
	parser.add_argument("--device", type=int, default=None, help="Input device index (use -1 for default)")
	parser.add_argument("--list-devices", action="store_true", help="List input devices and exit")
	args = parser.parse_args()

	config = load_settings()
	duration_seconds = args.seconds if args.seconds is not None else config.voice_input_duration_seconds
	language = args.language if args.language is not None else config.voice_input_language
	device = args.device if args.device is not None else config.voice_input_device
	if device is not None and device < 0:
		device = None

	if device is None and config.voice_input_device_name:
		device = resolve_input_device_by_name(config.voice_input_device_name)

	if args.list_devices:
		for index, name, input_channels in list_input_devices():
			print(f"{index}: {name} (in: {input_channels})")
		return

	if device is None and config.voice_input_device is None:
		device = choose_input_device(default_device=None)

	if device is None and config.voice_input_device_name:
		print(f"Warning: could not find input device matching '{config.voice_input_device_name}', using default device.")

	print("Press Enter to start recording...")
	input()
	print(f"Recording for {duration_seconds:.1f} seconds. Speak now...")
	wav_path = record_audio(
		sample_rate=config.voice_input_sample_rate,
		channels=config.voice_input_channels,
		duration_seconds=duration_seconds,
		device=device,
	)
	print("Transcribing...")
	text = transcribe_audio(wav_path, language=language)
	print(f"Result: {text}")


if __name__ == "__main__":
	main()
