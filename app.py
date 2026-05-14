from __future__ import annotations

import asyncio
import json
import logging
import secrets
import tempfile
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, Button, Entry, Frame, Label, StringVar, Text, Tk, filedialog, ttk
from tkinter.scrolledtext import ScrolledText

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr
import websockets

from config.settings import BASE_DIR, AppConfig, load_personality, load_settings
from main import build_messages, chat_with_backend, ensure_output_dirs, write_subtitle, clear_subtitle, schedule_subtitle_clear
from rvc.applio_stub import prime_applio_worker, process_with_rvc
from tts.audio_player import find_vb_audio_device, play_audio
from tts.edge_tts_engine import SpeakerName, synthesize_speech
from utils.cleanup import cleanup_old_files
from utils.history import load_history, save_history
from utils.logger import logger


class TkLogHandler(logging.Handler):
	def __init__(self, app: "AIVTApp") -> None:
		super().__init__()
		self.app = app

	def emit(self, record: logging.LogRecord) -> None:
		self.app.append_log(self.format(record))


ENV_KEYS = {
	"PREFERRED_BACKEND",
	"GOOGLE_AISTUDIO_MODEL",
	"LM_STUDIO_MODEL",
	"RVC_MODEL_PTH",
	"RVC_MODEL_INDEX",
	"EDGE_APPLIO_PATH",
	"LM_STUDIO_BASE_URL",
	"GOOGLE_AISTUDIO_API_KEY",
}


def _read_env_lines() -> list[str]:
	env_path = BASE_DIR / ".env"
	if not env_path.exists():
		return []
	return env_path.read_text(encoding="utf-8").splitlines()


def _write_env_value(key: str, value: str) -> None:
	env_path = BASE_DIR / ".env"
	lines = _read_env_lines()
	prefix = f"{key}="
	updated = False
	new_lines: list[str] = []

	for line in lines:
		if line.startswith(prefix):
			new_lines.append(f"{key}={value}")
			updated = True
		else:
			new_lines.append(line)

	if not updated:
		if new_lines and new_lines[-1].strip():
			new_lines.append("")
		new_lines.append(f"{key}={value}")

	env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class AIVTApp:
	def __init__(self) -> None:
		self.config = load_settings()
		ensure_output_dirs(self.config)
		prime_applio_worker(self.config)

		self.personality = load_personality(self.config.personality_path)
		self.history = load_history(self.config.history_file)
		self.current_speaker = self.config.tts_default_speaker  # type: ignore[assignment]
		self.current_pitch = self.config.tts_default_pitch_semitones
		self.busy = False

		self.root = Tk()
		self.root.title("AIVT Desktop")
		self.root.geometry("1100x760")
		self.root.minsize(960, 680)

		self.backend_var = StringVar(value=self.config.preferred_backend)
		self.gemini_model_var = StringVar(value=self.config.google_aistudio_model)
		self.lm_model_var = StringVar(value=self.config.model_name)
		self.voice_input_enabled_var = BooleanVar(value=True)
		self.chat_input_enabled_var = BooleanVar(value=True)
		self.auto_send_chat_var = BooleanVar(value=False)
		self.auto_send_ptt_var = BooleanVar(value=False)
		self.voice_mode_var = StringVar(value="voice_activation")
		self.voice_device_options = self._build_voice_device_options()
		self.voice_device_var = StringVar(value=self._initial_voice_device_label())
		self.rvc_pth_var = StringVar(value=str(self.config.rvc_model_pth))
		self.rvc_index_var = StringVar(value=str(self.config.rvc_model_index))
		self.applio_path_var = StringVar(value=str(self.config.applio_path))
		self.status_var = StringVar(value="Ready")
		self.lm_model_options = self._build_lm_model_options()
		self.voice_level_var = StringVar(value="Level: idle")
		self.ptt_recording = False
		self.ptt_frames: list[np.ndarray] = []
		self.ptt_stream: sd.InputStream | None = None
		self.voice_monitor_stop = threading.Event()
		self.voice_monitor_thread: threading.Thread | None = None
		self.last_ptt_text = ""
		self.restream_connected = False
		self.restream_thread: threading.Thread | None = None
		self.last_restream_text = ""
		self.last_restream_author = ""
		self.restream_status_var = StringVar(value="Restream: disconnected")
		self.log_handler = None

		self._build_ui()
		self._attach_log_handler()
		self._start_voice_monitor()
		self._refresh_chat_view()
		self.root.bind("<KeyPress-p>", self._on_ptt_press)
		self.root.bind("<KeyRelease-p>", self._on_ptt_release)
		self.root.bind("<KeyPress-P>", self._on_ptt_press)
		self.root.bind("<KeyRelease-P>", self._on_ptt_release)

	def _build_lm_model_options(self) -> tuple[str, ...]:
		common_models = [
			"qwen/qwen3-8b",
			"qwen/qwen3-4b",
			"qwen2.5-7b-instruct",
			"qwen2.5-3b-instruct",
			"llama-3.1-8b-instruct",
			"mistral-7b-instruct-v0.3",
			"gemma-2-9b-it",
		]
		models = [self.config.model_name] + common_models
		# Keep order but remove duplicates.
		return tuple(dict.fromkeys(m for m in models if m.strip()))

	def _build_ui(self) -> None:
		self.root.configure(bg="#10131a")

		top = Frame(self.root, bg="#10131a")
		top.pack(fill=X, padx=16, pady=(16, 8))

		Label(top, text="AIVT Desktop", fg="#f2f4f8", bg="#10131a", font=("Segoe UI", 20, "bold")).pack(anchor="w")
		Label(top, text="Chat + Gemini/LM Studio + RVC", fg="#9ca3af", bg="#10131a", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

		body = Frame(self.root, bg="#10131a")
		body.pack(fill=BOTH, expand=True, padx=16, pady=8)

		left = Frame(body, bg="#10131a")
		left.pack(side=LEFT, fill=BOTH, expand=True)

		input_panel = Frame(left, bg="#151a24", padx=14, pady=12)
		input_panel.pack(fill=X, pady=(0, 10))
		Label(input_panel, text="Main Input", fg="#f2f4f8", bg="#151a24", font=("Segoe UI", 13, "bold")).pack(anchor="w")

		source_row = Frame(input_panel, bg="#151a24")
		source_row.pack(fill=X, pady=(0, 8))
		ttk.Checkbutton(source_row, text="voice input", variable=self.voice_input_enabled_var).pack(side=LEFT)
		ttk.Checkbutton(source_row, text="chat input", variable=self.chat_input_enabled_var).pack(side=LEFT, padx=(14, 0))
		ttk.Checkbutton(source_row, text="Auto-send chat", variable=self.auto_send_chat_var).pack(side=LEFT, padx=(8, 0))
		ttk.Combobox(
			source_row,
			textvariable=self.voice_mode_var,
			values=("voice_activation", "push_to_talk (P)"),
			state="readonly",
			width=18,
		).pack(side=LEFT, padx=(14, 0))
		Button(source_row, text="Connect Restream", command=self.connect_restream, bg="#334155", fg="white", relief="flat", padx=10, pady=4).pack(side=LEFT, padx=(14, 0))
		Label(
			source_row,
			text="Priority: input > voice input > chat input",
			fg="#9ca3af",
			bg="#151a24",
		).pack(side=RIGHT)
		self.input_box = Text(input_panel, height=4, wrap="word", bg="#0b0f16", fg="#e5e7eb", insertbackground="#e5e7eb", font=("Segoe UI", 10), relief="flat")
		self.input_box.pack(fill=X, pady=(0, 8))
		self.input_box.bind("<Control-Return>", lambda _: self.send_message())

		input_actions = Frame(input_panel, bg="#151a24")
		input_actions.pack(fill=X)
		Button(input_actions, text="Send", command=self.send_message, bg="#2b6cb0", fg="white", relief="flat", padx=18, pady=8).pack(side=LEFT)
		Button(input_actions, text="Clear", command=self._clear_input, bg="#374151", fg="white", relief="flat", padx=18, pady=8).pack(side=LEFT, padx=(8, 0))
		Label(input_actions, textvariable=self.status_var, fg="#cbd5e1", bg="#151a24", wraplength=520, justify="left").pack(side=LEFT, padx=(14, 0))

		chat_panel = Frame(left, bg="#151a24", padx=14, pady=12)
		chat_panel.pack(fill=BOTH, expand=True, pady=(0, 10))
		Label(chat_panel, text="Chat", fg="#f2f4f8", bg="#151a24", font=("Segoe UI", 13, "bold")).pack(anchor="w")
		self.chat_view = ScrolledText(chat_panel, wrap="word", height=18, bg="#0b0f16", fg="#e5e7eb", insertbackground="#e5e7eb", font=("Segoe UI", 10), relief="flat")
		self.chat_view.pack(fill=BOTH, expand=True, pady=(8, 0))
		self.chat_view.configure(state="disabled")

		voice_panel = Frame(left, bg="#151a24", padx=14, pady=12)
		voice_panel.pack(fill=X)
		Label(voice_panel, text="Voice", fg="#f2f4f8", bg="#151a24", font=("Segoe UI", 13, "bold")).pack(anchor="w")
		voice_device_row = Frame(voice_panel, bg="#151a24")
		voice_device_row.pack(fill=X, pady=(8, 0))
		Label(voice_device_row, text="Microphone", fg="#d1d5db", bg="#151a24").pack(anchor="w")
		ttk.Combobox(
			voice_device_row,
			textvariable=self.voice_device_var,
			values=self.voice_device_options,
			state="readonly",
		).pack(fill=X, pady=(4, 0))
		self.voice_device_var.trace_add("write", lambda *_: self._on_voice_device_changed())
		level_row = Frame(voice_panel, bg="#151a24")
		level_row.pack(fill=X, pady=(10, 0))
		Label(level_row, textvariable=self.voice_level_var, fg="#9ca3af", bg="#151a24").pack(anchor="w")
		self.voice_level_bar = ttk.Progressbar(level_row, orient="horizontal", mode="determinate", maximum=100)
		self.voice_level_bar.pack(fill=X, pady=(4, 0))
		Label(voice_panel, textvariable=self.restream_status_var, fg="#9ca3af", bg="#151a24").pack(anchor="w", pady=(6, 0))
		Label(voice_panel, text="Hold P for push-to-talk when voice mode is set to push_to_talk", fg="#9ca3af", bg="#151a24").pack(anchor="w", pady=(4, 0))

		right = Frame(body, bg="#10131a")
		right.pack(side=RIGHT, fill=Y, padx=(12, 0))

		log_panel = Frame(right, bg="#151a24", padx=14, pady=12)
		log_panel.pack(fill=BOTH, expand=True, pady=(0, 10))
		Label(log_panel, text="Log", fg="#f2f4f8", bg="#151a24", font=("Segoe UI", 13, "bold")).pack(anchor="w")
		self.log_view = ScrolledText(log_panel, wrap="word", width=42, bg="#0b0f16", fg="#93c5fd", insertbackground="#e5e7eb", font=("Consolas", 9), relief="flat")
		self.log_view.pack(fill=BOTH, expand=True, pady=(8, 0))
		self.log_view.configure(state="disabled")

		settings = Frame(right, bg="#151a24", padx=14, pady=14)
		settings.pack(fill=X)

		Label(settings, text="Settings", fg="#f2f4f8", bg="#151a24", font=("Segoe UI", 13, "bold")).pack(anchor="w")

		self._field(settings, "Backend", ttk.Combobox, self.backend_var, values=("gemini", "lmstudio"), state="readonly")
		self._field(settings, "Gemini model", Entry, self.gemini_model_var)
		self._field(settings, "LM Studio model", ttk.Combobox, self.lm_model_var, values=self.lm_model_options)
		self._path_field(settings, "RVC model .pth", self.rvc_pth_var)
		self._path_field(settings, "RVC index", self.rvc_index_var)
		self._path_field(settings, "Applio path", self.applio_path_var)

		Button(settings, text="Apply & Save", command=self.apply_settings, bg="#16a34a", fg="white", relief="flat", padx=14, pady=8).pack(fill=X, pady=(12, 6))
		Button(settings, text="Refresh history", command=self._reload_history, bg="#4b5563", fg="white", relief="flat", padx=14, pady=8).pack(fill=X)

		shortcut = Label(settings, text="Ctrl+Enter = Send", fg="#6b7280", bg="#151a24")
		shortcut.pack(anchor="w", pady=(8, 0))

	def _field(self, parent: Frame, label: str, widget_cls, variable: StringVar, **kwargs) -> None:
		wrapper = Frame(parent, bg="#151a24")
		wrapper.pack(fill=X, pady=(10, 0))
		Label(wrapper, text=label, fg="#d1d5db", bg="#151a24").pack(anchor="w")
		widget = widget_cls(wrapper, textvariable=variable, **kwargs)
		widget.pack(fill=X, pady=(4, 0))

	def _path_field(self, parent: Frame, label: str, variable: StringVar) -> None:
		wrapper = Frame(parent, bg="#151a24")
		wrapper.pack(fill=X, pady=(10, 0))
		Label(wrapper, text=label, fg="#d1d5db", bg="#151a24").pack(anchor="w")
		row = Frame(wrapper, bg="#151a24")
		row.pack(fill=X, pady=(4, 0))
		Entry(row, textvariable=variable).pack(side=LEFT, fill=X, expand=True)
		Button(row, text="...", command=lambda: self._choose_path(variable), width=3).pack(side=RIGHT, padx=(6, 0))

	def _choose_path(self, variable: StringVar) -> None:
		path = filedialog.askopenfilename(title="Choose file")
		if path:
			variable.set(path)

	def _clear_input(self) -> None:
		self.input_box.delete("1.0", END)

	def _reload_history(self) -> None:
		self.history = load_history(self.config.history_file)
		self._refresh_chat_view()
		self.status_var.set(f"Loaded {len(self.history)} messages")

	def _refresh_chat_view(self) -> None:
		self.chat_view.configure(state="normal")
		self.chat_view.delete("1.0", END)
		self.chat_view.insert(END, "Welcome to AIVT Desktop\n\n")
		for item in self.history[-20:]:
			role = item.get("role", "message").title()
			content = item.get("content", "")
			self.chat_view.insert(END, f"{role}: {content}\n\n")
		self.chat_view.configure(state="disabled")
		self.chat_view.see(END)

	def _attach_log_handler(self) -> None:
		handler = TkLogHandler(self)
		if logger.handlers:
			handler.setFormatter(logger.handlers[0].formatter)
		self.log_handler = handler
		logger.addHandler(handler)

	def append_log(self, message: str) -> None:
		def _append() -> None:
			self.log_view.configure(state="normal")
			self.log_view.insert(END, message + "\n")
			self.log_view.see(END)
			self.log_view.configure(state="disabled")

		self.root.after(0, _append)

	def apply_settings(self) -> None:
		self.config.preferred_backend = self.backend_var.get().strip().lower() or "gemini"
		self.config.google_aistudio_model = self.gemini_model_var.get().strip() or self.config.google_aistudio_model
		self.config.model_name = self.lm_model_var.get().strip() or self.config.model_name
		voice_device_index, voice_device_name = self._resolve_selected_voice_device()
		self.config.voice_input_device = voice_device_index
		self.config.voice_input_device_name = voice_device_name
		self.config.rvc_model_pth = Path(self.rvc_pth_var.get().strip()) if self.rvc_pth_var.get().strip() else self.config.rvc_model_pth
		self.config.rvc_model_index = Path(self.rvc_index_var.get().strip()) if self.rvc_index_var.get().strip() else self.config.rvc_model_index
		self.config.applio_path = Path(self.applio_path_var.get().strip()) if self.applio_path_var.get().strip() else self.config.applio_path

		_write_env_value("PREFERRED_BACKEND", self.config.preferred_backend)
		_write_env_value("GOOGLE_AISTUDIO_MODEL", self.config.google_aistudio_model)
		_write_env_value("LM_STUDIO_MODEL", self.config.model_name)
		_write_env_value("VOICE_INPUT_DEVICE", str(self.config.voice_input_device if self.config.voice_input_device is not None else -1))
		_write_env_value("VOICE_INPUT_DEVICE_NAME", self.config.voice_input_device_name)
		_write_env_value("RVC_MODEL_PTH", str(self.config.rvc_model_pth))
		_write_env_value("RVC_MODEL_INDEX", str(self.config.rvc_model_index))
		_write_env_value("EDGE_APPLIO_PATH", str(self.config.applio_path))
		_write_env_value("AUTO_SEND_CHAT", "1" if self.auto_send_chat_var.get() else "0")
		_write_env_value("AUTO_SEND_PTT", "1" if self.auto_send_ptt_var.get() else "0")

		self.status_var.set(f"Saved settings. Backend={self.config.preferred_backend.upper()} | Gemini={self.config.google_aistudio_model}")

	def send_message(self) -> None:
		if self.busy:
			self.status_var.set("Busy processing the previous message")
			return

		input_text = self.input_box.get("1.0", END).strip()
		use_voice = bool(self.voice_input_enabled_var.get())
		use_chat = bool(self.chat_input_enabled_var.get())
		voice_mode = self.voice_mode_var.get().strip()

		if not input_text and not use_voice and not use_chat:
			self.status_var.set("No source enabled")
			return

		self.status_var.set("Preparing input...")
		self.busy = True

		threading.Thread(
			target=self._resolve_and_process_message,
			args=(input_text, use_voice, use_chat, voice_mode),
			daemon=True,
		).start()

	def _resolve_and_process_message(
		self,
		input_text: str,
		use_voice: bool,
		use_chat: bool,
		voice_mode: str,
	) -> None:
		try:
			# 1) input (the bottom input box)
			if input_text:
				selected_text = input_text
				source = "input"
			else:
				selected_text = ""
				source = ""

			# 2) voice input
			if not selected_text and use_voice:
				if voice_mode.startswith("voice_activation"):
					self.root.after(0, lambda: self.status_var.set("Recording voice input..."))
					voice_text = self._record_and_transcribe_voice()
				else:
					voice_text = self.last_ptt_text.strip()
					self.last_ptt_text = ""
				if voice_text:
					selected_text = voice_text
					source = "voice input"

			# 3) chat input
			if not selected_text and use_chat and self.last_restream_text.strip():
				selected_text = self.last_restream_text.strip()
				source = "chat input"

			if not selected_text:
				self.root.after(0, lambda: self._on_error("Could not resolve any valid input from selected sources"))
				return

			self.root.after(0, lambda s=source, t=selected_text: self._on_user_selected(s, t))
			self._process_message(selected_text)
		except Exception as exc:
			message = str(exc)
			logger.error(f"Desktop input resolve error: {exc}")
			self.root.after(0, lambda msg=message: self._on_error(msg))
			self.root.after(0, self._finish_busy)

	def _on_user_selected(self, source: str, text: str) -> None:
		self._clear_input()
		self._append_chat("EiX2", f"[{source}] {text}")
		self.status_var.set(f"Thinking... (source: {source})")
		if source == "chat input":
			self.last_restream_text = ""
			self.last_restream_author = ""
			self.root.after(0, lambda: self.restream_status_var.set("Restream: waiting for new messages"))

	def connect_restream(self) -> None:
		if self.restream_connected:
			self.restream_status_var.set("Restream: already connected")
			return
		if self.restream_thread and self.restream_thread.is_alive():
			self.restream_status_var.set("Restream: connecting...")
			return

		self.restream_status_var.set("Restream: starting OAuth...")
		self.restream_thread = threading.Thread(target=self._restream_auth_and_listen, daemon=True)
		self.restream_thread.start()

	def _restream_auth_and_listen(self) -> None:
		client_id = self.config.restream_client_id
		client_secret = self.config.restream_client_secret
		redirect_uri = self.config.restream_redirect_uri

		if not client_id or not client_secret:
			self.root.after(0, lambda: self.restream_status_var.set("Restream: missing client_id/client_secret in .env"))
			return

		state = secrets.token_hex(16)
		auth_url = (
			"https://api.restream.io/login"
			f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
		)

		parsed = urlparse(redirect_uri)
		host = parsed.hostname or "localhost"
		port = parsed.port or 8080

		result: dict[str, str] = {"code": "", "state": ""}

		class CallbackHandler(BaseHTTPRequestHandler):
			def do_GET(self) -> None:
				params = parse_qs(urlparse(self.path).query)
				result["code"] = params.get("code", [""])[0]
				result["state"] = params.get("state", [""])[0]
				self.send_response(200)
				self.end_headers()
				self.wfile.write("Done! กลับไปดู AIVT app ได้เลย".encode("utf-8"))

			def log_message(self, format: str, *args) -> None:  # noqa: A003
				return

		try:
			self.root.after(0, lambda: self.restream_status_var.set("Restream: open browser for login"))
			webbrowser.open(auth_url)
			server = HTTPServer((host, port), CallbackHandler)
			server.timeout = 180
			server.handle_request()
			server.server_close()

			code = result.get("code", "")
			state_recv = result.get("state", "")
			if not code:
				self.root.after(0, lambda: self.restream_status_var.set("Restream: no authorization code received"))
				return
			if state_recv and state_recv != state:
				self.root.after(0, lambda: self.restream_status_var.set("Restream: state mismatch"))
				return

			token_res = requests.post(
				"https://api.restream.io/oauth/token",
				data={
					"grant_type": "authorization_code",
					"code": code,
					"redirect_uri": redirect_uri,
					"client_id": client_id,
					"client_secret": client_secret,
				},
				timeout=30,
			)
			token_res.raise_for_status()
			access_token = token_res.json().get("access_token", "")
			if not access_token:
				self.root.after(0, lambda: self.restream_status_var.set("Restream: failed to get access token"))
				return

			self.restream_connected = True
			self.root.after(0, lambda: self.restream_status_var.set("Restream: connected, waiting messages..."))
			asyncio.run(self._restream_read_chat(access_token))
		except Exception as exc:
			self.restream_connected = False
			message = f"Restream error: {exc}"
			logger.error(message)
			self.root.after(0, lambda m=message: self.restream_status_var.set(m))

	async def _restream_read_chat(self, access_token: str) -> None:
		url = f"wss://chat.api.restream.io/ws?accessToken={access_token}"
		async with websockets.connect(url) as ws:
			async for raw in ws:
				try:
					data = json.loads(raw)
				except Exception:
					continue

				action = data.get("action")
				if action == "heartbeat":
					continue
				if action != "event":
					continue

				payload = data.get("payload", {})
				event_payload = payload.get("eventPayload", {})
				author = event_payload.get("author", {}).get("displayName", "Unknown")
				text = (event_payload.get("text") or "").strip()
				if not text:
					continue

				self.last_restream_author = author
				self.last_restream_text = text
				self.root.after(0, lambda a=author, t=text: self._on_restream_message(a, t))

	def _on_restream_message(self, author: str, text: str) -> None:
		self.restream_status_var.set(f"Restream: latest from {author}: {text[:60]}")
		self._append_chat(author, text)
		# Auto-send incoming Restream chat to backend when enabled
		try:
			if self.auto_send_chat_var.get() and not self.busy:
				threading.Thread(
					target=self._resolve_and_process_message,
					args=("", False, True, self.voice_mode_var.get()),
					daemon=True,
				).start()
		except Exception as exc:
			logger.warning(f"Auto-send Restream failed: {exc}")

	def _normalize_voice_mode(self) -> str:
		mode = self.voice_mode_var.get().strip().lower()
		if mode.startswith("push_to_talk"):
			return "push_to_talk"
		return "voice_activation"

	def _build_voice_device_options(self) -> tuple[str, ...]:
		options: list[str] = []
		try:
			for index, device in enumerate(sd.query_devices()):
				if int(device.get("max_input_channels", 0)) <= 0:
					continue
				name = str(device.get("name", "Unknown"))
				options.append(f"{index}: {name}")
		except Exception as exc:
			logger.warning(f"Could not enumerate microphones: {exc}")
		if not options:
			options.append("default")
		return tuple(options)

	def _initial_voice_device_label(self) -> str:
		if self.config.voice_input_device is not None and self.config.voice_input_device >= 0:
			for option in self.voice_device_options:
				if option.startswith(f"{self.config.voice_input_device}:"):
					return option
		if self.config.voice_input_device_name:
			for option in self.voice_device_options:
				if self.config.voice_input_device_name.lower() in option.lower():
					return option
		return self.voice_device_options[0] if self.voice_device_options else "default"

	def _resolve_selected_voice_device(self) -> tuple[int | None, str]:
		selection = self.voice_device_var.get().strip()
		if not selection or selection == "default":
			return None, ""
		if selection and selection[0].isdigit() and ":" in selection:
			index_text, name = selection.split(":", 1)
			try:
				return int(index_text.strip()), name.strip()
			except ValueError:
				return None, selection
		return None, selection

	def _start_voice_monitor(self) -> None:
		if self.voice_monitor_thread and self.voice_monitor_thread.is_alive():
			return
		self.voice_monitor_stop.clear()
		self.voice_monitor_thread = threading.Thread(target=self._voice_monitor_loop, daemon=True)
		self.voice_monitor_thread.start()

	def _on_voice_device_changed(self) -> None:
		self.voice_monitor_stop.set()
		self.voice_monitor_stop = threading.Event()
		self._start_voice_monitor()

	def _voice_monitor_loop(self) -> None:
		while not self.voice_monitor_stop.is_set():
			device, device_name = self._resolve_selected_voice_device()
			try:
				if not bool(self.voice_input_enabled_var.get()):
					self.root.after(0, lambda: self._set_voice_level(0.0, "Voice disabled"))
					time.sleep(0.2)
					continue

				def _callback(indata, frames, _time_info, status):
					if status:
						logger.debug(f"Voice monitor status: {status}")
					try:
						rms = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
						self.root.after(0, lambda r=rms, n=device_name: self._set_voice_level(r, n))
					except Exception:
						pass

				with sd.InputStream(
					samplerate=self.config.voice_input_sample_rate,
					channels=self.config.voice_input_channels,
					dtype="float32",
					device=device,
					callback=_callback,
				):
					while not self.voice_monitor_stop.is_set():
						time.sleep(0.1)
			except Exception as exc:
				self.root.after(0, lambda e=str(exc): self._set_voice_level(0.0, f"Mic monitor error: {e}"))
				time.sleep(1.0)

	def _set_voice_level(self, rms: float, device_name: str) -> None:
		level = max(0.0, min(1.0, rms * 12.0)) * 100.0
		self.voice_level_bar["value"] = level
		if level <= 1.0:
			state = "No sound input"
		else:
			state = f"Sound input: {level:.0f}%"
		if device_name:
			state = f"{state} | {device_name}"
		self.voice_level_var.set(state)

	def _on_ptt_press(self, _event) -> None:
		if not bool(self.voice_input_enabled_var.get()):
			return
		if self._normalize_voice_mode() != "push_to_talk":
			return
		if self.busy or self.ptt_recording:
			return

		self.ptt_frames = []
		self.ptt_recording = True
		self.status_var.set("PTT: recording... release P to stop")

		def _callback(indata, frames, _time_info, status):
			if status:
				logger.warning(f"PTT stream status: {status}")
			if self.ptt_recording:
				self.ptt_frames.append(indata.copy())

		device, _device_name = self._resolve_selected_voice_device()

		self.ptt_stream = sd.InputStream(
			samplerate=self.config.voice_input_sample_rate,
			channels=self.config.voice_input_channels,
			dtype="float32",
			device=device,
			callback=_callback,
		)
		self.ptt_stream.start()

	def _on_ptt_release(self, _event) -> None:
		if not self.ptt_recording:
			return
		self.ptt_recording = False

		if self.ptt_stream is not None:
			try:
				self.ptt_stream.stop()
				self.ptt_stream.close()
			except Exception as exc:
				logger.warning(f"PTT stream close error: {exc}")
			finally:
				self.ptt_stream = None

		if not self.ptt_frames:
			self.status_var.set("PTT: no voice captured")
			return

		try:
			audio = np.concatenate(self.ptt_frames, axis=0)
			if self.config.voice_input_channels == 1:
				audio_to_save = audio.reshape(-1)
			else:
				audio_to_save = audio

			wav_path = Path(tempfile.gettempdir()) / "aivt_ui_ptt.wav"
			sf.write(str(wav_path), audio_to_save, self.config.voice_input_sample_rate)

			recognizer = sr.Recognizer()
			with sr.AudioFile(str(wav_path)) as source:
				audio_data = recognizer.record(source)

			text = recognizer.recognize_google(audio_data, language=self.config.voice_input_language).strip()  # type: ignore[attr-defined]
			self.last_ptt_text = text
			self.input_box.delete("1.0", END)
			self.input_box.insert("1.0", text)
			self.status_var.set("PTT: voice captured (press Send)")
			# If configured, auto-send captured PTT to backend
			if self.auto_send_ptt_var.get() and not self.busy:
				self.send_message()
		except sr.UnknownValueError:
			self.last_ptt_text = ""
			self.status_var.set("PTT: could not recognize speech")
		except Exception as exc:
			self.last_ptt_text = ""
			logger.warning(f"PTT transcription error: {exc}")
			self.status_var.set("PTT: transcription failed")

	def _record_and_transcribe_voice(self) -> str:
		device, _device_name = self._resolve_selected_voice_device()

		frames = int(self.config.voice_input_sample_rate * self.config.voice_input_duration_seconds)
		audio = sd.rec(
			frames,
			samplerate=self.config.voice_input_sample_rate,
			channels=self.config.voice_input_channels,
			dtype="float32",
			device=device,
		)
		sd.wait()

		if self.config.voice_input_channels == 1:
			audio_to_save = audio.reshape(-1)
		else:
			audio_to_save = audio

		wav_path = Path(tempfile.gettempdir()) / "aivt_ui_voice_input.wav"
		sf.write(str(wav_path), audio_to_save, self.config.voice_input_sample_rate)

		recognizer = sr.Recognizer()
		with sr.AudioFile(str(wav_path)) as source:
			audio_data = recognizer.record(source)

		try:
			return getattr(recognizer, "recognize_google")(audio_data, language=self.config.voice_input_language).strip()
		except sr.UnknownValueError:
			return ""
		except sr.RequestError as exc:
			logger.warning(f"Voice STT request error: {exc}")
			return ""

	def _process_message(self, user_text: str) -> None:
		try:
			turn_start = time.perf_counter()
			messages = build_messages(self.personality, self.history, user_text)
			assistant_text = chat_with_backend(self.config, messages)
			if not assistant_text:
				raise RuntimeError("Backend returned empty response")

			# Update subtitle while thinking
			write_subtitle(f"คิดing...")

			self.history.append({"role": "user", "content": user_text})
			self.history.append({"role": "assistant", "content": assistant_text})
			self.history = self.history[-self.config.max_history_messages :]
			save_history(self.history, self.config.history_file)

			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			tts_path = self.config.tts_output_dir / f"reply_{timestamp}.{self.config.tts_output_format}"
			asyncio.run(
				synthesize_speech(
					text=assistant_text,
					output_path=tts_path,
					voice=self.config.tts_voice,
					rate=self.config.tts_rate,
					volume=self.config.tts_volume,
					speaker=self.current_speaker,  # type: ignore[arg-type]
					pitch_semitones=self.current_pitch,
				)
			)
			rvc_ready_path = process_with_rvc(tts_path, self.config)
			if self.config.audio_play_output:
				device_id = self.config.audio_output_device or find_vb_audio_device()
				if device_id is not None:
					# Update subtitle with AI response while playing
					write_subtitle(assistant_text)
					play_audio(rvc_ready_path, device_id=device_id, blocking=True)
					# Clear subtitle after playback
					schedule_subtitle_clear(delay=3.0)
			cleanup_old_files(self.config.tts_output_dir, max_files=5)

			elapsed = time.perf_counter() - turn_start
			self.root.after(0, lambda: self._on_success(user_text, assistant_text, elapsed))
		except Exception as exc:
			message = str(exc)
			logger.error(f"Desktop app error: {exc}")
			self.root.after(0, lambda msg=message: self._on_error(msg))
		finally:
			self.root.after(0, self._finish_busy)

	def _on_success(self, user_text: str, assistant_text: str, elapsed: float) -> None:
		self._append_chat("AI", assistant_text)
		self.status_var.set(f"Done in {elapsed:.2f}s using {self.config.preferred_backend.upper()}")

	def _on_error(self, message: str) -> None:
		self._append_chat("Error", message)
		self.status_var.set(message)

	def _finish_busy(self) -> None:
		self.busy = False

	def _append_chat(self, role: str, content: str) -> None:
		self.chat_view.configure(state="normal")
		self.chat_view.insert(END, f"{role}: {content}\n\n")
		self.chat_view.configure(state="disabled")
		self.chat_view.see(END)

	def run(self) -> None:
		self.root.protocol("WM_DELETE_WINDOW", self._on_close)
		self.root.mainloop()

	def _on_close(self) -> None:
		self.voice_monitor_stop.set()
		try:
			if self.log_handler is not None:
				logger.removeHandler(self.log_handler)
		except Exception:
			pass
		self.root.destroy()


def main() -> None:
	AIVTApp().run()


if __name__ == "__main__":
	main()