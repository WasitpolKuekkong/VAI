"""
Integrated Voice Input with Speaker Identification
Combines voice recording, speaker identification, and speech recognition
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import sounddevice as sd
import soundfile as sf
import speech_recognition as sr
from dataclasses import dataclass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import load_settings
from utils.logger import logger
from scripts.voice_recognize import SpeakerIdentifier, SAMPLE_RATE


@dataclass
class VoiceInputResult:
    """Result from voice input processing"""
    speaker_name: str | None
    speaker_confidence: float
    transcription: str
    language: str
    is_confident: bool


class VoiceInputWithSpeakerID:
    """Voice input system with speaker identification"""
    
    def __init__(self, language: str = "th"):
        self.language = language
        self.settings = load_settings()
        self.speaker_identifier = SpeakerIdentifier()
        self.recognizer = cast(Any, sr.Recognizer())
    
    def list_input_devices(self) -> list[tuple[int, str, int]]:
        """List available input devices"""
        devices: list[tuple[int, str, int]] = []
        for index, device in enumerate(sd.query_devices()):
            input_channels = int(device.get("max_input_channels", 0))
            if input_channels > 0:
                devices.append((index, str(device.get("name", "Unknown")), input_channels))
        return devices
    
    def record_audio(
        self,
        duration_seconds: float,
        device: int | None = None,
        sample_rate: int = SAMPLE_RATE
    ) -> Path:
        """Record audio from microphone"""
        frames = int(sample_rate * duration_seconds)
        logger.info(f"Recording {duration_seconds}s of audio...")
        
        audio = sd.rec(
            frames,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=device
        )
        sd.wait()
        
        temp_dir = Path(tempfile.gettempdir())
        wav_path = temp_dir / "voice_input_recording.wav"
        sf.write(str(wav_path), audio, sample_rate)
        
        return wav_path
    
    def transcribe_audio(self, audio_path: Path, language: str | None = None) -> str:
        """Transcribe audio to text"""
        if language is None:
            language = self.language
        
        try:
            with sr.AudioFile(str(audio_path)) as source:
                audio_data = self.recognizer.record(source)
            
            text = self.recognizer.recognize_google(audio_data, language=language)
            logger.info(f"Transcription: {text}")
            return text
        
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return "[ไม่สามารถถอดเสียงได้]"
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return "[เกิดข้อผิดพลาดในการรู้จำเสียง]"
    
    def identify_speaker(self, audio_path: Path) -> tuple[str | None, float]:
        """Identify speaker from audio"""
        results = self.speaker_identifier.identify_speaker(audio_path, top_k=1)
        
        if results:
            speaker_name, confidence = results[0]
            logger.info(f"Identified speaker: {speaker_name} ({confidence:.2%})")
            return speaker_name, confidence
        
        return None, 0.0
    
    def process_voice_input(
        self,
        duration_seconds: float = 5.0,
        device: int | None = None,
        language: str | None = None,
        identify_speaker_flag: bool = True,
        speaker_confidence_threshold: float = 0.5
    ) -> VoiceInputResult:
        """
        Complete voice input processing pipeline:
        1. Record audio
        2. Identify speaker (optional)
        3. Transcribe audio
        
        Returns:
            VoiceInputResult with speaker info and transcription
        """
        try:
            # Record audio
            audio_path = self.record_audio(duration_seconds, device)
            
            # Identify speaker
            speaker_name = None
            speaker_confidence = 0.0
            
            if identify_speaker_flag and self.speaker_identifier.list_speakers():
                speaker_name, speaker_confidence = self.identify_speaker(audio_path)
            
            # Transcribe
            if language is None:
                language = self.language
            
            transcription = self.transcribe_audio(audio_path, language)
            
            # Determine confidence
            is_confident = (
                speaker_confidence >= speaker_confidence_threshold
                if speaker_name else False
            )
            
            result = VoiceInputResult(
                speaker_name=speaker_name,
                speaker_confidence=speaker_confidence,
                transcription=transcription,
                language=language,
                is_confident=is_confident
            )
            
            logger.info(f"Voice input result: {result}")
            
            # Cleanup
            try:
                audio_path.unlink()
            except:
                pass
            
            return result
        
        except Exception as e:
            logger.error(f"Voice input processing failed: {e}")
            raise
    
    def enroll_speaker_from_voice(
        self,
        speaker_name: str,
        num_samples: int = 3,
        duration_seconds: float = 3.0,
        device: int | None = None
    ) -> bool:
        """
        Enroll a speaker using microphone input
        """
        samples = []
        
        print(f"\n=== Enrolling Speaker: {speaker_name} ===")
        print(f"Recording {num_samples} samples of {duration_seconds}s each")
        
        for i in range(num_samples):
            input(f"\nPress Enter to start recording sample {i + 1}/{num_samples}...")
            
            try:
                # Record sample
                audio_path = self.record_audio(duration_seconds, device)
                samples.append(audio_path)
                print(f"✓ Sample {i + 1} recorded")
                
            except Exception as e:
                print(f"✗ Failed to record sample {i + 1}: {e}")
                # Clean up already recorded samples
                for sample in samples:
                    try:
                        sample.unlink()
                    except:
                        pass
                return False
        
        # Enroll speaker
        try:
            success = self.speaker_identifier.enroll_speaker(speaker_name, samples)
            
            if success:
                print(f"\n✓ Successfully enrolled speaker: {speaker_name}")
            else:
                print(f"\n✗ Failed to enroll speaker: {speaker_name}")
            
            return success
        
        finally:
            # Clean up samples
            for sample in samples:
                try:
                    sample.unlink()
                except:
                    pass


def main_interactive():
    """Interactive CLI for voice input and speaker identification"""
    voice_input = VoiceInputWithSpeakerID()
    
    print("=== Voice Input with Speaker Identification ===\n")
    
    while True:
        print("\nOptions:")
        print("1. Test voice input")
        print("2. Enroll new speaker")
        print("3. List speakers")
        print("4. Delete speaker")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            # Test voice input
            print("\nAvailable input devices:")
            devices = voice_input.list_input_devices()
            for idx, name, channels in devices:
                print(f"  {idx}: {name} (channels: {channels})")
            
            device_choice = input("\nSelect device (press Enter for default): ").strip()
            device = int(device_choice) if device_choice else None
            
            duration = float(input("Duration in seconds (default 5): ") or "5")
            
            try:
                print("\n🎤 Recording...")
                result = voice_input.process_voice_input(
                    duration_seconds=duration,
                    device=device,
                    identify_speaker_flag=True
                )
                
                print(f"\n📊 Result:")
                print(f"  Speaker: {result.speaker_name or 'Unknown'}")
                print(f"  Confidence: {result.speaker_confidence:.2%}")
                print(f"  Text: {result.transcription}")
                
            except Exception as e:
                print(f"Error: {e}")
        
        elif choice == "2":
            # Enroll speaker
            speaker_name = input("\nEnter speaker name: ").strip()
            if not speaker_name:
                print("Speaker name cannot be empty")
                continue
            
            device_choice = input("Select device (press Enter for default): ").strip()
            device = int(device_choice) if device_choice else None
            
            num_samples = int(input("Number of samples (default 3): ") or "3")
            duration = float(input("Duration per sample (default 3): ") or "3")
            
            voice_input.enroll_speaker_from_voice(
                speaker_name=speaker_name,
                num_samples=num_samples,
                duration_seconds=duration,
                device=device
            )
        
        elif choice == "3":
            # List speakers
            speakers = voice_input.speaker_identifier.list_speakers()
            if speakers:
                print("\nEnrolled speakers:")
                for speaker in speakers:
                    print(f"  - {speaker}")
            else:
                print("\nNo speakers enrolled yet")
        
        elif choice == "4":
            # Delete speaker
            speaker_name = input("\nEnter speaker name to delete: ").strip()
            if speaker_name:
                if voice_input.speaker_identifier.delete_speaker(speaker_name):
                    print(f"Deleted: {speaker_name}")
                else:
                    print(f"Failed to delete: {speaker_name}")
        
        elif choice == "5":
            print("\nGoodbye!")
            break
        
        else:
            print("Invalid option")


if __name__ == "__main__":
    main_interactive()
