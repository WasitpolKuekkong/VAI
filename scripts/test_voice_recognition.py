"""
Voice Recognition System - Quick Test and Setup Script
Tests voice recognition system installation and functionality
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_imports():
    """Test if all required packages are installed"""
    print("📦 Testing imports...\n")
    
    packages = {
        "librosa": "Audio feature extraction",
        "numpy": "Numerical computing",
        "sklearn": "Machine learning",
        "scipy": "Scientific computing",
        "sounddevice": "Audio I/O",
        "soundfile": "Audio file handling",
        "speech_recognition": "Speech recognition",
    }
    
    failed = []
    
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"✓ {package:20} - {description}")
        except ImportError as e:
            print(f"✗ {package:20} - {description}")
            failed.append((package, str(e)))
    
    if failed:
        print(f"\n❌ {len(failed)} package(s) missing!")
        print("\nInstall missing packages with:")
        print(f"  pip install -r requirements.txt")
        return False
    
    print(f"\n✅ All packages installed!")
    return True


def test_audio_devices():
    """Test audio device detection"""
    print("\n🎤 Testing audio devices...\n")
    
    try:
        import sounddevice as sd
        
        devices = sd.query_devices()
        input_devices = []
        
        for index, device in enumerate(devices):
            input_channels = int(device.get("max_input_channels", 0))
            if input_channels > 0:
                input_devices.append((index, device.get("name", "Unknown"), input_channels))
        
        if input_devices:
            print("Available input devices:")
            for idx, name, channels in input_devices:
                marker = "→" if idx == sd.default.device[0] else " "
                print(f"  {marker} [{idx}] {name} ({channels}ch)")
            print(f"\n✅ Found {len(input_devices)} input device(s)")
            return True
        else:
            print("❌ No input devices found!")
            return False
    
    except Exception as e:
        print(f"❌ Error testing audio devices: {e}")
        return False


def test_voice_recognition_system():
    """Test voice recognition system initialization"""
    print("\n🎙️ Testing voice recognition system...\n")
    
    try:
        from scripts.voice_recognize import SpeakerIdentifier
        from utils.inputer import VoiceInputWithSpeakerID
        
        # Test SpeakerIdentifier
        identifier = SpeakerIdentifier()
        speakers = identifier.list_speakers()
        print(f"✓ SpeakerIdentifier initialized")
        print(f"  Enrolled speakers: {len(speakers)}")
        if speakers:
            for speaker in speakers:
                print(f"    - {speaker}")
        
        # Test VoiceInputWithSpeakerID
        voice_input = VoiceInputWithSpeakerID(language="th")
        print(f"✓ VoiceInputWithSpeakerID initialized (language: th)")
        
        # List audio devices
        devices = voice_input.list_input_devices()
        print(f"✓ Audio devices detected: {len(devices)}")
        
        print(f"\n✅ Voice recognition system ready!")
        return True
    
    except Exception as e:
        print(f"❌ Error testing system: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_data_directories():
    """Check data directories"""
    print("\n📁 Checking data directories...\n")
    
    try:
        from scripts.voice_recognize import VOICE_PROFILES_DIR
        
        print(f"Voice profiles directory: {VOICE_PROFILES_DIR}")
        
        if VOICE_PROFILES_DIR.exists():
            print(f"✓ Directory exists")
            profile_files = list(VOICE_PROFILES_DIR.glob("*.pkl"))
            print(f"  Profile files: {len(profile_files)}")
        else:
            print(f"✓ Directory will be created automatically")
        
        return True
    
    except Exception as e:
        print(f"❌ Error checking directories: {e}")
        return False


def print_usage_examples():
    """Print usage examples"""
    print("\n" + "="*60)
    print("📖 USAGE EXAMPLES")
    print("="*60)
    
    print("\n1️⃣  Interactive CLI:")
    print("    python utils/inputer.py")
    
    print("\n2️⃣  Enroll a speaker:")
    print("    python scripts/voice_recognize.py enroll 'John' --samples 3")
    
    print("\n3️⃣  Identify speaker:")
    print("    python scripts/voice_recognize.py identify /path/to/audio.wav")
    
    print("\n4️⃣  List speakers:")
    print("    python scripts/voice_recognize.py list")
    
    print("\n5️⃣  Delete speaker:")
    print("    python scripts/voice_recognize.py delete 'John'")
    
    print("\n6️⃣  Programmatic usage:")
    print("""
    from utils.inputer import VoiceInputWithSpeakerID
    
    voice_input = VoiceInputWithSpeakerID(language="th")
    result = voice_input.process_voice_input(duration_seconds=5.0)
    
    print(f"Speaker: {result.speaker_name}")
    print(f"Text: {result.transcription}")
    """)
    
    print("\n📚 Documentation: docs/VOICE_RECOGNITION.md")
    print("="*60)


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🎵 Voice Recognition System - Installation Test")
    print("="*60)
    
    results = {
        "Imports": test_imports(),
        "Audio Devices": test_audio_devices(),
        "System": test_voice_recognition_system(),
        "Directories": check_data_directories(),
    }
    
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ All tests passed! System is ready to use.")
        print_usage_examples()
        return 0
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Check microphone connection")
        print("  3. Verify audio device settings")
        return 1


if __name__ == "__main__":
    sys.exit(main())
