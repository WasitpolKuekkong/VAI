#!/usr/bin/env python3
"""Quick test of expression triggering flow"""

import asyncio
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from utils.vtuber_controller import (
    initialize_vtuber_controller,
    cleanup_vtuber_controller,
    _run_in_loop,
    trigger_expression,
    clear_expression,
)
from utils.logger import logger

def main():
    print("\n" + "="*60)
    print("VTuber Expression Flow Test")
    print("="*60)
    
    # Initialize controller (like main.py does)
    print("\n1️⃣  Initializing VTuber controller...")
    vtuber_ctrl = _run_in_loop(initialize_vtuber_controller())
    if not vtuber_ctrl:
        print("❌ Failed to initialize controller")
        return
    
    print(f"✅ Controller initialized")
    print(f"   WebSocket: {bool(vtuber_ctrl.websocket)}")
    print(f"   Auth token: {bool(vtuber_ctrl._auth_token)}")
    
    # Test each expression
    expressions = ["smile_happy", "angry", "sad", "brush"]
    print(f"\n2️⃣  Testing {len(expressions)} expressions...")
    
    for expr in expressions:
        print(f"\n   Testing: {expr}")
        success = trigger_expression(expr, controller=vtuber_ctrl)
        print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
        if success:
            # Hold expression for a moment
            import time
            time.sleep(1.0)
    
    # Clear expression
    print(f"\n3️⃣  Clearing expression...")
    success = clear_expression(controller=vtuber_ctrl)
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Cleanup
    print(f"\n4️⃣  Cleaning up...")
    _run_in_loop(cleanup_vtuber_controller())
    print("✅ Done")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    main()
