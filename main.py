from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import requests

from config.settings import AppConfig, load_personality, load_settings
from rvc.applio_stub import process_with_rvc
from tts.edge_tts_engine import synthesize_speech
from tts.edge_tts_engine import SpeakerName
from tts.audio_player import play_audio, find_vb_audio_device
from typing import cast
from utils.history import load_history, save_history
from utils.cleanup import cleanup_old_files
from utils.logger import logger
import time


def build_messages(system_prompt: str, history: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
	messages = [{"role": "system", "content": system_prompt}]
	messages.extend(history)
	messages.append({"role": "user", "content": user_text})
	return messages


def chat_with_lm_studio(config: AppConfig, messages: list[dict[str, str]]) -> str:
	url = f"{config.lm_studio_base_url.rstrip('/')}/v1/chat/completions"
	payload = {
		"model": config.model_name,
		"messages": messages,
		"temperature": config.temperature,
		"max_tokens": config.max_tokens,
		"stream": False,
	}
	response = requests.post(url, json=payload, timeout=config.request_timeout)
	response.raise_for_status()
	data = response.json()
	return data["choices"][0]["message"]["content"].strip()


def ensure_output_dirs(config: AppConfig) -> None:
	config.tts_output_dir.mkdir(parents=True, exist_ok=True)
	config.rvc_output_dir.mkdir(parents=True, exist_ok=True)
	config.history_file.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
	config = load_settings()
	ensure_output_dirs(config)

	personality = load_personality(config.personality_path)
	history = load_history(config.history_file)

	print("AIVT ready")
	print(f"LM Studio: {config.lm_studio_base_url}")
	print(f"Model: {config.model_name}")
	print(f"Loaded {len(history)} messages from history")
	print("Type 'exit' to quit.\n")

	current_speaker = cast(SpeakerName, config.tts_default_speaker)
	current_pitch = config.tts_default_pitch_semitones

	print(f"Current speaker: {current_speaker}, pitch offset: {current_pitch} semitones")

	while True:
		user_text = input("You: ").strip()
		if not user_text:
			continue
		if user_text.lower() in {"exit", "quit"}:
			break

		# Simple commands to change speaker/pitch at runtime
		if user_text.startswith("/speaker "):
			_, sp = user_text.split(maxsplit=1)
			current_speaker = cast(SpeakerName, sp.strip())
			print(f"Speaker set to: {current_speaker}")
			continue

		if user_text.startswith("/pitch "):
			try:
				_, val = user_text.split(maxsplit=1)
				current_pitch = float(val)
				print(f"Pitch offset set to: {current_pitch} semitones")
			except Exception:
				print("Usage: /pitch <semitones>  (e.g. /pitch 2 or /pitch -1)")
			continue

		if user_text.strip() == "/speakers":
			print("Available speakers: normal, high, low, chipmunk, deep")
			continue

		turn_start = time.perf_counter()
		try:
			lm_start = time.perf_counter()
			messages = build_messages(personality, history, user_text)
			assistant_text = chat_with_lm_studio(config, messages)
			lm_time = time.perf_counter() - lm_start
			logger.info(f"LM response time: {lm_time:.3f}s")
		except requests.RequestException as exc:
			logger.error(f"LM Studio error: {exc}")
			continue

		print(f"AI: {assistant_text}\n")
		history.append({"role": "user", "content": user_text})
		history.append({"role": "assistant", "content": assistant_text})
		history = history[-config.max_history_messages :]
		save_history(history, config.history_file)

		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		tts_path = config.tts_output_dir / f"reply_{timestamp}.{config.tts_output_format}"

		try:
			tts_start = time.perf_counter()
			asyncio.run(
				synthesize_speech(
					text=assistant_text,
					output_path=tts_path,
					voice=config.tts_voice,
					rate=config.tts_rate,
					volume=config.tts_volume,
					speaker=current_speaker,
					pitch_semitones=current_pitch,
				)
			)
			tts_time = time.perf_counter() - tts_start
			logger.info(f"TTS synthesis time: {tts_time:.3f}s -> {tts_path.name}")
			print(f"TTS saved: {tts_path}")
			cleanup_old_files(config.tts_output_dir, max_files=5)
		except Exception as exc:  # pragma: no cover - runtime integration safety
			logger.error(f"TTS error: {exc}")
			continue

		# Run Applio / RVC processing and log time
		rvc_start = time.perf_counter()
		rvc_ready_path = process_with_rvc(tts_path, config)
		rvc_time = time.perf_counter() - rvc_start
		logger.info(f"RVC/Applio processing time: {rvc_time:.3f}s -> {rvc_ready_path.name}")
		if rvc_ready_path != tts_path:
			print(f"RVC placeholder output: {rvc_ready_path}")

		# Play audio output if configured
		if config.audio_play_output:
			device_id = config.audio_output_device
			if device_id is None:
				# Try to auto-detect VB-Audio
				device_id = find_vb_audio_device()
			if device_id is not None or config.audio_output_device is None:
				logger.info(f"Playing audio (device_id={device_id})")
				play_audio(rvc_ready_path, device_id=device_id, blocking=False)
			else:
				logger.warning("Audio playback enabled but no device configured")

		turn_time = time.perf_counter() - turn_start
		logger.info(f"Turn total time: {turn_time:.3f}s")


if __name__ == "__main__":
	os.chdir(Path(__file__).resolve().parent)
	main()
