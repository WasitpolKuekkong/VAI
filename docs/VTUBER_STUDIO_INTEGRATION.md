# VTuber Studio API Integration Guide

## Overview

This integration provides WebSocket-based control of VTuber Studio avatars from your VAI system. You can synchronize avatar expressions, mouth movements, and animations with text-to-speech output and chat interactions.

## Quick Start

### 1. Prerequisites

- **VTuber Studio** running on your system (default: `localhost:8001`)
- **websockets** Python library: `pip install websockets`

### 2. Configuration

Add to your `.env` file:

```env
# VTuber Studio Integration
VTUBER_STUDIO_API_URL=ws://localhost:8001
VTUBER_STUDIO_AUTH_TOKEN=
VTUBER_STUDIO_ENABLED=true
```

### 3. Run the Demo

```bash
# Test basic connectivity
python scripts/vtubestudio_connect.py

# Run specific demo
python scripts/vtubestudio_connect.py --demo expressions

# Interactive mode for manual testing
python scripts/vtubestudio_connect.py --demo interactive

# With custom API endpoint
python scripts/vtubestudio_connect.py --api-url ws://localhost:8001
```

## VTuber Studio API Reference

### Supported Expressions

The demo script can set these common expressions:

- `Happy` - Smiling expression
- `Sad` - Sad expression
- `Angry` - Angry expression
- `Surprised` - Surprised/shocked expression
- `Neutral` - Neutral/normal face

**Note:** Available expressions depend on your avatar model. Use the interactive demo to discover your avatar's available expressions.

### Supported Animations/Parameters

- `Mouth_Open` - Mouth opening animation (0.0 = closed, 1.0 = fully open)
- `Eye_Blink` - Eye blink animation
- `Idle` - Idle animation loop
- Other blend shapes depend on your avatar

## Usage Examples

### Example 1: Basic Demo

```python
import asyncio
from scripts.vtubestudio_connect import VTuberStudioAPI

async def main():
    vts = VTuberStudioAPI("ws://localhost:8001")
    if await vts.connect():
        await vts.set_expression("Happy")
        await vts.animate_parameter("Mouth_Open", 0.8, duration=0.5)
        await vts.disconnect()

asyncio.run(main())
```

### Example 2: Integration into main.py

```python
from utils.vtuber_controller import initialize_vtuber_controller, get_vtuber_controller

# In your main initialization
vtuber_ctrl = await initialize_vtuber_controller()

# When processing chat responses
if vtuber_ctrl:
    # Show thinking expression
    await vtuber_ctrl.respond_to_emotion("thinking")
    
    # During TTS playback
    await vtuber_ctrl.animate_mouth(0.8, duration=0.3)

# Cleanup on exit
await cleanup_vtuber_controller()
```

### Example 3: Emotion-based Responses

```python
async def show_emotion(emotion: str):
    vtuber_ctrl = get_vtuber_controller()
    if vtuber_ctrl:
        await vtuber_ctrl.respond_to_emotion(emotion)

# Usage
await show_emotion("happy")    # Shows happy expression
await show_emotion("sad")      # Shows sad expression
await show_emotion("thinking") # Shows neutral (thinking) expression
```

## API Classes Reference

### VTuberStudioAPI (scripts/vtubestudio_connect.py)

Main WebSocket client for VTuber Studio API.

**Methods:**

```python
async connect() -> bool
    Connect to VTuber Studio WebSocket API

async disconnect()
    Disconnect from VTuber Studio

async get_api_version() -> dict | None
    Get API version information

async get_state() -> dict | None
    Get current avatar state

async set_expression(expression_name: str) -> bool
    Set avatar expression

async animate_parameter(parameter_name: str, target_value: float, duration: float) -> bool
    Smoothly animate a blend shape parameter

async set_idle_animation(enable: bool) -> bool
    Enable or disable idle animation
```

### VTuberStudioController (utils/vtuber_controller.py)

Simplified controller for main pipeline integration.

**Methods:**

```python
async connect() -> bool
    Connect to VTuber Studio

async disconnect()
    Disconnect from VTuber Studio

async set_expression(expression_name: str) -> bool
    Set avatar expression

async animate_mouth(open_value: float, duration: float) -> bool
    Animate mouth opening

async animate_eye_blink() -> bool
    Play eye blink animation

async respond_to_emotion(emotion: str) -> bool
    Change expression based on emotion (happy, sad, angry, surprised, thinking, neutral)
```

## Advanced Topics

### Custom Blend Shapes

If your avatar has custom blend shapes, you can control them:

```python
vts = VTuberStudioAPI()
await vts.connect()

# Control custom blend shape
await vts.animate_parameter("CustomBlendShape", 0.5, duration=1.0)

await vts.disconnect()
```

### Multi-step Animations

```python
async def complex_animation(vts: VTuberStudioAPI):
    """Example: Simulate talking"""
    # Open mouth gradually
    await vts.animate_parameter("Mouth_Open", 0.8, duration=0.5)
    
    # Simulate jaw movement
    await vts.animate_parameter("Jaw_Forward", 0.3, duration=0.3)
    
    # Close mouth
    await vts.animate_parameter("Mouth_Open", 0.0, duration=0.4)
```

### Error Handling

```python
import asyncio

try:
    vts = VTuberStudioAPI()
    if await vts.connect():
        result = await vts.set_expression("Happy")
        if result:
            print("✅ Expression changed")
        else:
            print("⚠️  Expression change timed out")
    else:
        print("❌ Could not connect to VTuber Studio")
except Exception as e:
    print(f"Error: {e}")
finally:
    await vts.disconnect()
```

## Troubleshooting

### Connection Issues

**Problem:** "Connection failed: Connection refused"

**Solution:**
1. Ensure VTuber Studio is running
2. Check VTuber Studio is listening on port 8001
3. Verify firewall allows localhost connections
4. Try: `VTUBER_STUDIO_API_URL=ws://127.0.0.1:8001`

### Expression Not Changing

**Problem:** Expression parameter sent but avatar doesn't change

**Solution:**
1. Verify expression name matches your avatar's available expressions
2. Use interactive demo to list available expressions
3. Check if avatar model supports the expression
4. Try sending multiple parameter updates in sequence

### Response Timeout

**Problem:** "⏱️ Response timeout for [function_name]"

**Solution:**
1. Check network latency
2. Verify VTuber Studio is responsive
3. Try increasing timeout in code
4. Reduce number of simultaneous requests

## Configuration Reference

### .env Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VTUBER_STUDIO_API_URL` | WebSocket endpoint | `ws://localhost:8001` |
| `VTUBER_STUDIO_AUTH_TOKEN` | Authentication token (if required) | `` |
| `VTUBER_STUDIO_ENABLED` | Enable/disable integration | `true` |

### Code Configuration

```python
from config.settings import load_settings

config = load_settings()
print(config.vtuber_studio_api_url)      # ws://localhost:8001
print(config.vtuber_studio_enabled)      # True
print(config.vtuber_studio_auth_token)   # ""
```

## Demo Modes

### Mode: `basic`

Tests basic API calls (version, state).

```bash
python scripts/vtubestudio_connect.py --demo basic
```

### Mode: `expressions`

Cycles through different avatar expressions (Happy, Sad, Angry, Neutral, Surprised).

```bash
python scripts/vtubestudio_connect.py --demo expressions
```

### Mode: `animation`

Demonstrates smooth parameter animation (mouth, eye blink).

```bash
python scripts/vtubestudio_connect.py --demo animation
```

### Mode: `talking`

Simulates talking animation with synchronized mouth movements.

```bash
python scripts/vtubestudio_connect.py --demo talking
```

### Mode: `interactive`

Interactive shell for manual avatar control.

```bash
python scripts/vtubestudio_connect.py --demo interactive

# Commands:
$ expression Happy
$ animate Mouth_Open 0.8
$ blink
$ talk
$ state
$ quit
```

### Mode: `all` (default)

Runs all demos in sequence.

```bash
python scripts/vtubestudio_connect.py
```

## Future Integration Ideas

1. **Emotion Detection**: Analyze chat response to auto-set avatar emotion
2. **Lip Sync**: Synchronize mouth movements to TTS audio
3. **Head Tracking**: Follow voice input direction
4. **Multi-Avatar**: Control multiple avatars
5. **Gesture System**: Link specific commands to avatar gestures
6. **Status Display**: Update subtitle.txt based on avatar state

## File Structure

```
VAI/
├── config/
│   └── settings.py           # Configuration (includes VTUBER_STUDIO_*)
├── utils/
│   └── vtuber_controller.py  # Simple integration controller
├── scripts/
│   └── vtubestudio_connect.py  # Main demo and API client
└── .env                       # Environment variables
```

## License & Attribution

This integration uses the VTuber Studio WebSocket API.

For more information about VTuber Studio:
- Official Site: https://denchisoft.com/
- Documentation: Check your VTuber Studio installation

## Support

For issues with this integration:
1. Check the Troubleshooting section above
2. Run `--demo interactive` to verify API connectivity
3. Check logs from `utils/logger.py`
4. Verify `.env` configuration
