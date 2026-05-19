"""
Debug script to check VTuber Studio hotkeys and model status
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.vtuber_controller import VTuberStudioController, _get_hotkeys
from utils.logger import logger


async def get_model_info(controller):
    """Get current model info"""
    if not controller.websocket or not controller._auth_token:
        return None
    
    try:
        from utils.vtuber_controller import _send_request
        response = await _send_request(controller.websocket, "CurrentModelRequest")
        return response.get("data", {})
    except Exception as e:
        print(f"Error getting model info: {e}")
        return None


async def debug_hotkeys():
    """Debug hotkey fetching"""
    print("\n" + "="*80)
    print("VTUBER STUDIO HOTKEYS DEBUG")
    print("="*80 + "\n")
    
    try:
        ctrl = VTuberStudioController()
        
        # Connect
        print("1. Connecting to VTuber Studio...")
        if not await ctrl.connect():
            print("❌ Failed to connect!")
            return
        print("✓ Connected and authenticated\n")
        
        # Get model info
        print("2. Checking current model...")
        model_info = await get_model_info(ctrl)
        if model_info:
            model_name = model_info.get("modelName", "Unknown")
            model_id = model_info.get("modelID", "Unknown")
            print(f"✓ Current model: {model_name} (ID: {model_id})")
        else:
            print("❌ Could not get model info - model may not be loaded!")
            print("   → Load a model in VTuber Studio first!")
            return
        print()
        
        # Get hotkeys
        print("3. Fetching hotkeys for current model...")
        hotkeys = await _get_hotkeys(ctrl.websocket)
        
        if not hotkeys:
            print("❌ No hotkeys returned by API!")
            print("\n   Possible causes:")
            print("   1. ⚠️  No model is currently loaded in VTuber Studio")
            print("   2. ⚠️  Hotkeys are not assigned to the current model")
            print("   3. ⚠️  Hotkeys exist but are not in the API response")
            print("\n   Solution:")
            print("   → Make sure a model is loaded in VTuber Studio")
            print("   → Assign hotkeys to the current model (Settings → Hotkeys)")
            print("   → Try restarting VTuber Studio")
            await ctrl.disconnect()
            return
        
        print(f"✓ Found {len(hotkeys)} hotkeys:\n")
        
        for i, hotkey in enumerate(hotkeys, 1):
            name = hotkey.get('name', '<unnamed>')
            hotkey_id = hotkey.get('hotkeyID', '')
            file_name = hotkey.get('fileName') or hotkey.get('file') or ''
            hotkey_type = hotkey.get('type', '')
            
            print(f"{i}. Name: '{name}'")
            if hotkey_id:
                print(f"   ID: {hotkey_id}")
            if file_name:
                print(f"   File: {file_name}")
            if hotkey_type:
                print(f"   Type: {hotkey_type}")
            print()
        
        # Show how to use
        print("="*80)
        print("HOW TO USE IN CODE:")
        print("="*80)
        print("\nFrom the hotkeys above, use the exact 'Name' value:\n")
        for hotkey in hotkeys[:3]:
            name = hotkey.get('name', '')
            if name:
                print(f"  trigger_expression('{name}')")
        
        await ctrl.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception(e)


def main():
    asyncio.run(debug_hotkeys())


if __name__ == "__main__":
    main()
