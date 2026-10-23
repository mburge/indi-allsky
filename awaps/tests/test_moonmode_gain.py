"""Exercise the real exposure classes without connecting to camera hardware."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from indi_allsky import constants
from indi_allsky.exposure.autogain_exposurepriority_dB import (
    IndiAllSky_Exposure_AutoGain_ExposurePriority_dB,
    IndiAllSky_Exposure_AutoGain_ExposurePriority_dB_1_10,
    IndiAllSky_Exposure_AutoGain_ExposurePriority_ISO,
    IndiAllSky_Exposure_AutoGain_ExposurePriority_ISO_1_100,
)


class MoonmodeGainTests(unittest.TestCase):
    classes = (
        IndiAllSky_Exposure_AutoGain_ExposurePriority_dB,
        IndiAllSky_Exposure_AutoGain_ExposurePriority_dB_1_10,
        IndiAllSky_Exposure_AutoGain_ExposurePriority_ISO,
        IndiAllSky_Exposure_AutoGain_ExposurePriority_ISO_1_100,
    )

    def camera(self, cls=None, night=True, moon=True):
        cls = cls or IndiAllSky_Exposure_AutoGain_ExposurePriority_dB_1_10
        obj = cls.__new__(cls)
        obj.night_av = [False] * (max(constants.NIGHT_NIGHT, constants.NIGHT_MOONMODE) + 1)
        obj.night_av[constants.NIGHT_NIGHT] = night
        obj.night_av[constants.NIGHT_MOONMODE] = moon
        obj._expUtils = SimpleNamespace(
            GAIN_MIN_NIGHT=100.0, GAIN_MAX_NIGHT=300.0,
            GAIN_MIN_MOONMODE=50.0, GAIN_MAX_MOONMODE=150.0,
            EXPOSURE_MAX=9.0, EXPOSURE_MIN_NIGHT=0.001, EXPOSURE_MIN_DAY=0.00001,
        )
        return obj

    def test_moonlit_night_uses_moonmode_limits_for_every_gain_scale(self):
        for cls in self.classes:
            with self.subTest(cls=cls.__name__):
                obj = self.camera(cls)
                self.assertEqual((obj.gain_min, obj.gain_max), (50.0, 150.0))

    def test_normal_night_retains_night_limits(self):
        obj = self.camera(moon=False)
        self.assertEqual((obj.gain_min, obj.gain_max), (100.0, 300.0))

    def test_daytime_preserves_previous_fallback_even_with_stale_moon_flag(self):
        obj = self.camera(night=False)
        self.assertEqual((obj.gain_min, obj.gain_max), (100.0, 300.0))

    def test_mode_switch_is_observed_without_recreating_the_controller(self):
        obj = self.camera(moon=False)
        self.assertEqual(obj.gain_max, 300.0)
        obj.night_av[constants.NIGHT_MOONMODE] = True
        self.assertEqual(obj.gain_max, 150.0)
        obj.night_av[constants.NIGHT_MOONMODE] = False
        self.assertEqual(obj.gain_max, 300.0)

    def test_increasing_gain_clamps_to_moonmode_maximum(self):
        obj = self.camera()
        _, _, gain_db, _ = obj.increase_gain(9.0, 100.0, 900.0)
        self.assertAlmostEqual(obj.dB2gain(gain_db), 150.0)

    def test_decreasing_gain_clamps_to_moonmode_minimum(self):
        obj = self.camera()
        _, _, gain_db, _ = obj.reduce_gain(9.0, 100.0, 0.09)
        self.assertAlmostEqual(obj.dB2gain(gain_db), 50.0)


if __name__ == '__main__':
    unittest.main()
