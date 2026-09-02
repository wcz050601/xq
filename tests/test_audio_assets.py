import unittest
import wave
from pathlib import Path

from xq.audio import EVENT_FILES


class AudioAssetTests(unittest.TestCase):
    def test_all_event_sounds_are_valid_pcm_wav_files(self):
        root = Path(__file__).resolve().parent.parent / "assets" / "sounds"
        for event, filename in EVENT_FILES.items():
            with self.subTest(event=event):
                path = root / filename
                self.assertTrue(path.exists())
                with wave.open(str(path), "rb") as sound:
                    self.assertEqual(sound.getsampwidth(), 2)
                    self.assertEqual(sound.getnchannels(), 1)
                    self.assertGreater(sound.getnframes(), 1000)


if __name__ == "__main__":
    unittest.main()
