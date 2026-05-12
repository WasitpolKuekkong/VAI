# Backend Switching Feature - Implementation Summary

## Overview
Successfully implemented the ability to switch between **Google Gemini Flash** and **LM Studio** backends at runtime.

## Changes Made

### 1. **config/settings.py**
- Added `preferred_backend: str` field to `AppConfig` dataclass
- Loads from environment variable `PREFERRED_BACKEND` (defaults to "gemini")

### 2. **.env**
- Added `PREFERRED_BACKEND=gemini` configuration entry
- Can be changed to "lmstudio" to use LM Studio instead

### 3. **main.py**
Major updates:
- **New Imports**: Added `from google import genai` for Gemini SDK
- **New Function**: `chat_with_google_gemini()` - Uses Google Gemini 2.5 Flash with retry logic for rate limits
- **New Function**: `chat_with_backend()` - Wrapper that routes to appropriate backend based on config
- **New Function**: `chat_with_lm_studio()` - Moved/restructured from original code
- **New CLI Command**: `/backend <gemini|lmstudio>` - Switch backends at runtime
- **Startup Message**: Displays current backend and model information
- **Updated Error Handling**: Backend-agnostic error messages

### 4. **requirements.txt**
- Maintains `google-genai>=0.8.0` dependency

## Features

### CLI Commands Available:
```
/backend <gemini|lmstudio>    - Switch between backends
/speaker <name>               - Change TTS speaker
/pitch <value>                - Adjust pitch (semitones)
/speakers                     - List available speakers
/hotkeys                      - List VTuber hotkeys
```

### Backend Capabilities:

#### **Gemini Backend:**
- Model: `gemini-2.5-flash` (configurable)
- API: Google AI Studio (cloud-based)
- Retry Logic: Handles rate limiting (429) and service unavailability (503)
- Requires: `GOOGLE_AISTUDIO_API_KEY` environment variable

#### **LM Studio Backend:**
- Local HTTP API server
- URL: `http://127.0.0.1:1234` (configurable)
- Model: Configurable (default: `qwen/qwen3-4b`)
- Fast local inference without API keys

## Usage Example

```bash
# Start the application
python main.py

# You: hello
# AI: [Response from current backend - default Gemini]

# Switch to LM Studio
# You: /backend lmstudio
# ✓ Backend switched to: LM STUDIO (model: qwen/qwen3-4b)

# You: hello
# AI: [Response from LM Studio]

# Switch back to Gemini
# You: /backend gemini
# ✓ Backend switched to: GEMINI (model: gemini-2.5-flash)
```

## Configuration

### Setting Default Backend in .env:
```env
# Use Gemini as default
PREFERRED_BACKEND=gemini

# Or use LM Studio as default
PREFERRED_BACKEND=lmstudio
```

### Google Gemini Configuration:
```env
GOOGLE_AISTUDIO_API_KEY=your_api_key_here
GOOGLE_AISTUDIO_MODEL=gemini-2.5-flash
```

### LM Studio Configuration:
```env
LM_STUDIO_BASE_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3-4b
LM_STUDIO_TEMPERATURE=0.7
LM_STUDIO_MAX_TOKENS=512
```

## Implementation Details

### Retry Logic (Gemini):
- Max 4 attempts with exponential backoff
- 10s initial delay, doubles each retry (10s, 20s, 40s)
- Catches rate limit (429) and service unavailable (503) errors
- Logs warning with current attempt progress

### Error Handling:
- LM Studio: Raises `requests.RequestException` on HTTP errors
- Gemini: Returns empty string on final failure after retries
- Both: Log detailed error messages for debugging

## Files Modified
- `main.py` - Core logic
- `config/settings.py` - Configuration schema
- `.env` - Runtime settings

## Verification
✅ Python syntax validation passed
✅ All imports resolved
✅ Settings schema compatible
✅ CLI commands implemented
✅ Error handling robust

## Next Steps (Optional)
- Add persistent backend preference storage
- Add backend status indicator in subtitle
- Create web UI for backend selection
- Add backend performance metrics
