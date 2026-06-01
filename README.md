# 🎭 VAI - AI VTuber Chat System

VAI is a comprehensive Windows-based AI VTuber chat pipeline. It combines conversational AI, text-to-speech synthesis, voice conversion, and avatar expression control into one integrated system.

## 🌟 What It Does

- 🤖 **Chat with AI** - Google Gemini or Local LM Studio backend
- 💬 **Conversation Memory** - Full chat history with context awareness
- 🎤 **Speech Synthesis** - Edge TTS with voice presets and pitch control
- 🎙️ **Voice Conversion** - Optional Applio/RVC for voice transformation
- 🎭 **Avatar Control** - VTuber Studio integration for expression sync
- 😠 **Emotion Detection** - Automatic Thai sentiment analysis
- 🎯 **Dual Interface** - CLI mode or Desktop GUI
- 👤 **Voice Recognition** - Optional speaker identification

## 📋 Requirements

- **Windows 10/11**
- **Python 3.10+** recommended
- **ffmpeg** installed and on PATH
- **One of:**
  - LM Studio running locally with OpenAI-compatible server
  - Google Account with Gemini API access
- **Optional:**
  - VTuber Studio for avatar control
  - Applio/RVC for voice conversion
  - VB-Audio Virtual Cable for advanced audio routing

## 🚀 Quick Start

### Installation

1. **Install dependencies:**
```bash
python -m pip install -r requirements.txt
```

2. **Set up `.env` file:**
```bash
# Choose your backend
PREFERRED_BACKEND=gemini

# Audio output (VB-Audio device 11 recommended)
AUDIO_OUTPUT_DEVICE=11
AUDIO_PLAY_OUTPUT=true

# VTuber Studio (optional but recommended)
VTUBER_STUDIO_ENABLED=true
VTUBER_STUDIO_API_URL=ws://localhost:8001
```

3. **Run the app:**

**CLI Mode:**
```bash
python main.py
```

**GUI Mode:**
```bash
python app.py
```

**One-Click Launch:**
```bash
Run.bat
```

### First Run

1. Start VTuber Studio (if using avatar)
2. Load an avatar model in VTuber Studio
3. Run `python main.py` or `python app.py`
4. Start chatting!

Commands in CLI:
- `/speaker <name>` - Change voice
- `/pitch <value>` - Adjust pitch
- `/backend <type>` - Switch AI backend
- `exit` - Quit

## ⚙️ Configuration

The app reads settings from `.env` in the project root. See the comprehensive guide below for all options.

### Backend Selection

**Google Gemini (Recommended - Cloud):**
```env
PREFERRED_BACKEND=gemini
GOOGLE_AISTUDIO_MODEL=gemini-2.5-flash
```

**Local LM Studio:**
```env
PREFERRED_BACKEND=lmstudio
LM_STUDIO_BASE_URL=http://127.0.0.1:1234
LM_STUDIO_MODEL=qwen/qwen3-4b
LM_STUDIO_TEMPERATURE=0.7
```

### Voice & Audio

```env
# Speaker presets: normal, high, low, chipmunk, deep
EDGE_TTS_SPEAKER=normal
EDGE_TTS_PITCH_SEMITONES=0

# Audio device selection
AUDIO_OUTPUT_DEVICE=11
AUDIO_PLAY_OUTPUT=true
```

### Avatar Integration (Optional)

```env
# VTuber Studio connection
VTUBER_STUDIO_ENABLED=true
VTUBER_STUDIO_API_URL=ws://localhost:8001
# Token auto-generated on first connection

# Supported expressions: angry, smile_happy, sad, brush, smug, clear
```

### Voice Conversion (Optional)

```env
# Applio/RVC for voice transformation
EDGE_APPLIO_PATH=C:\Users\MSI\Desktop\Applio
RVC_MODEL_PTH=rvc/models/no7/no7_talk.pth
RVC_MODEL_INDEX=rvc/models/no7/added_IVF1259_Flat_nprobe_1_no7_talk_v2.index
```

### Voice Recognition (Optional)

```env
VOICE_INPUT_ENABLED=1
VOICE_MODE=voice_activation
CHAT_INPUT_ENABLED=1
```

**See `README_COMPREHENSIVE.md` for complete configuration reference.**

## 🎮 Runtime Commands

Available in CLI mode (`main.py`) while running:

```
/speaker <name>      - Change voice preset (normal, high, low, chipmunk, deep)
/pitch <semitones>   - Adjust pitch (e.g., /pitch 2 or /pitch -1)
/backend <type>      - Switch backend (gemini or lmstudio)
/speakers            - List available speaker presets
/hotkeys             - Show available VTuber Studio expressions
exit                 - Close the application
```

**Examples:**
```
You: ลองพูดเสียงสูงหน่อยครับ
/speaker chipmunk
/pitch 3
AI: [responds in chipmunk voice]

You: /backend gemini
✓ Backend switched to: GEMINI
```

Desktop GUI (`app.py`) uses menu buttons instead of text commands.

## 📁 Project Structure

```
VAI/
├── main.py                        # CLI chat interface
├── app.py                        # Desktop GUI (tkinter)
├── Run.bat                       # One-click launcher
│
├── config/
│   ├── settings.py               # Configuration management
│   └── personality.txt           # AI personality prompt
│
├── utils/
│   ├── vtuber_controller.py      # VTuber Studio API wrapper
│   ├── logger.py                 # Logging system
│   ├── history.py                # Chat history management
│   ├── inputer.py                # Voice input interface
│   └── cleanup.py                # File cleanup
│
├── tts/
│   ├── edge_tts_engine.py        # Text-to-speech
│   ├── audio_player.py           # Audio playback
│   └── output/                   # Generated audio
│
├── rvc/
│   ├── applio_stub.py            # Voice conversion wrapper
│   ├── models/                   # RVC model files
│   └── output/                   # Processed audio
│
├── scripts/
│   ├── voice_recognize.py        # Speaker identification
│   ├── vtubestudio_connect.py    # VTuber connection test
│   ├── check_rvc_config.py       # Configuration validator
│   ├── list_audio_devices.py     # Audio device detection
│   └── ...                       # Other utilities
│
├── data/
│   ├── chat_history.json         # Saved conversations
│   └── voice_profiles/           # Speaker profiles
│
├── docs/
│   ├── VTUBER_STUDIO_INTEGRATION.md
│   └── VOICE_RECOGNITION.md
│
├── logs/                         # Application logs
├── subtitle.txt                  # Subtitle output (for streaming)
│
├── QUICK_REFERENCE.md            # ⚡ Start here for quick reference
├── README_COMPREHENSIVE.md       # 📚 Complete documentation
└── requirements.txt              # Python dependencies
```

## 🎭 Avatar Expression System

VAI automatically detects emotions in AI responses and updates your VTuber avatar's expressions in real-time.

### How It Works

1. **Sentiment Detection** - Thai keywords in response are analyzed
2. **Expression Mapping** - Emotion mapped to hotkey:
   - `โกรธ`, `แย่` → angry
   - `ดี`, `ยิ้ม` → smile_happy  
   - `เศร้า`, `ทุกข์` → sad
3. **Avatar Sync** - VTuber Studio API triggers expression
4. **Audio Playback** - Audio plays while expression is active
5. **Auto Clear** - Expression returns to neutral after 2 seconds

### Setup

1. Open VTuber Studio and load an avatar
2. Create hotkeys in Settings → Hotkeys:
   - angry, smile_happy, sad, brush, smug, clear
3. Link hotkeys to expression files (.exp3.json)
4. Enable in `.env`: `VTUBER_STUDIO_ENABLED=true`
5. Run VAI - expressions will sync automatically!

**For detailed setup:** See `docs/VTUBER_STUDIO_INTEGRATION.md`

## 🔧 Troubleshooting

### Avatar Not Working
```bash
# Check VTuber connection
python scripts/vtubestudio_connect.py
```
- ✅ Ensure VTuber Studio is running
- ✅ Check that model is loaded
- ✅ Verify hotkeys are created

### Audio Not Playing
```bash
# List available audio devices
python scripts/list_audio_devices.py
```
- ✅ Update `AUDIO_OUTPUT_DEVICE` in .env
- ✅ Verify ffmpeg is installed
- ✅ Check `AUDIO_PLAY_OUTPUT=true`

### Backend Issues
- **Gemini**: Check internet connection and API key
- **LM Studio**: Ensure it's running on port 1234
- **LM Studio**: Load a model in the UI first

## 📚 Documentation

- 📖 **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Fast reference guide ⭐ Start here!
- 📖 **[README_COMPREHENSIVE.md](README_COMPREHENSIVE.md)** - Complete documentation
- 📖 **[docs/VTUBER_STUDIO_INTEGRATION.md](docs/VTUBER_STUDIO_INTEGRATION.md)** - Avatar integration
- 📖 **[docs/VOICE_RECOGNITION.md](docs/VOICE_RECOGNITION.md)** - Voice input setup
- 📖 **[EXPRESSION_SYSTEM_INTEGRATED.md](EXPRESSION_SYSTEM_INTEGRATED.md)** - Expression system details

## 📝 Notes

- **Personality**: Customize `config/personality.txt` for AI behavior
- **History**: Chat history saved to `data/chat_history.json`
- **TTS Output**: Generated audio in `tts/output/`
- **Logging**: Check `logs/` for detailed debugging information
- **Streaming**: Use `subtitle.txt` with OBS for overlay subtitles
