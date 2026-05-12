"""
VTuber Studio Integration Helper
Provides functions to control avatar from main chat pipeline
"""

from __future__ import annotations

import asyncio
import json
import uuid
import re
from typing import Any
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

from config.settings import load_settings
from utils.logger import logger


API_NAME = "VTubeStudioPublicAPI"
API_VERSION = "1.0"
PLUGIN_NAME = "VAI Demo"
PLUGIN_DEVELOPER = "Copilot"

BASE_DIR = PROJECT_ROOT
ENV_FILE = BASE_DIR / ".env"

DEFAULT_EXPRESSION_NAMES = ("angry", "brush", "sad", "smile_happy", "smug")
DEFAULT_CLEAR_NAMES = ("", "neutral", "clear", "reset", "idle")


async def _send_request(
    websocket: Any,
    message_type: str,
    data: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    request_id = request_id or uuid.uuid4().hex
    payload = {
        "apiName": API_NAME,
        "apiVersion": API_VERSION,
        "requestID": request_id,
        "messageType": message_type,
        "data": data or {},
    }
    await websocket.send(json.dumps(payload))
    response_raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    return json.loads(response_raw)


async def _authenticate(
    websocket: Any,
    auth_token: str | None = None,
    plugin_name: str = PLUGIN_NAME,
    plugin_developer: str = PLUGIN_DEVELOPER,
) -> str | None:
    auth_data = {
        "pluginName": plugin_name,
        "pluginDeveloper": plugin_developer,
    }

    if auth_token:
        try:
            response = await _send_request(websocket, "AuthenticationRequest", {
                **auth_data,
                "authenticationToken": auth_token,
            })
            if response.get("messageType") == "AuthenticationResponse":
                return auth_token
        except asyncio.TimeoutError:
            logger.debug("Auth token validation timed out")

    try:
        logger.debug("🔑 Requesting new authentication token...")
        token_response = await _send_request(websocket, "AuthenticationTokenRequest", auth_data)
        token_data = token_response.get("data", {})
        new_token = token_data.get("authenticationToken")
        if not new_token:
            logger.warning("⚠️  No token received - approve plugin in VTuber Studio UI")
            return None

        auth_response = await _send_request(websocket, "AuthenticationRequest", {
            **auth_data,
            "authenticationToken": new_token,
        })
        if auth_response.get("messageType") == "AuthenticationResponse":
            _persist_auth_token(new_token)
            return new_token

        return None
    except asyncio.TimeoutError:
        logger.warning("⚠️  Authentication timed out - approve plugin in VTuber Studio UI and retry")
        return None


def _persist_auth_token(auth_token: str) -> None:
    """Persist the auth token to .env so the approval prompt is only needed once."""
    if not auth_token:
        return

    env_line = f"VTUBER_STUDIO_AUTH_TOKEN={auth_token}"
    try:
        if ENV_FILE.exists():
            content = ENV_FILE.read_text(encoding="utf-8")
            lines = content.splitlines()
            updated = False
            for index, line in enumerate(lines):
                if line.startswith("VTUBER_STUDIO_AUTH_TOKEN="):
                    lines[index] = env_line
                    updated = True
                    break
            if not updated:
                lines.append(env_line)
            ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            ENV_FILE.write_text(env_line + "\n", encoding="utf-8")
        logger.info("🔐 Saved VTuber Studio auth token to .env")
    except Exception as exc:
        logger.warning(f"⚠️  Could not save VTuber Studio auth token: {exc}")


async def _get_hotkeys(websocket: Any) -> list[dict[str, Any]]:
    response = await _send_request(websocket, "HotkeysInCurrentModelRequest")
    data = response.get("data", {})
    return data.get("availableHotkeys", []) or data.get("hotkeys", []) or []


async def _trigger_hotkey(websocket: Any, hotkey_id: str) -> bool:
    response = await _send_request(websocket, "HotkeyTriggerRequest", {"hotkeyID": hotkey_id})
    return response.get("messageType") == "HotkeyTriggerResponse"


def _normalize_expression_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _find_hotkey_id(hotkeys: list[dict[str, Any]], expression_name: str) -> str | None:
    target = _normalize_expression_name(expression_name)
    for hotkey in hotkeys:
        hotkey_name = _normalize_expression_name(str(hotkey.get("name", "")))
        file_name_raw = str(hotkey.get("fileName") or hotkey.get("file") or "")
        file_name = _normalize_expression_name(file_name_raw)
        if file_name.endswith(".exp3.json"):
            file_name = file_name[:-10]
        hotkey_id = str(hotkey.get("hotkeyID", "")).strip()
        hotkey_type = _normalize_expression_name(str(hotkey.get("type", "")))

        # For clear, only match explicit clear/remove-all entries.
        if target == "":
            if hotkey_name == "" or hotkey_type == "removeallexpressions":
                return hotkey_id or None
            continue

        # Normal expression matching by exact name or backing expression file.
        if target == hotkey_name or target == file_name:
            return hotkey_id or None

        # Fallback fuzzy matching: allow substring and prefix/suffix matches
        if target and (target in hotkey_name or target in file_name or hotkey_name.startswith(target) or hotkey_name.endswith(target)):
            return hotkey_id or None

        # Support numeric '1num' style shortcuts by mapping to default list
        m = re.match(r"^(\d+)(num)?$", target)
        if m:
            try:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(DEFAULT_EXPRESSION_NAMES):
                    desired = _normalize_expression_name(DEFAULT_EXPRESSION_NAMES[idx])
                    if desired == hotkey_name or desired == file_name:
                        return hotkey_id or None
            except Exception:
                pass
    return None


def list_hotkeys(controller: 'VTuberStudioController | None' = None) -> list[dict[str, Any]]:
    """Return a list of available hotkeys (wrapper for sync callers)."""
    if controller is None:
        controller = VTuberStudioController()
    return _run_in_loop(controller._list_hotkeys() if hasattr(controller, "_list_hotkeys") else _list_hotkeys_for_controller(controller))


async def _list_hotkeys_for_controller(controller: 'VTuberStudioController') -> list[dict[str, Any]]:
    if not controller.websocket or not controller._auth_token:
        if not await controller.connect():
            return []
    return await _get_hotkeys(controller.websocket)


async def _trigger_expression_async(
    expression_names: tuple[str, ...],
    api_url: str | None = None,
    auth_token: str | None = None,
) -> bool:
    config = load_settings()
    api_url = api_url or config.vtuber_studio_api_url
    auth_token = auth_token or config.vtuber_studio_auth_token

    if not config.vtuber_studio_enabled or not websockets:
        return False

    try:
        async with websockets.connect(api_url) as websocket:
            token = await _authenticate(websocket, auth_token=auth_token)
            if not token:
                logger.warning("⚠️  VTuber Studio authentication failed")
                return False

            hotkeys = await _get_hotkeys(websocket)
            for expression_name in expression_names:
                hotkey_id = _find_hotkey_id(hotkeys, expression_name)
                if hotkey_id:
                    logger.info(f"🎭 Triggering VTuber Studio expression: {expression_name}")
                    return await _trigger_hotkey(websocket, hotkey_id)

            logger.warning(f"⚠️  No VTuber Studio expression hotkey matched: {', '.join(expression_names)}")
            return False
    except Exception as exc:
        logger.warning(f"⚠️  VTuber Studio expression request failed: {exc}")
        return False


_persistent_loop: asyncio.AbstractEventLoop | None = None


def _run_in_loop(coro):
    """Helper to run coroutine in persistent event loop (never closes)."""
    global _persistent_loop
    
    if _persistent_loop is None or _persistent_loop.is_closed():
        _persistent_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_persistent_loop)
    
    return _persistent_loop.run_until_complete(coro)


def trigger_expression(
    expression_name: str,
    api_url: str | None = None,
    auth_token: str | None = None,
    controller: 'VTuberStudioController | None' = None,
) -> bool:
    """Trigger a VTuber Studio expression hotkey.
    
    Args:
        expression_name: Name of the expression to trigger
        api_url: Optional API URL (used if controller not provided)
        auth_token: Optional auth token (used if controller not provided)
        controller: Optional existing VTuberStudioController to reuse connection
    """
    if not controller:
        # Create temporary controller if none provided
        controller = VTuberStudioController(api_url=api_url, auth_token=auth_token)
    
    # Let controller handle reconnection if needed
    return _run_in_loop(controller.set_expression(expression_name))


def clear_expression(
    api_url: str | None = None,
    auth_token: str | None = None,
    clear_names: tuple[str, ...] | None = None,
    controller: 'VTuberStudioController | None' = None,
) -> bool:
    """Trigger a VTuber Studio clear/neutral hotkey.
    
    Args:
        api_url: Optional API URL (used if controller not provided)
        auth_token: Optional auth token (used if controller not provided)
        clear_names: Optional tuple of clear expression names to try
        controller: Optional existing VTuberStudioController to reuse connection
    """
    names = clear_names or DEFAULT_CLEAR_NAMES
    
    if not controller:
        # Create temporary controller if none provided
        controller = VTuberStudioController(api_url=api_url, auth_token=auth_token)
    
    # Let controller handle reconnection if needed
    return _run_in_loop(controller.clear_expression(names))


class VTuberStudioController:
    """Simple VTuber Studio avatar controller for integration into main pipeline"""

    def __init__(self, api_url: str | None = None, auth_token: str | None = None):
        config = load_settings()
        self.api_url = api_url or config.vtuber_studio_api_url
        self.auth_token = auth_token or config.vtuber_studio_auth_token
        self.enabled = config.vtuber_studio_enabled
        self.websocket: Any | None = None
        self._auth_token: str | None = None
        self.current_expression: str | None = None

    async def connect(self) -> bool:
        """Connect and authenticate with VTuber Studio"""
        if not self.enabled or not websockets:
            return False

        try:
            logger.debug(f"🔗 Connecting to {self.api_url}...")
            self.websocket = await websockets.connect(self.api_url)
            logger.debug(f"✅ WebSocket connected")
            
            # Authenticate immediately after connecting
            self._auth_token = await _authenticate(self.websocket, auth_token=self.auth_token)
            if not self._auth_token:
                logger.warning("⚠️  Authentication failed - expressions won't work")
                await self.disconnect()
                return False
            
            logger.info(f"✅ VTuber Studio authenticated: {self.api_url}")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Connection timeout to {self.api_url}")
            self.websocket = None
            return False
        except Exception as e:
            logger.warning(f"⚠️  Could not connect to VTuber Studio: {e}")
            self.websocket = None
            return False

    async def disconnect(self):
        """Disconnect from VTuber Studio"""
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
            self._auth_token = None
            self.current_expression = None

    async def clear_expression(self, clear_names: tuple[str, ...] | None = None) -> bool:
        """Clear the current expression by trying known clear hotkeys."""
        clear_candidates = clear_names or DEFAULT_CLEAR_NAMES
        for candidate in clear_candidates:
            logger.debug(f"🎭 Trying clear expression candidate: {candidate or 'remove_all'}")
            if await self.set_expression(candidate):
                return True
        logger.warning("⚠️  No clear expression hotkey matched")
        return False

    async def set_expression(self, expression_name: str) -> bool:
        """Set avatar expression hotkey"""
        if not self.websocket or not self._auth_token:
            # Try to reconnect if not authenticated
            if not await self.connect():
                return False

        target_expression = expression_name.strip()
        is_clear_expression = target_expression == ""

        async def _attempt_trigger() -> bool:
            logger.debug(f"🎭 Getting hotkeys...")
            hotkeys = await _get_hotkeys(self.websocket)
            if not hotkeys:
                logger.warning("⚠️  No hotkeys available")
                return False

            hotkey_id = _find_hotkey_id(hotkeys, expression_name)
            if not hotkey_id:
                logger.debug(f"⚠️  Expression '{expression_name}' not found in {len(hotkeys)} hotkeys")
                return False

            logger.info(f"🎭 Triggering expression: {expression_name or 'clear'}")
            success = await _trigger_hotkey(self.websocket, hotkey_id)
            if success:
                self.current_expression = None if is_clear_expression else target_expression
                logger.info(f"🎭 Current VTuber expression: {self.current_expression or 'clear'}")
                logger.debug(f"✅ Expression triggered: {expression_name or 'clear'}")
            else:
                logger.warning(f"⚠️  Failed to trigger: {expression_name}")
            return success

        try:
            return await _attempt_trigger()
        except asyncio.TimeoutError:
            logger.warning(f"⏱️  Timeout during expression trigger")
            await self.disconnect()
            return False
        except Exception as e:
            error_name = type(e).__name__
            error_text = str(e)
            if "ConnectionClosed" in error_name or "1002" in error_text or "protocol error" in error_text.lower():
                logger.warning(f"⚠️  VTuber connection dropped during '{expression_name}' ({error_name}: {e}). Reconnecting once...")
                await self.disconnect()
                if await self.connect():
                    try:
                        return await _attempt_trigger()
                    except Exception as retry_error:
                        logger.warning(f"⚠️  Retry failed for '{expression_name}': {type(retry_error).__name__}: {retry_error}")
                        await self.disconnect()
                        return False
                return False
            logger.warning(f"⚠️  Expression error: {error_name}: {e}")
            await self.disconnect()
            return False


# Singleton instance for easy access from main.py
_vtuber_controller: VTuberStudioController | None = None


async def initialize_vtuber_controller() -> VTuberStudioController | None:
    """Initialize and connect VTuber Studio controller"""
    global _vtuber_controller
    _vtuber_controller = VTuberStudioController()
    if await _vtuber_controller.connect():
        return _vtuber_controller
    return None


def get_vtuber_controller() -> VTuberStudioController | None:
    """Get the VTuber Studio controller instance"""
    return _vtuber_controller


async def cleanup_vtuber_controller():
    """Clean up VTuber Studio connection"""
    global _vtuber_controller
    if _vtuber_controller:
        await _vtuber_controller.disconnect()
        _vtuber_controller = None
