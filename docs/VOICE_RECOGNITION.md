# Voice Recognition System - Voice Input with Speaker Identification

แบบระบบ Voice Input ที่สามารถจำเสียงและรู้จำผู้พูด (Speaker Identification)

## Features

✨ **Core Features:**
- 🎤 **Speaker Recognition**: จำและรู้จำเสียงของผู้พูดต่างๆ
- 🗣️ **Speech Recognition**: แปลงเสียงเป็นข้อความ
- 👤 **Speaker Enrollment**: ลงทะเบียนผู้พูดใหม่
- 📊 **Confidence Scoring**: ระดับความมั่นใจในการรู้จำเสียง
- 💾 **Speaker Profiles**: เก็บโปรไฟล์เสียงของผู้พูด

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `librosa` - Audio feature extraction
- `scikit-learn` - Machine learning models
- `scipy` - Scientific computing
- `sounddevice` - Audio recording
- `soundfile` - Audio file I/O
- `SpeechRecognition` - Speech-to-text

### 2. Create Data Directories

Directories will be created automatically:
```
data/
  voice_profiles/  # Speaker profiles stored here
```

## Usage

### Method 1: Interactive CLI

```bash
# Main voice input interface
python utils/inputer.py

# Voice recognition system directly
python scripts/voice_recognize.py
```

### Method 2: Direct Script Usage

#### Enroll a New Speaker

```bash
python scripts/voice_recognize.py enroll "John" --samples 3 --duration 3
```

When prompted, record 3 samples of 3 seconds each.

#### Identify Speaker

```bash
python scripts/voice_recognize.py identify /path/to/audio.wav
```

Output:
```
Identified: John (confidence: 85.42%)
```

#### List All Speakers

```bash
python scripts/voice_recognize.py list
```

#### Delete Speaker Profile

```bash
python scripts/voice_recognize.py delete "John"
```

### Method 3: Programmatic Usage

```python
from utils.inputer import VoiceInputWithSpeakerID

# Initialize
voice_input = VoiceInputWithSpeakerID(language="th")

# Process voice input
result = voice_input.process_voice_input(
    duration_seconds=5.0,
    identify_speaker_flag=True
)

print(f"Speaker: {result.speaker_name}")
print(f"Confidence: {result.speaker_confidence:.2%}")
print(f"Text: {result.transcription}")
```

## System Components

### 1. `scripts/voice_recognize.py`
Core speaker identification system

**Key Classes:**
- `SpeakerIdentifier`: Main system for speaker management
- `SpeakerProfile`: Data class for speaker information

**Key Methods:**
- `enroll_speaker(speaker_name, audio_samples)`: Register new speaker
- `identify_speaker(audio_path, top_k)`: Identify speaker from audio
- `record_sample(duration)`: Record audio from microphone
- `list_speakers()`: List all enrolled speakers
- `delete_speaker(speaker_name)`: Remove speaker profile

### 2. `utils/inputer.py`
High-level voice input interface

**Key Classes:**
- `VoiceInputWithSpeakerID`: Complete voice input pipeline
- `VoiceInputResult`: Result data class

**Key Methods:**
- `process_voice_input()`: Full pipeline (record → identify → transcribe)
- `enroll_speaker_from_voice()`: Interactive enrollment
- `transcribe_audio()`: Convert audio to text
- `identify_speaker()`: Identify speaker

## How It Works

### Speaker Enrollment Process

1. **Audio Recording**: Record multiple audio samples (minimum 3 recommended)
2. **Feature Extraction**: Extract MFCC features from each sample
3. **Model Training**: Train Gaussian Mixture Model (GMM) on the features
4. **Profile Storage**: Save the trained model and features scaler

### Speaker Identification Process

1. **Audio Recording**: Capture voice input
2. **Feature Extraction**: Extract MFCC features
3. **Scoring**: Calculate likelihood against all speaker profiles
4. **Ranking**: Sort by confidence and return top matches
5. **Confidence Threshold**: Only return matches above threshold

## Audio Features

The system uses the following features for speaker recognition:

- **MFCCs** (Mel-Frequency Cepstral Coefficients): 13 coefficients
- **MFCC Statistics**: Mean and standard deviation
- **Delta MFCCs**: Rate of change of MFCCs

Total feature dimension: **39 dimensions**

## Configuration

### Default Settings

```python
SAMPLE_RATE = 16000          # Hz
MFCC_FEATURES = 13           # Number of MFCC coefficients
DURATION = 3.0               # Seconds per sample
THRESHOLD = 0.5              # Confidence threshold (0-1)
```

Modify in `scripts/voice_recognize.py` to customize.

## Speaker Profiles

Speaker profiles are stored as pickle files in `data/voice_profiles/`:

```
data/voice_profiles/
  John.pkl
  Alice.pkl
  Bob.pkl
```

Each profile contains:
- Trained Gaussian Mixture Model
- Feature scaler (normalization parameters)
- Number of training samples
- Feature dimension

## Best Practices

### For Enrollment

✅ **Do:**
- Use 3-5 samples per speaker
- Speak clearly and naturally
- Record in consistent environment
- Use 2-4 second samples
- Wait for feedback after each sample

❌ **Don't:**
- Record with background noise
- Use very short samples (<1 second)
- Enroll only 1 sample
- Change microphone between samples
- Use heavily distorted audio

### For Identification

✅ **Do:**
- Use the same or similar microphone as enrollment
- Speak in similar tone/style
- Record in similar acoustic environment
- Trust results with >70% confidence

❌ **Don't:**
- Use drastically different speech patterns
- Change microphone hardware
- Record in very noisy environments
- Trust results with <50% confidence

## Troubleshooting

### "No input devices found"
- Check audio input is connected
- Verify microphone is not disabled
- List devices: `python scripts/check_device_channels.py`

### Low confidence scores
- Record more enrollment samples (5+ recommended)
- Ensure consistent recording environment
- Check microphone settings
- Try different speaker profile

### "Could not understand audio"
- Check microphone connection
- Ensure audio quality
- Verify Google Speech API connectivity
- Try different audio input device

### Poor speaker identification
- Enroll more samples (4-5 recommended)
- Record in same environment as identification
- Use same microphone if possible
- Speak in consistent manner

## Integration with Main Application

Example integration with main.py:

```python
from utils.inputer import VoiceInputWithSpeakerID

# In your application
voice_input = VoiceInputWithSpeakerID(language="th")

# Get voice input with speaker identification
result = voice_input.process_voice_input(
    duration_seconds=5.0,
    identify_speaker_flag=True,
    speaker_confidence_threshold=0.5
)

# Use the result
if result.speaker_name:
    logger.info(f"Message from {result.speaker_name}")
else:
    logger.info("Unknown speaker")

# Process the transcribed text
user_input = result.transcription
```

## Performance Notes

- **Enrollment Time**: ~2-5 seconds per sample
- **Identification Time**: ~0.5-1 second per audio
- **Accuracy**: Varies with enrollment quality and environment
- **Best Accuracy**: >80% with proper enrollment

## Supported Languages

Speech recognition supports:
- Thai: `th` or `th-TH`
- English: `en` or `en-US`
- Others: Any language code supported by Google Speech API

## Limitations

- Requires internet connection for speech recognition
- Speaker recognition works best in similar acoustic conditions
- Limited to ~10-50 speakers practically
- Requires sufficient audio samples for accurate models
- May be affected by audio quality and background noise

## Future Improvements

- [ ] Offline speech recognition
- [ ] Support for more speakers (deep learning)
- [ ] Real-time streaming recognition
- [ ] Speaker separation/diarization
- [ ] Emotion recognition from voice
- [ ] Voice activity detection (VAD)
- [ ] Anti-spoofing (liveness detection)

## License

Part of VAI (VTuber AI Assistant) project

## Support

For issues or questions, check:
1. [logs/](../logs/) - System logs
2. `scripts/check_device_channels.py` - Audio device verification
3. Troubleshooting section above
