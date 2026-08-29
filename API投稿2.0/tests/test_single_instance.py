import tempfile
import unittest
from pathlib import Path


class SingleInstanceTests(unittest.TestCase):
    def test_second_lock_for_same_directory_is_rejected_until_first_closes(self):
        from desktop_posting.single_instance import acquire_instance_lock

        with tempfile.TemporaryDirectory() as temp:
            base_dir = Path(temp)
            first = acquire_instance_lock(base_dir)
            self.assertIsNotNone(first)
            self.assertIsNone(acquire_instance_lock(base_dir))
            first.close()
            second = acquire_instance_lock(base_dir)
            self.assertIsNotNone(second)
            second.close()


if __name__ == "__main__":
    unittest.main()
