"""
Speech-to-Text module for Vox.

Provides offline speech recognition using whisper.cpp via pywhispercpp.
Records audio from the microphone and transcribes it using local GGML models.
"""
import io
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

from AppKit import NSOperationQueue

# Constants
MODELS_DIR = Path.home() / "Library" / "Application Support" / "Vox" / "models"

# RMS normalization constant (max 16-bit value is 32767, use half for headroom)
RMS_NORMALIZATION_FACTOR = 16384.0

# Whisper model definitions with download URLs
WHISPER_MODELS = {
    "tiny": {
        "file": "ggml-tiny.bin",
        "size_mb": 39,
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    },
    "base": {
        "file": "ggml-base.bin",
        "size_mb": 74,
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    },
    "small": {
        "file": "ggml-small.bin",
        "size_mb": 244,
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    },
    "medium": {
        "file": "ggml-medium.bin",
        "size_mb": 769,
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    },
}

# Supported languages for transcription
SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
}


class SpeechError(Exception):
    """Base exception for speech-related errors."""
    pass


class MicrophonePermissionError(SpeechError):
    """Raised when microphone permission is denied."""
    pass


class ModelDownloadError(SpeechError):
    """Raised when model download fails."""
    pass


class ModelNotDownloadedError(SpeechError):
    """Raised when trying to use a model that hasn't been downloaded."""
    pass


class WhisperModelManager:
    """Download, cache, and load GGML whisper models."""

    def __init__(self, models_dir: Path = None):
        """
        Initialize the model manager.

        Args:
            models_dir: Directory to store downloaded models.
        """
        self._models_dir = models_dir or MODELS_DIR
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_model = None
        self._loaded_model_name = None

    def get_model_path(self, name: str) -> Path:
        """Get the path to a model file."""
        if name not in WHISPER_MODELS:
            raise ValueError(f"Unknown model: {name}")
        return self._models_dir / WHISPER_MODELS[name]["file"]

    def is_model_downloaded(self, name: str) -> bool:
        """
        Check if a model has been downloaded.

        Args:
            name: Model name (tiny, base, small, medium).

        Returns:
            True if the model file exists and has the expected size.
        """
        if name not in WHISPER_MODELS:
            return False
        path = self.get_model_path(name)
        if not path.exists():
            return False
        # Verify file size is at least 95% of expected (allow some tolerance)
        expected_size = WHISPER_MODELS[name]["size_mb"] * 1024 * 1024
        actual_size = path.stat().st_size
        return actual_size >= expected_size * 0.95

    def get_model_size_mb(self, name: str) -> int:
        """Get the expected size of a model in MB."""
        if name not in WHISPER_MODELS:
            return 0
        return WHISPER_MODELS[name]["size_mb"]

    def download_model(
        self,
        name: str,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> bool:
        """
        Download a whisper model.

        Args:
            name: Model name (tiny, base, small, medium).
            progress_callback: Optional callback for download progress (0.0-1.0).

        Returns:
            True if download succeeded.

        Raises:
            ModelDownloadError: If download fails.
        """
        import urllib.request
        import urllib.error

        if name not in WHISPER_MODELS:
            raise ValueError(f"Unknown model: {name}")

        model_info = WHISPER_MODELS[name]
        model_path = self.get_model_path(name)
        temp_path = model_path.with_suffix(".tmp")

        try:
            # Clean up any previous partial download
            if temp_path.exists():
                temp_path.unlink()

            url = model_info["url"]
            expected_size = model_info["size_mb"] * 1024 * 1024

            def report_progress(block_num, block_size, total_size):
                if progress_callback:
                    downloaded = block_num * block_size
                    if total_size > 0:
                        progress = min(downloaded / total_size, 1.0)
                    else:
                        progress = min(downloaded / expected_size, 1.0)
                    # Dispatch to main thread
                    NSOperationQueue.mainQueue().addOperationWithBlock_(
                        lambda p=progress: progress_callback(p)
                    )

            # Download to temp file first
            urllib.request.urlretrieve(url, temp_path, reporthook=report_progress)

            # Move to final location
            temp_path.rename(model_path)

            # Clear loaded model cache if we re-downloaded the current model
            if self._loaded_model_name == name:
                self._loaded_model = None
                self._loaded_model_name = None

            return True

        except urllib.error.URLError as e:
            if temp_path.exists():
                temp_path.unlink()
            raise ModelDownloadError(f"Failed to download model: {e}")
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise ModelDownloadError(f"Download error: {e}")

    def get_or_load_model(self, name: str):
        """
        Get a loaded model, loading it if necessary.

        Args:
            name: Model name (tiny, base, small, medium).

        Returns:
            pywhispercpp Model instance.

        Raises:
            ModelNotDownloadedError: If the model hasn't been downloaded.
        """
        if not self.is_model_downloaded(name):
            raise ModelNotDownloadedError(
                f"Model '{name}' not downloaded. Please download it first."
            )

        # Return cached model if same
        if self._loaded_model is not None and self._loaded_model_name == name:
            return self._loaded_model

        # Import here to avoid startup overhead
        from pywhispercpp.model import Model

        model_path = self.get_model_path(name)
        self._loaded_model = Model(str(model_path))
        self._loaded_model_name = name

        return self._loaded_model

    def unload_model(self):
        """Unload the currently loaded model to free memory."""
        self._loaded_model = None
        self._loaded_model_name = None


class AudioRecorder:
    """Record audio from the microphone using PyAudio (16kHz mono)."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """
        Initialize the audio recorder.

        Args:
            sample_rate: Sample rate for recording (default 16kHz for whisper).
            channels: Number of audio channels (default 1 for mono).
        """
        self._sample_rate = sample_rate
        self._channels = channels
        self._audio = None
        self._stream = None
        self._frames = []
        self._is_recording = False
        self._level_callback = None

    @staticmethod
    def has_microphone_permission() -> bool:
        """
        Check if microphone permission has been granted.

        Returns:
            True if microphone access is available.
        """
        try:
            import pyaudio
            # Try to initialize PyAudio - this will fail without permission
            audio = pyaudio.PyAudio()
            # Try to get default input device info
            try:
                default_input = audio.get_default_input_device_info()
                audio.terminate()
                return default_input is not None
            except Exception:
                audio.terminate()
                return False
        except Exception:
            return False

    def start_recording(
        self, level_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """
        Start recording from the microphone.

        Args:
            level_callback: Optional callback for audio level updates (0.0-1.0).

        Returns:
            True if recording started successfully.

        Raises:
            MicrophonePermissionError: If microphone access is denied.
        """
        if self._is_recording:
            return True

        try:
            import pyaudio

            self._audio = pyaudio.PyAudio()
            self._frames = []
            self._level_callback = level_callback
            self._is_recording = True

            def audio_callback(in_data, frame_count, time_info, status):
                self._frames.append(in_data)

                # Calculate audio level for VU meter
                if self._level_callback:
                    import struct
                    # Convert bytes to samples (assuming 16-bit audio)
                    samples = struct.unpack(
                        f"<{frame_count}h", in_data
                    )
                    # Calculate RMS level
                    if samples:
                        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                        # Normalize to 0-1 range (max 16-bit value is 32767)
                        level = min(rms / RMS_NORMALIZATION_FACTOR, 1.0)
                        # Dispatch to main thread
                        NSOperationQueue.mainQueue().addOperationWithBlock_(
                            lambda l=level: self._level_callback(l)
                        )

                return (in_data, pyaudio.paContinue)

            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=1024,
                stream_callback=audio_callback,
            )

            self._stream.start_stream()
            return True

        except OSError as e:
            self._is_recording = False
            if "Input device" in str(e) or "No Default" in str(e):
                raise MicrophonePermissionError(
                    "Microphone access denied. Please grant microphone permission "
                    "in System Settings → Privacy & Security → Microphone."
                )
            raise
        except Exception as e:
            self._is_recording = False
            raise MicrophonePermissionError(f"Failed to start recording: {e}")

    def stop_recording(self) -> bytes:
        """
        Stop recording and return the recorded audio as WAV data.

        Returns:
            WAV-formatted audio bytes.
        """
        if not self._is_recording:
            return b""

        self._is_recording = False

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if self._audio:
            self._audio.terminate()
            self._audio = None

        # Convert to WAV format
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self._channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(b"".join(self._frames))

        return wav_buffer.getvalue()

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording


class SpeechTranscriber:
    """Coordinate audio recording and transcription."""

    def __init__(self, model_manager: WhisperModelManager = None):
        """
        Initialize the transcriber.

        Args:
            model_manager: WhisperModelManager instance for model loading.
        """
        self._model_manager = model_manager or WhisperModelManager()
        self._recorder = AudioRecorder()
        self._is_recording = False

    def start_recording(
        self, level_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """
        Start recording audio.

        Args:
            level_callback: Optional callback for audio level updates.

        Returns:
            True if recording started successfully.
        """
        if self._is_recording:
            return True

        result = self._recorder.start_recording(level_callback)
        if result:
            self._is_recording = True
        return result

    def stop_and_transcribe(
        self,
        model_name: str = "base",
        language: str = "auto",
    ) -> Optional[str]:
        """
        Stop recording and transcribe the audio.

        Args:
            model_name: Name of the whisper model to use.
            language: Language code or "auto" for auto-detect.

        Returns:
            Transcribed text, or None if transcription failed.
        """
        if not self._is_recording:
            return None

        self._is_recording = False

        # Stop recording and get WAV data
        wav_data = self._recorder.stop_recording()

        if not wav_data:
            return None

        try:
            # Load model
            model = self._model_manager.get_or_load_model(model_name)

            # Transcribe
            # pywhispercpp can accept file path or we can save to temp file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_data)
                temp_path = f.name

            try:
                # Set language (empty string for auto-detect)
                lang = "" if language == "auto" else language

                # Transcribe - returns a generator of segments
                segments = model.transcribe(temp_path, language=lang)

                # Combine all segments into text
                text = " ".join(segment.text.strip() for segment in segments)

                return text.strip() if text.strip() else None

            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)

        except ModelNotDownloadedError:
            raise
        except Exception as e:
            print(f"Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def cancel_recording(self):
        """Cancel the current recording."""
        if self._is_recording:
            self._is_recording = False
            self._recorder.stop_recording()
