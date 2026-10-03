import unittest

import numpy as np

from audio_capture_app import resample_to_16khz
from audio_capture_gui import safe_name


class AudioCaptureTests(unittest.TestCase):
    def test_resample_48khz_to_exact_16khz(self):
        source = np.zeros(48_000, dtype=np.float32)
        result = resample_to_16khz(source, 48_000)
        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(len(result), 16_000)

    def test_resample_accepts_other_source_rate(self):
        source = np.ones(44_100, dtype=np.float32)
        result = resample_to_16khz(source, 44_100)
        self.assertAlmostEqual(len(result) / 16_000, 1.0, places=3)

    def test_safe_name_removes_windows_path_characters(self):
        self.assertEqual(safe_name('bad<>:"/\\|?*name'), "bad_________name")
        self.assertEqual(safe_name("..."), "capture")


if __name__ == "__main__":
    unittest.main()
