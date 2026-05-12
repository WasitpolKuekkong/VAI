"""
VTuber Studio API - Connection Test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import websockets
except ImportError:
    print("❌ websockets library not found. Install with: pip install websockets")
    sys.exit(1)

from config.settings import load_settings
from utils.logger import logger

config = load_settings()

API_NAME = "VTubeStudioPublicAPI"
API_VERSION = "1.0"
PLUGIN_NAME = "VAI Demo"
PLUGIN_DEVELOPER = "Copilot"

EXPRESSION_SEQUENCE = ["angry", "brush", "sad", "smile_happy"]
EXPRESSION_HOLD_SECONDS = 3.0


async def send_request(
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


async def authenticate(
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
        logger.info("🔐 Using authentication token from .env...")
        response = await send_request(websocket, "AuthenticationRequest", {
            **auth_data,
            "authenticationToken": auth_token,
        })
        logger.info(f"📥 Authentication response:\n{json.dumps(response, indent=2)}")
        if response.get("messageType") == "AuthenticationResponse":
            return auth_token

        logger.warning("⚠️  Saved token was rejected, requesting a new one...")

    logger.info("🔑 Requesting a new authentication token...")
    token_response = await send_request(websocket, "AuthenticationTokenRequest", auth_data)
    logger.info(f"📥 Token response:\n{json.dumps(token_response, indent=2)}")

    token_data = token_response.get("data", {})
    new_token = token_data.get("authenticationToken")
    if not new_token:
        return None

    logger.info("🔐 Sending authentication request with the new token...")
    auth_response = await send_request(websocket, "AuthenticationRequest", {
        **auth_data,
        "authenticationToken": new_token,
    })
    logger.info(f"📥 Authentication response:\n{json.dumps(auth_response, indent=2)}")

    if auth_response.get("messageType") == "AuthenticationResponse":
        return new_token

    return None


async def get_hotkeys(websocket: Any) -> list[dict[str, Any]]:
    response = await send_request(websocket, "HotkeysInCurrentModelRequest")
    logger.info(f"📥 Hotkeys response:\n{json.dumps(response, indent=2)}")
    data = response.get("data", {})
    return data.get("availableHotkeys", []) or data.get("hotkeys", []) or []


async def trigger_hotkey(websocket: Any, hotkey_id: str) -> bool:
    response = await send_request(websocket, "HotkeyTriggerRequest", {"hotkeyID": hotkey_id})
    logger.info(f"📥 Hotkey trigger response:\n{json.dumps(response, indent=2)}")
    return response.get("messageType") == "HotkeyTriggerResponse"


def _normalize_expression_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _find_hotkey_id(hotkeys: list[dict[str, Any]], expression_name: str) -> str | None:
    target = _normalize_expression_name(expression_name)
    for hotkey in hotkeys:
        hotkey_name = _normalize_expression_name(str(hotkey.get("name", "")))
        file_name = _normalize_expression_name(str(hotkey.get("fileName", "")))
        hotkey_id = str(hotkey.get("hotkeyID", "")).strip()
        if target and (target == hotkey_name or target == file_name):
            return hotkey_id or None
    return None


async def connect_test(api_url: str | None = None, auth_token: str | None = None) -> bool:
    """Connect to VTuber Studio and complete the public API authentication handshake."""

    api_url = api_url or config.vtuber_studio_api_url
    auth_token = auth_token or config.vtuber_studio_auth_token

    try:
        logger.info(f"🔗 Connecting to {api_url}...")

        async with websockets.connect(api_url) as websocket:
            logger.info("✅ Connection successful!")

            token = await authenticate(websocket, auth_token=auth_token)
            if not token:
                logger.error("❌ Authentication failed")
                return False

            logger.info("✅ Authentication successful")
            state_response = await send_request(websocket, "APIStateRequest")
            logger.info(f"📥 API state response:\n{json.dumps(state_response, indent=2)}")

            if state_response.get("messageType") in {"APIStateResponse", "AuthenticationResponse"}:
                return True

            return False

    except asyncio.TimeoutError:
        logger.error("❌ Connection timeout - VTuber Studio not responding")
        return False
    except ConnectionRefusedError:
        logger.error(f"❌ Connection refused - Is VTuber Studio running on {api_url}?")
        return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False


async def run_expression_test(api_url: str | None = None, auth_token: str | None = None) -> bool:
    """Connect, authenticate, and trigger the expression hotkeys in sequence."""

    api_url = api_url or config.vtuber_studio_api_url
    auth_token = auth_token or config.vtuber_studio_auth_token

    try:
        logger.info(f"🔗 Connecting to {api_url}...")

        async with websockets.connect(api_url) as websocket:
            logger.info("✅ Connection successful!")

            token = await authenticate(websocket, auth_token=auth_token)
            if not token:
                logger.error("❌ Authentication failed")
                return False

            logger.info("✅ Authentication successful")
            hotkeys = await get_hotkeys(websocket)
            if not hotkeys:
                logger.error("❌ No hotkeys found in the current model")
                return False

            logger.info(f"✅ Found {len(hotkeys)} hotkeys")

            matched_hotkeys: list[tuple[str, str]] = []
            for expression_name in EXPRESSION_SEQUENCE:
                hotkey_id = _find_hotkey_id(hotkeys, expression_name)
                if hotkey_id:
                    matched_hotkeys.append((expression_name, hotkey_id))
                else:
                    logger.warning(f"⚠️  Expression hotkey not found: {expression_name}")

            if not matched_hotkeys:
                logger.warning("⚠️  No named expression hotkeys matched. Falling back to all available hotkeys in model order.")
                matched_hotkeys = [
                    (
                        str(hotkey.get("name") or hotkey.get("file") or hotkey.get("description") or f"hotkey_{index + 1}"),
                        str(hotkey.get("hotkeyID", "")).strip(),
                    )
                    for index, hotkey in enumerate(hotkeys)
                    if str(hotkey.get("hotkeyID", "")).strip()
                ]

            for expression_name, hotkey_id in matched_hotkeys:
                logger.info(f"🎭 Triggering expression: {expression_name} ({hotkey_id})")
                if not await trigger_hotkey(websocket, hotkey_id):
                    logger.warning(f"⚠️  Failed to trigger: {expression_name}")
                    continue

                await asyncio.sleep(EXPRESSION_HOLD_SECONDS)

            return True

    except asyncio.TimeoutError:
        logger.error("❌ Connection timeout - VTuber Studio not responding")
        return False
    except ConnectionRefusedError:
        logger.error(f"❌ Connection refused - Is VTuber Studio running on {api_url}?")
        return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="VTuber Studio API connection test")
    parser.add_argument("--api-url", default=config.vtuber_studio_api_url, help="VTuber Studio WebSocket URL")
    parser.add_argument("--token", default=config.vtuber_studio_auth_token, help="Saved authentication token")
    parser.add_argument("--mode", choices=["connect", "expression"], default="connect", help="Test mode")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("VTuber Studio API - Connection Test")
    print("=" * 60)
    print(f"API URL: {args.api_url}\n")

    if args.mode == "expression":
        success = await run_expression_test(api_url=args.api_url, auth_token=args.token)
    else:
        success = await connect_test(api_url=args.api_url, auth_token=args.token)

    print("\n" + "=" * 60)
    if success:
        print("✅ Connection Test PASSED")
    else:
        print("❌ Connection Test FAILED")
        print("\nTroubleshooting:")
        print("1. Make sure VTuber Studio is running")
        print("2. Approve the plugin/auth request inside VTuber Studio if prompted")
        print("3. Check the API URL and port")
        print("4. Update VTUBER_STUDIO_API_URL in .env if needed")
        print("5. If expressions are missing, make sure the model has hotkeys named angry, brush, sad, and smile_happy")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
