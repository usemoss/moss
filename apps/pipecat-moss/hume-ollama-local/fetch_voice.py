"""Download a high-quality female voice reference from LibriTTS-R."""

from datasets import load_dataset
import soundfile as sf
import numpy as np

print("Finding female speaker...")
ds = load_dataset("parler-tts/libritts_r_filtered", "clean", split="test.clean", streaming=True)

for sample in ds:
    audio = sample["audio"]
    duration = len(audio["array"]) / audio["sampling_rate"]
    speaker = sample.get("speaker_id", 0)
    # Female speakers have even IDs in LibriTTS
    if speaker % 2 != 0:
        continue
    if duration >= 10:
        sf.write(
            "reference_voice.wav",
            np.array(audio["array"], dtype=np.float32),
            audio["sampling_rate"],
        )
        text = sample.get("text_normalized", sample.get("text", ""))
        print(f"Speaker: {speaker}")
        print(f"Duration: {duration:.1f}s at {audio['sampling_rate']}Hz")
        print(f"Text: {text}")
        break
