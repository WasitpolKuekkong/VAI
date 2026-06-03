from __future__ import annotations

import asyncio
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Awaitable, Callable

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

from utils.logger import logger

RESTREAM_AUTH_URL = "https://api.restream.io/login"
RESTREAM_TOKEN_URL = "https://api.restream.io/oauth/token"
RESTREAM_CHAT_WS = "wss://chat.api.restream.io/ws"

_running = False


def build_auth_url(client_id: str, redirect_uri: str) -> str:
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": secrets.token_urlsafe(16),
    })
    return f"{RESTREAM_AUTH_URL}?{params}"


def exchange_code_sync(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange OAuth authorization code for access token.
    Sync — intended to be called via asyncio.to_thread."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(RESTREAM_TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise RuntimeError(f"Restream token exchange {exc.code}: {detail}") from exc


def is_connected() -> bool:
    return _running


def disconnect() -> None:
    global _running
    _running = False


def _extract_platform(connection_id: str) -> str:
    """Extract platform from connectionIdentifier like '11341151-twitch-846559714'."""
    parts = connection_id.split("-")
    # Format: {channelId}-{platform}-{userId} — platform is the middle segment
    if len(parts) >= 3:
        return parts[1].lower()
    if len(parts) == 2:
        return parts[0].lower()
    return "restream"


def normalize_message(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize different Restream payload shapes into a consistent format.
    Returns None for non-chat events (joins, gifts, etc.)
    """
    logger.debug(f"🔴 Restream raw payload: {json.dumps(payload)[:400]}")

    # ── Format D (actual Restream WS): { connectionIdentifier, eventPayload: {author, text} }
    if "eventPayload" in payload:
        ep = payload["eventPayload"]
        text = ep.get("text") or ep.get("message") or ep.get("body", "")
        if not text:
            return None  # non-chat event (sub, follow, etc.)
        author = ep.get("author") or {}
        platform = _extract_platform(payload.get("connectionIdentifier", ""))
        return {
            "id": payload.get("eventId") or ep.get("id"),
            "text": text,
            "author": {
                "displayName": (
                    author.get("displayName")
                    or author.get("name")
                    or author.get("login")
                    or "Unknown"
                ),
                "type": platform,
                "avatar": author.get("avatar") or author.get("avatarUrl") or author.get("profileImageUrl"),
            },
            "timestamp": ep.get("timestamp") or payload.get("eventId"),
            "channelId": payload.get("connectionIdentifier"),
        }

    # ── Format A: { author: {displayName, type}, text, id } ─────────────────
    if "author" in payload and "text" in payload:
        author = payload["author"]
        return {
            "id": payload.get("id"),
            "text": payload["text"],
            "author": {
                "displayName": author.get("displayName") or author.get("name") or "Unknown",
                "type": author.get("type") or author.get("platform") or "restream",
                "avatar": author.get("avatar") or author.get("avatarUrl"),
            },
            "timestamp": payload.get("timestamp"),
            "channelId": payload.get("channelId"),
        }

    # ── Format B: { chatMessage: {authorName, text}, channel: {platform} } ──
    if "chatMessage" in payload:
        cm = payload["chatMessage"]
        ch = payload.get("channel", {})
        if not cm.get("text"):
            return None
        return {
            "id": cm.get("id"),
            "text": cm["text"],
            "author": {
                "displayName": cm.get("authorName") or cm.get("displayName") or "Unknown",
                "type": ch.get("platform") or ch.get("type") or "restream",
                "avatar": cm.get("authorAvatar") or cm.get("avatar"),
            },
            "timestamp": cm.get("timestamp"),
            "channelId": cm.get("channelId") or ch.get("id"),
        }

    # ── Format C: flat { authorName, platform, text } ────────────────────────
    if "authorName" in payload and "text" in payload:
        return {
            "id": payload.get("id"),
            "text": payload["text"],
            "author": {
                "displayName": payload.get("authorName") or "Unknown",
                "type": payload.get("platform") or payload.get("channelType") or "restream",
                "avatar": payload.get("authorAvatar") or payload.get("avatar"),
            },
            "timestamp": payload.get("timestamp"),
            "channelId": payload.get("channelId"),
        }

    logger.warning(f"🔴 Restream unknown message format: {json.dumps(payload)[:600]}")
    return None


async def start_chat_listener(
    access_token: str,
    on_message: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Connect to Restream chat WebSocket and call on_message for each chat event.
    Runs until disconnect() is called or the connection drops."""
    global _running
    if not websockets:
        raise RuntimeError("websockets library is not installed")

    url = f"{RESTREAM_CHAT_WS}?accessToken={access_token}"
    _running = True
    logger.info("🔴 Connecting to Restream chat WebSocket...")

    try:
        async with websockets.connect(url, ping_interval=20) as ws:
            logger.info("🔴 Restream chat connected")
            while _running:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=35)
                    payload = json.loads(raw)
                    action = payload.get("action")
                    if action == "event":
                        msg = normalize_message(payload.get("payload", {}))
                        if msg:
                            await on_message(msg)
                    elif action == "ping":
                        await ws.send(json.dumps({"action": "pong"}))
                except asyncio.TimeoutError:
                    pass  # websockets ping_interval handles keepalive
                except Exception as exc:
                    if _running:
                        logger.warning(f"⚠️  Restream recv error: {exc}")
                    break
    except Exception as exc:
        logger.warning(f"⚠️  Restream connection failed: {exc}")
    finally:
        _running = False
        logger.info("🔴 Restream chat disconnected")
