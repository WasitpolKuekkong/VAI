"""
Voice Recognition and Speaker Identification System
Recognizes and remembers different speakers
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, cast

import librosa
import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
import sounddevice as sd
import soundfile as sf
import sys
from dataclasses import dataclass, asdict

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import logger

# Configuration
VOICE_PROFILES_DIR = PROJECT_ROOT / "data" / "voice_profiles"
VOICE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# Audio processing parameters
SAMPLE_RATE = 16000
MFCC_FEATURES = 13
DURATION = 3.0  # seconds for training samples
THRESHOLD = 0.5  # confidence threshold for identification


@dataclass
class SpeakerProfile:
    """Speaker identification profile"""
    name: str
    gmm_model: Any  # GaussianMixture model (will be pickled)
    scaler: Any  # StandardScaler (will be pickled)
    num_samples: int
    created_at: str


class SpeakerIdentifier:
    """Main speaker identification system"""
    
    def __init__(self):
        self.profiles: dict[str, dict[str, Any]] = {}
        self.scaler = StandardScaler()
        self._load_profiles()
    
    def _load_profiles(self):
        """Load all saved speaker profiles"""
        profile_files = list(VOICE_PROFILES_DIR.glob("*.pkl"))
        for profile_file in profile_files:
            try:
                with open(profile_file, "rb") as f:
                    data = pickle.load(f)
                    speaker_name = profile_file.stem
                    self.profiles[speaker_name] = data
                    logger.info(f"Loaded speaker profile: {speaker_name}")
            except Exception as e:
                logger.error(f"Failed to load profile {profile_file}: {e}")
    
    def _extract_mfcc_features(self, audio_path: Path) -> np.ndarray:
        """Extract MFCC features from audio file"""
        try:
            y, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE, duration=DURATION)
            
            # Extract MFCC features
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=MFCC_FEATURES)
            
            # Calculate statistics for each MFCC coefficient
            mfcc_mean = np.mean(mfccs, axis=1)
            mfcc_std = np.std(mfccs, axis=1)
            mfcc_delta_mean = np.mean(librosa.feature.delta(mfccs), axis=1)
            
            # Combine all features
            features = np.concatenate([mfcc_mean, mfcc_std, mfcc_delta_mean])
            return features.reshape(1, -1)
        
        except Exception as e:
            logger.error(f"Failed to extract features from {audio_path}: {e}")
            raise
    
    def enroll_speaker(self, speaker_name: str, audio_samples: list[Path]) -> bool:
        """
        Enroll a new speaker by training on multiple audio samples
        
        Args:
            speaker_name: Name of the speaker to enroll
            audio_samples: List of audio file paths for training
        
        Returns:
            True if enrollment successful, False otherwise
        """
        try:
            if len(audio_samples) < 2:
                logger.warning("At least 2 audio samples required for enrollment")
                return False
            
            logger.info(f"Enrolling speaker: {speaker_name} with {len(audio_samples)} samples")
            
            # Extract features from all samples
            all_features = []
            for audio_path in audio_samples:
                if not Path(audio_path).exists():
                    logger.warning(f"Audio file not found: {audio_path}")
                    continue
                
                features = self._extract_mfcc_features(Path(audio_path))
                all_features.append(features[0])
            
            if len(all_features) < 2:
                logger.error("Not enough valid audio samples for enrollment")
                return False
            
            # Combine features and fit Gaussian Mixture Model
            X = np.array(all_features)
            
            # Fit scaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Train GMM model
            gmm = GaussianMixture(n_components=2, covariance_type='diag', n_init=10)
            gmm.fit(X_scaled)
            
            # Save profile
            profile_data = {
                'name': speaker_name,
                'gmm_model': gmm,
                'scaler': scaler,
                'num_samples': len(all_features),
                'features_dim': X.shape[1]
            }
            
            profile_path = VOICE_PROFILES_DIR / f"{speaker_name}.pkl"
            with open(profile_path, "wb") as f:
                pickle.dump(profile_data, f)
            
            self.profiles[speaker_name] = profile_data
            logger.info(f"Successfully enrolled speaker: {speaker_name}")
            return True
        
        except Exception as e:
            logger.error(f"Enrollment failed for {speaker_name}: {e}")
            return False
    
    def identify_speaker(self, audio_path: Path, top_k: int = 1) -> list[tuple[str, float]]:
        """
        Identify the speaker from an audio sample
        
        Args:
            audio_path: Path to the audio file
            top_k: Number of top matches to return
        
        Returns:
            List of (speaker_name, confidence) tuples sorted by confidence
        """
        try:
            if not self.profiles:
                logger.warning("No speaker profiles available")
                return []
            
            # Extract features from the unknown audio
            features = self._extract_mfcc_features(audio_path)
            
            # Score against all known speakers
            scores = {}
            for speaker_name, profile_data in self.profiles.items():
                try:
                    scaler = profile_data['scaler']
                    gmm = profile_data['gmm_model']
                    
                    # Normalize features using the speaker's scaler
                    X_scaled = scaler.transform(features)
                    
                    # Calculate log probability
                    score = gmm.score(X_scaled)
                    scores[speaker_name] = score
                
                except Exception as e:
                    logger.debug(f"Failed to score {speaker_name}: {e}")
                    continue
            
            if not scores:
                logger.warning("Could not score against any speaker profiles")
                return []
            
            # Normalize scores to 0-1 confidence range
            min_score = min(scores.values())
            max_score = max(scores.values())
            
            if max_score == min_score:
                confidence_scores = {k: 0.5 for k in scores.keys()}
            else:
                confidence_scores = {
                    k: (scores[k] - min_score) / (max_score - min_score)
                    for k in scores.keys()
                }
            
            # Sort by confidence (descending) and return top_k
            sorted_results = sorted(
                confidence_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]
            
            logger.info(f"Identification results: {sorted_results}")
            return sorted_results
        
        except Exception as e:
            logger.error(f"Identification failed: {e}")
            return []
    
    def list_speakers(self) -> list[str]:
        """Get list of all enrolled speakers"""
        return list(self.profiles.keys())
    
    def delete_speaker(self, speaker_name: str) -> bool:
        """Delete a speaker profile"""
        try:
            profile_path = VOICE_PROFILES_DIR / f"{speaker_name}.pkl"
            if profile_path.exists():
                profile_path.unlink()
                del self.profiles[speaker_name]
                logger.info(f"Deleted speaker profile: {speaker_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete speaker {speaker_name}: {e}")
            return False
    
    def record_sample(
        self,
        duration: float = DURATION,
        sample_rate: int = SAMPLE_RATE,
        device: int | None = None
    ) -> Path:
        """
        Record an audio sample from microphone
        
        Args:
            duration: Duration in seconds
            sample_rate: Sample rate in Hz
            device: Device index (None for default)
        
        Returns:
            Path to the recorded file
        """
        try:
            logger.info(f"Recording {duration}s audio sample...")
            frames = int(sample_rate * duration)
            
            audio = sd.rec(
                frames,
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                device=device
            )
            sd.wait()
            
            # Save to temporary location
            temp_path = VOICE_PROFILES_DIR / "temp_sample.wav"
            sf.write(str(temp_path), audio, sample_rate)
            
            logger.info(f"Audio sample saved to {temp_path}")
            return temp_path
        
        except Exception as e:
            logger.error(f"Failed to record audio: {e}")
            raise


# Convenience functions
def identify_speaker_in_audio(audio_path: str | Path) -> tuple[str | None, float]:
    """
    Identify the speaker in an audio file
    Returns (speaker_name, confidence) or (None, 0.0) if not identified
    """
    identifier = SpeakerIdentifier()
    results = identifier.identify_speaker(Path(audio_path), top_k=1)
    
    if results:
        speaker_name, confidence = results[0]
        if confidence >= THRESHOLD:
            return speaker_name, confidence
    
    return None, 0.0


def enroll_speaker_interactive(speaker_name: str, num_samples: int = 3, duration: float = DURATION) -> bool:
    """
    Interactive speaker enrollment from microphone
    """
    identifier = SpeakerIdentifier()
    samples = []
    
    print(f"\n=== Enrolling Speaker: {speaker_name} ===")
    print(f"You will record {num_samples} audio samples, each {duration} seconds long.")
    print("Speak naturally and clearly in each recording.\n")
    
    for i in range(num_samples):
        input(f"Press Enter to start recording sample {i + 1}/{num_samples}...")
        try:
            sample_path = identifier.record_sample(duration)
            samples.append(sample_path)
            print(f"✓ Sample {i + 1} recorded successfully\n")
        except Exception as e:
            print(f"✗ Failed to record sample {i + 1}: {e}\n")
            return False
    
    # Enroll with recorded samples
    success = identifier.enroll_speaker(speaker_name, samples)
    
    # Clean up temp files
    for sample in samples:
        try:
            sample.unlink()
        except:
            pass
    
    if success:
        print(f"✓ Successfully enrolled speaker: {speaker_name}")
    else:
        print(f"✗ Failed to enroll speaker: {speaker_name}")
    
    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice Recognition and Speaker Identification")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Enroll command
    enroll_parser = subparsers.add_parser("enroll", help="Enroll a new speaker")
    enroll_parser.add_argument("name", help="Speaker name")
    enroll_parser.add_argument("--samples", type=int, default=3, help="Number of samples")
    enroll_parser.add_argument("--duration", type=float, default=DURATION, help="Duration per sample")
    
    # Identify command
    identify_parser = subparsers.add_parser("identify", help="Identify speaker in audio")
    identify_parser.add_argument("audio_path", help="Path to audio file")
    
    # List command
    subparsers.add_parser("list", help="List all enrolled speakers")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete speaker profile")
    delete_parser.add_argument("name", help="Speaker name")
    
    args = parser.parse_args()
    
    if args.command == "enroll":
        enroll_speaker_interactive(args.name, args.samples, args.duration)
    
    elif args.command == "identify":
        speaker, confidence = identify_speaker_in_audio(args.audio_path)
        if speaker:
            print(f"Identified: {speaker} (confidence: {confidence:.2%})")
        else:
            print("Unknown speaker or confidence too low")
    
    elif args.command == "list":
        identifier = SpeakerIdentifier()
        speakers = identifier.list_speakers()
        if speakers:
            print("Enrolled speakers:")
            for speaker in speakers:
                print(f"  - {speaker}")
        else:
            print("No speakers enrolled yet")
    
    elif args.command == "delete":
        identifier = SpeakerIdentifier()
        if identifier.delete_speaker(args.name):
            print(f"Deleted speaker: {args.name}")
        else:
            print(f"Failed to delete speaker: {args.name}")
    
    else:
        parser.print_help()
