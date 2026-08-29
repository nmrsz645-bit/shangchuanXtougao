import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class MainTests(unittest.TestCase):
    def test_default_base_dir_uses_exe_dir_when_frozen(self):
        from desktop_posting.main import default_base_dir

        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / "API投稿2.0.exe"
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe)):
                self.assertEqual(exe.parent, default_base_dir())


if __name__ == "__main__":
    unittest.main()
