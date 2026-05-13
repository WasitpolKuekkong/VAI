# VAI

VAI is a small AI VTuber-style chat pipeline for Windows. It takes your input from the console, sends it to LM Studio, turns the reply into speech, optionally runs that audio through Applio/RVC, and can play the result to an audio device or VB-Audio cable.

## What it does

- Chat with a local LLM through LM Studio
- Keep conversation history between runs
- Generate speech with gTTS-based TTS
- Apply simple speaker and pitch presets
- Optionally run the audio through Applio/RVC
- Play the final output to a selected audio device

## Requirements

- Windows
- Python 3.10+ recommended
- LM Studio running locally with an OpenAI-compatible server enabled
- ffmpeg installed and available on PATH for audio processing
- Optional: Applio/RVC installation for voice conversion

## Quick Start

1. Start LM Studio and load the model you want to use.
2. Install the Python dependencies:

```bat
python -m pip install -r requirements.txt
```

3. Run the app:

```bat
python main.py
```

You can also use `Run.bat`, which installs requirements and launches the app.

## Configuration

The app reads settings from `.env` in the project root. If a variable is not set, the defaults in `config/settings.py` are used.

### LM Studio

- `LM_STUDIO_BASE_URL` - LM Studio server URL, default `http://127.0.0.1:1234`
- `LM_STUDIO_MODEL` - model name passed to LM Studio, default `qwen/qwen3-4b`
- `LM_STUDIO_TEMPERATURE` - sampling temperature, default `0.7`
- `LM_STUDIO_MAX_TOKENS` - max response tokens, default `512`
- `LM_STUDIO_HISTORY` - number of messages kept in memory, default `100`
- `LM_STUDIO_TIMEOUT` - request timeout in seconds, default `120`

### TTS

- `EDGE_TTS_VOICE` - language/voice code, default `th`
- `EDGE_TTS_RATE` - speech rate, default `+20%`
- `EDGE_TTS_VOLUME` - output volume, default `+0%`
- `EDGE_TTS_FORMAT` - output format, default `mp3`
- `EDGE_TTS_SPEAKER` - speaker preset, default `normal`
- `EDGE_TTS_PITCH_SEMITONES` - extra pitch shift, default `0`

Supported speaker presets are `normal`, `high`, `low`, `chipmunk`, and `deep`.

### RVC / Applio

- `EDGE_APPLIO_PATH` - path to your Applio installation, default `C:\Users\MSI\Desktop\Applio`
- `EDGE_APPLIO_TIMEOUT` - Applio timeout in seconds, default `120`
- `RVC_MODEL_PTH` - path to the `.pth` model file
- `RVC_MODEL_INDEX` - path to the `.index` file
- `RVC_EMBEDDER_MODEL` - embedder model name, default `contentvec`
- `RVC_EMBEDDER_CUSTOM` - custom embedder path, if used
- `RVC_F0_METHOD` - pitch extraction method, default `rmvpe`

If RVC processing cannot run, the app falls back to copying the input audio into the RVC output folder so the pipeline can continue.

### Audio Output

- `AUDIO_OUTPUT_DEVICE` - output device index
- `AUDIO_PLAY_OUTPUT` - `true` or `false`, default `true`

If no audio device is set, the app tries to detect a VB-Audio device automatically.

## Runtime Commands

While the app is running, these commands are available in the console:

- `/speaker <name>` - change the current speaker preset
- `/pitch <semitones>` - change the additional pitch offset
- `/speakers` - list the supported presets
- `exit` or `quit` - close the app

Example:

```text
/speaker chipmunk
/pitch 2
```

## Project Layout

- `main.py` - application entrypoint
- `config/` - settings and personality prompt
- `data/` - saved chat history
- `tts/` - speech synthesis and audio playback
- `rvc/` - Applio/RVC integration and model files
- `utils/` - logging, cleanup, and history helpers
- `scripts/` - diagnostic helpers for devices and RVC config

## Notes

- The default personality prompt is stored in `config/personality.txt`.
- Chat history is saved to `data/chat_history.json`.
- Generated audio is written to `tts/output/` and processed RVC output to `rvc/output/`.
