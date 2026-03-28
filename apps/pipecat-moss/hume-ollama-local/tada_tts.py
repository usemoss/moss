"""Custom Pipecat TTS service wrapping Hume AI's TADA MLX for local Apple Silicon inference."""

from collections.abc import AsyncGenerator

import numpy as np
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
)
from pipecat.services.tts_service import TTSService


class TadaMLXTTSService(TTSService):
    """Local TTS using Hume AI's TADA model via MLX on Apple Silicon.

    Requires: pip install mlx-tada
    Models: HumeAI/mlx-tada-1b or HumeAI/mlx-tada-3b

    Note: MLX Metal operations must run on the main thread.
    """

    TADA_SAMPLE_RATE = 24000
    TADA_NUM_CHANNELS = 1

    def __init__(
        self,
        *,
        model_id: str = "HumeAI/mlx-tada-1b",
        reference_audio_path: str,
        reference_text: str | None = None,
        quantize: int = 4,
        flow_matching_steps: int = 6,
        **kwargs,
    ):
        super().__init__(
            sample_rate=self.TADA_SAMPLE_RATE,
            push_start_frame=True,
            push_stop_frames=True,
            **kwargs,
        )
        self._model_id = model_id
        self._reference_audio_path = reference_audio_path
        self._reference_text = reference_text
        self._quantize = quantize
        self._flow_matching_steps = flow_matching_steps
        self._model = None
        self._reference = None
        self._inference_options = None
        self._ready = False

    def load(self):
        """Eagerly load the model, reference, and pre-warm Metal kernels.

        Call this at startup before the pipeline runs.
        """
        if self._ready:
            return

        from mlx_tada import InferenceOptions, TadaForCausalLM

        logger.info(f"Loading TADA model {self._model_id} (quantize={self._quantize})...")
        self._model = TadaForCausalLM.from_pretrained(self._model_id, quantize=self._quantize)
        logger.info("TADA model loaded!")

        logger.info(f"Loading voice reference: {self._reference_audio_path}")
        self._reference = self._model.load_reference(
            self._reference_audio_path, audio_text=self._reference_text
        )
        logger.info("Voice reference loaded!")

        self._inference_options = InferenceOptions(
            num_flow_matching_steps=self._flow_matching_steps,
        )

        # Pre-warm: first generation compiles Metal kernels, subsequent ones are faster
        logger.info("Pre-warming TADA (compiling Metal kernels)...")
        self._model.generate("Hello.", self._reference, inference_options=self._inference_options)
        logger.info("TADA ready!")
        self._ready = True

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        """Generate speech from text using TADA MLX.

        Only yields TTSAudioRawFrame — start/stop frames are managed by the base class
        via push_start_frame=True and push_stop_frames=True.
        """
        logger.debug(f"TadaMLXTTSService: Generating speech for: {text[:80]}...")

        try:
            if not self._ready:
                self.load()

            out = self._model.generate(
                text, self._reference, inference_options=self._inference_options
            )

            # Convert float32 numpy array to int16 PCM bytes
            audio_float = np.array(out.audio, dtype=np.float32)
            audio_float = np.clip(audio_float, -1.0, 1.0)
            audio_int16 = (audio_float * 32767).astype(np.int16)

            logger.debug(f"TadaMLXTTSService: Generated {out.duration:.1f}s audio (RTF: {out.rtf:.3f})")

            # Yield audio in small chunks so Pipecat's audio context buffers correctly
            chunk_samples = self.TADA_SAMPLE_RATE // 50  # 480 samples = 20ms at 24kHz
            for i in range(0, len(audio_int16), chunk_samples):
                chunk = audio_int16[i:i + chunk_samples]
                yield TTSAudioRawFrame(
                    audio=chunk.tobytes(),
                    sample_rate=self.TADA_SAMPLE_RATE,
                    num_channels=self.TADA_NUM_CHANNELS,
                    context_id=context_id,
                )
        except Exception as e:
            logger.error(f"TadaMLXTTSService error: {e}")
            yield ErrorFrame(error=str(e))
