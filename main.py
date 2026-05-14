from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

import requests
from google import genai

from config.settings import AppConfig, load_personality, load_settings
from rvc.applio_stub import prime_applio_worker, process_with_rvc
from tts.edge_tts_engine import synthesize_speech
from tts.edge_tts_engine import SpeakerName
from tts.audio_player import play_audio, find_vb_audio_device
from utils.vtuber_controller import (
	initialize_vtuber_controller,
	cleanup_vtuber_controller,
	_run_in_loop,
	list_hotkeys,
	get_vtuber_controller,
)
from typing import cast
from utils.history import load_history, save_history
from utils.cleanup import cleanup_old_files
from utils.logger import logger
import time
import threading
from typing import Optional


# Subtitle management (module-level for use in app.py and CLI)
_SUBTITLE_FILE = Path(__file__).resolve().parent / "subtitle.txt"
_SUBTITLE_LOCK = threading.Lock()
_SUBTITLE_TIMER: Optional[threading.Timer] = None


def write_subtitle(text: str) -> None:
	"""Write text to subtitle.txt for streaming/display."""
	with _SUBTITLE_LOCK:
		try:
			_SUBTITLE_FILE.write_text(text + "\n", encoding="utf-8")
		except Exception as exc:
			logger.error(f"Failed to write subtitle: {exc}")


def clear_subtitle() -> None:
	"""Clear subtitle.txt."""
	with _SUBTITLE_LOCK:
		try:
			_SUBTITLE_FILE.write_text("", encoding="utf-8")
		except Exception as exc:
			logger.error(f"Failed to clear subtitle: {exc}")


def schedule_subtitle_clear(delay: float = 5.0) -> None:
	"""Schedule subtitle auto-clear after delay (in seconds)."""
	global _SUBTITLE_TIMER
	with _SUBTITLE_LOCK:
		if _SUBTITLE_TIMER:
			try:
				_SUBTITLE_TIMER.cancel()
			except Exception:
				pass
		_SUBTITLE_TIMER = threading.Timer(delay, clear_subtitle)
		_SUBTITLE_TIMER.daemon = True
		_SUBTITLE_TIMER.start()


def build_messages(system_prompt: str, history: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
	messages = [{"role": "system", "content": system_prompt}]
	messages.extend(history)
	messages.append({"role": "user", "content": user_text})
	return messages


def chat_with_lm_studio(config: AppConfig, messages: list[dict[str, str]]) -> str:
	"""Send messages to LM Studio local API."""
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


def chat_with_google_gemini(config: AppConfig, messages: list[dict[str, str]]) -> str:
	"""Send messages to Google Gemini using the current SDK."""
	if not config.google_aistudio_api_key:
		raise RuntimeError("GOOGLE_AISTUDIO_API_KEY is not set")

	client = genai.Client(api_key=config.google_aistudio_api_key)
	prompt_parts: list[str] = []
	for message in messages:
		role = message.get("role", "user")
		content = message.get("content", "").strip()
		if not content:
			continue
		if role == "system":
			prompt_parts.append(f"[System: {content}]")
		elif role == "user":
			prompt_parts.append(content)
		else:
			prompt_parts.append(f"{role.title()}: {content}")

	prompt = "\n".join(prompt_parts) if prompt_parts else "สวัสดี"
	model = config.google_aistudio_model or "gemini-2.5-flash"

	max_attempts = 4
	delay_seconds = 10

	for attempt in range(1, max_attempts + 1):
		try:
			response = client.models.generate_content(
				model=model,
				contents=prompt,
			)
			return (response.text or "").strip()
		except Exception as exc:
			message = str(exc)
			is_rate_limited = "429" in message or "RESOURCE_EXHAUSTED" in message
			is_busy = "503" in message or "UNAVAILABLE" in message
			if (is_rate_limited or is_busy) and attempt < max_attempts:
				label = "rate-limited (429)" if is_rate_limited else "busy (503)"
				logger.warning(f"🔄 {config.preferred_backend.upper()} {label}, retrying in {delay_seconds}s... ({attempt}/{max_attempts})")
				time.sleep(delay_seconds)
				delay_seconds *= 2
				continue
			raise

	return ""


def chat_with_backend(config: AppConfig, messages: list[dict[str, str]]) -> str:
	"""Wrapper to call the appropriate backend based on config."""
	backend = config.preferred_backend.lower()
	
	if backend == "gemini":
		return chat_with_google_gemini(config, messages)
	elif backend == "lmstudio":
		return chat_with_lm_studio(config, messages)
	else:
		raise ValueError(f"Unknown backend: {backend}. Use 'gemini' or 'lmstudio'")


def ensure_output_dirs(config: AppConfig) -> None:
	config.tts_output_dir.mkdir(parents=True, exist_ok=True)
	config.rvc_output_dir.mkdir(parents=True, exist_ok=True)
	config.history_file.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
	config = load_settings()
	ensure_output_dirs(config)

	# Start the Applio worker early so its startup/import cost is paid before the first reply
	prime_applio_worker(config)

	# Initialize VTuber controller once so connection is visible and reused
	vtuber_ctrl = None
	try:
		vtuber_ctrl = _run_in_loop(initialize_vtuber_controller())
		logger.info(f"VTuber controller connected: {bool(vtuber_ctrl)}")
	except Exception as e:
		logger.warning(f"Failed to initialize VTuber controller at startup: {e}")

	# subtitle timer to auto-clear after delay (for CLI)
	# Use module-level functions: write_subtitle, clear_subtitle, schedule_subtitle_clear

	personality = load_personality(config.personality_path)
	history = load_history(config.history_file)

	print("AIVT ready")
	print(f"Backend: {config.preferred_backend.upper()}")
	if config.preferred_backend.lower() == "gemini":
		print(f"Model: {config.google_aistudio_model or 'gemini-2.5-flash'}")
	else:
		print(f"Model: {config.model_name}")
	print(f"Loaded {len(history)} messages from history")
	print("Commands: /backend <gemini|lmstudio>, /speaker <name>, /pitch <value>, /speakers, /hotkeys\n")

	current_speaker = cast(SpeakerName, config.tts_default_speaker)
	current_pitch = config.tts_default_pitch_semitones

	print(f"Current speaker: {current_speaker}, pitch offset: {current_pitch} semitones")

	while True:
		user_text = input("You: ").strip()
		# New input arrives -> cancel any pending subtitle clear and clear immediately
		if _SUBTITLE_TIMER is not None:
			try:
				_SUBTITLE_TIMER.cancel()
			except Exception:
				pass
			clear_subtitle()
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

		if user_text.startswith("/backend "):
			try:
				_, backend = user_text.split(maxsplit=1)
				backend = backend.strip().lower()
				if backend not in ("gemini", "lmstudio"):
					print("Usage: /backend <gemini|lmstudio>")
					continue
				config.preferred_backend = backend
				if backend == "gemini":
					print(f"✓ Backend switched to: GEMINI (model: {config.google_aistudio_model or 'gemini-2.5-flash'})")
				else:
					print(f"✓ Backend switched to: LM STUDIO (model: {config.model_name})")
			except Exception as e:
				logger.error(f"Error switching backend: {e}")
				print("Usage: /backend <gemini|lmstudio>")
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

		if user_text.strip() == "/hotkeys":
			controller = get_vtuber_controller()
			if not controller:
				print("VTuber controller not initialized")
				continue
			hotkeys = list_hotkeys(controller)
			if not hotkeys:
				print("No hotkeys available or not connected")
			else:
				print("Available hotkeys:")
				for idx, hk in enumerate(hotkeys, start=1):
					name = hk.get("name") or hk.get("fileName") or hk.get("file") or "<unnamed>"
					print(f"{idx}: {name}  id={hk.get('hotkeyID')}")
			continue

		turn_start = time.perf_counter()
		try:
			# Write subtitle: LLM thinking
			write_subtitle("*** คิดing ***")
			lm_start = time.perf_counter()
			messages = build_messages(personality, history, user_text)
			assistant_text = chat_with_backend(config, messages)
			lm_time = time.perf_counter() - lm_start
			backend_name = config.preferred_backend.upper()
			logger.info(f"{backend_name} response time: {lm_time:.3f}s")
			
			# Skip if response is empty
			if not assistant_text:
				logger.warning(f"{backend_name} returned empty response")
				continue
		except Exception as exc:
			logger.error(f"LLM Backend error ({config.preferred_backend.upper()}): {exc}")
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
				# Write subtitle: spoken text
				write_subtitle(assistant_text)
				logger.info(f"Playing audio (device_id={device_id})")
				play_audio(rvc_ready_path, device_id=device_id, blocking=True)
				# schedule clear after playback ends
				schedule_subtitle_clear(5.0)
			else:
				logger.warning("Audio playback enabled but no device configured")
		else:
			# Not playing audio — still schedule subtitle clear
			schedule_subtitle_clear(5.0)

		turn_time = time.perf_counter() - turn_start
		logger.info(f"Turn total time: {turn_time:.3f}s")


if __name__ == "__main__":
	os.chdir(Path(__file__).resolve().parent)
	main()
