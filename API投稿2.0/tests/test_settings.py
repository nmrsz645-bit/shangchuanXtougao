import tempfile
import unittest
from pathlib import Path


class SettingsTests(unittest.TestCase):
    def test_callback_requires_auth_code(self):
        from desktop_posting.settings import callback_auth_code

        with self.assertRaisesRegex(ValueError, "auth_code"):
            callback_auth_code("https://example.com/callback")

    def test_settings_round_trip_stays_under_base_dir(self):
        from desktop_posting.settings import AppSettings, load_settings, save_settings

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            save_settings(root, AppSettings(qianchuan_app_id="id", submission_sheet_url="https://x"))
            self.assertEqual("id", load_settings(root).qianchuan_app_id)
            self.assertTrue((root / "config" / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
