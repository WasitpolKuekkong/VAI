from __future__ import annotations

import asyncio
import io
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from utils.logger import logger

if TYPE_CHECKING:
    from core.pipeline import VTuberPipeline

try:
    import discord
    from discord.ext import commands
    _DISCORD_AVAILABLE = True
except ImportError:
    _DISCORD_AVAILABLE = False

try:
    import whisper as _whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False


# ── Globals ───────────────────────────────────────────────────────────────────
_bot: "VAIBot | None" = None
_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None and _WHISPER_AVAILABLE:
        logger.info("Loading Whisper model (small)...")
        _whisper_model = _whisper.load_model("small")
    return _whisper_model


# ── Audio sink for receiving voice ────────────────────────────────────────────
if _DISCORD_AVAILABLE:
    class _VAISink(discord.sinks.WaveSink):
        """Collect audio per-user; on stop, transcribe + send to pipeline."""

        def __init__(self, bot: "VAIBot") -> None:
            super().__init__()
            self._vai_bot = bot

        def cleanup(self) -> None:
            super().cleanup()


    # ── Bot class ─────────────────────────────────────────────────────────────
    class VAIBot(commands.Bot):
        def __init__(
            self,
            pipeline: "VTuberPipeline",
            chat_channel_id: int | None,
            owner_name: str = "EiX2",
            language: str = "th",
        ) -> None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            intents.members = True
            super().__init__(command_prefix="!", intents=intents)
            self.pipeline = pipeline
            self.chat_channel_id = chat_channel_id
            self.owner_name = owner_name
            self.language = language
            self._listen_mode: dict[int, bool] = {}   # guild_id → VAD on/off
            self._sink: dict[int, _VAISink] = {}
            self._pipeline_lock = asyncio.Lock()
            self._register_commands()

        # ── Lifecycle ─────────────────────────────────────────────────────────

        async def on_ready(self) -> None:
            await self.tree.sync()
            logger.info(f"Discord bot ready as {self.user}")

        # ── Text events ───────────────────────────────────────────────────────

        async def on_message(self, message: discord.Message) -> None:
            if message.author.bot:
                return
            await self.process_commands(message)

            is_tagged = self.user in message.mentions
            is_chat_channel = (
                self.chat_channel_id is not None
                and message.channel.id == self.chat_channel_id
            )
            if not (is_tagged or is_chat_channel):
                return

            text = message.clean_content.replace(f"@{self.user.display_name}", "").strip()
            if not text:
                return

            display = message.author.display_name
            is_owner = display.lower() == self.owner_name.lower()
            prefix = f"[{self.owner_name}]" if is_owner else f"[Discord | {display}]"
            labelled = f"{prefix}: {text}"

            async with message.channel.typing():
                reply = await self._run_pipeline(labelled)
            if reply:
                await message.reply(reply, mention_author=False)

        # ── Slash commands ────────────────────────────────────────────────────

        def _register_commands(self) -> None:
            @self.tree.command(name="join", description="VAI เข้า voice channel ของคุณ")
            async def join(interaction: discord.Interaction) -> None:
                await self._cmd_join(interaction)

            @self.tree.command(name="leave", description="VAI ออกจาก voice channel")
            async def leave(interaction: discord.Interaction) -> None:
                await self._cmd_leave(interaction)

            @self.tree.command(name="listen", description="เปิด/ปิด Voice Activation (VAD)")
            async def listen(interaction: discord.Interaction) -> None:
                await self._cmd_listen(interaction)

        async def _cmd_join(self, interaction: discord.Interaction) -> None:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.response.send_message("คุณยังไม่ได้อยู่ใน voice channel ครับ", ephemeral=True)
                return
            vc = interaction.user.voice.channel
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(vc)
            else:
                await vc.connect()
            await interaction.response.send_message(f"เข้า **{vc.name}** แล้วครับ 🎙️")

        async def _cmd_leave(self, interaction: discord.Interaction) -> None:
            if not interaction.guild.voice_client:
                await interaction.response.send_message("ไม่ได้อยู่ใน VC ครับ", ephemeral=True)
                return
            guild_id = interaction.guild.id
            self._listen_mode[guild_id] = False
            vc: discord.VoiceClient = interaction.guild.voice_client
            if vc.recording:
                vc.stop_recording()
            await vc.disconnect()
            await interaction.response.send_message("ออกจาก voice channel แล้วครับ")

        async def _cmd_listen(self, interaction: discord.Interaction) -> None:
            guild_id = interaction.guild.id
            vc: discord.VoiceClient | None = interaction.guild.voice_client

            if not vc:
                await interaction.response.send_message("ใช้ `/join` ก่อนนะครับ", ephemeral=True)
                return

            current = self._listen_mode.get(guild_id, False)
            self._listen_mode[guild_id] = not current

            if self._listen_mode[guild_id]:
                # Start recording
                sink = _VAISink(self)
                self._sink[guild_id] = sink
                vc.start_recording(sink, self._on_recording_done, interaction.channel)
                await interaction.response.send_message("🎤 Voice Activation เปิดแล้ว — พูดได้เลยครับ")
            else:
                if vc.recording:
                    vc.stop_recording()
                await interaction.response.send_message("🔇 Voice Activation ปิดแล้ว")

        # ── Voice recording callback ───────────────────────────────────────────

        async def _on_recording_done(
            self,
            sink: _VAISink,
            channel: discord.abc.Messageable,
            *args,
        ) -> None:
            wm = _get_whisper()
            if not wm:
                return

            for user_id, audio in sink.audio_data.items():
                user = self.get_user(user_id)
                display = user.display_name if user else str(user_id)
                is_owner = display.lower() == self.owner_name.lower()

                try:
                    wav_bytes = audio.file.read()
                    if len(wav_bytes) < 4096:
                        continue

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(wav_bytes)
                        tmp_path = f.name

                    result = await asyncio.to_thread(
                        wm.transcribe, tmp_path, language=self.language
                    )
                    Path(tmp_path).unlink(missing_ok=True)

                    text = (result.get("text") or "").strip()
                    if not text:
                        continue

                    logger.info(f"Discord STT [{display}]: {text}")
                    prefix = f"[{self.owner_name}]" if is_owner else f"[Discord | {display}]"
                    reply = await self._run_pipeline(f"{prefix}: {text}")
                    if reply:
                        await channel.send(f"**{display}**: {text}\n> {reply}")
                        await self._speak(channel, reply)

                except Exception as exc:
                    logger.error(f"Discord voice processing error: {exc}")

        # ── TTS playback in VC ────────────────────────────────────────────────

        async def _speak(self, channel: discord.abc.Messageable, text: str) -> None:
            guild = getattr(channel, "guild", None)
            if not guild:
                return
            vc: discord.VoiceClient | None = guild.voice_client
            if not vc or not vc.is_connected():
                return

            try:
                from tts.edge_tts_engine import synthesize_speech
                from config.settings import load_settings

                cfg = self.pipeline.config
                out_dir = cfg.tts_output_dir
                ts = int(time.time())
                out_path = out_dir / f"discord_{ts}.wav"

                wav_path = await asyncio.to_thread(
                    synthesize_speech,
                    text, out_path,
                    cfg.tts_voice, cfg.tts_rate, cfg.tts_volume,
                    self.pipeline.current_speaker, self.pipeline.current_pitch,
                )

                import discord.opus
                source = discord.FFmpegPCMAudio(str(wav_path))
                if vc.is_playing():
                    vc.stop()
                vc.play(source, after=lambda e: wav_path.unlink(missing_ok=True) if e is None else None)

            except Exception as exc:
                logger.error(f"Discord TTS speak error: {exc}")

        # ── Pipeline runner ───────────────────────────────────────────────────

        async def _run_pipeline(self, labelled_text: str) -> str:
            async with self._pipeline_lock:
                result: dict = {"text": "", "error": None}

                def on_response(_: str, assistant: str, elapsed: float) -> None:
                    result["text"] = assistant

                def on_error(exc: Exception) -> None:
                    result["error"] = str(exc)

                from core.pipeline import TurnCallbacks
                await asyncio.to_thread(
                    self.pipeline.process_turn,
                    labelled_text,
                    TurnCallbacks(on_response=on_response, on_error=on_error),
                )
                if result["error"]:
                    logger.error(f"Discord pipeline error: {result['error']}")
                return result["text"]

else:
    # Stub when discord.py not installed
    class VAIBot:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("discord.py not installed — run: pip install discord.py[voice] PyNaCl")


# ── Public API ────────────────────────────────────────────────────────────────

def create_bot(
    pipeline: "VTuberPipeline",
    token: str,
    chat_channel_id: int | None = None,
    owner_name: str = "EiX2",
    language: str = "th",
) -> "VAIBot | None":
    if not _DISCORD_AVAILABLE:
        logger.warning("discord.py not installed — Discord bot disabled")
        return None
    if not token:
        logger.warning("DISCORD_BOT_TOKEN not set — Discord bot disabled")
        return None
    global _bot
    _bot = VAIBot(pipeline, chat_channel_id, owner_name, language)
    return _bot


async def start_bot(bot: "VAIBot", token: str) -> None:
    try:
        await bot.start(token)
    except Exception as exc:
        logger.error(f"Discord bot error: {exc}")


def get_bot() -> "VAIBot | None":
    return _bot
