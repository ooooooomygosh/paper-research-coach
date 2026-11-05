from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finalize import publish_move


class PublishRetryTests(unittest.TestCase):
    def setup_paths(self, temporary):
        out = Path(temporary) / 'out'
        stage = out / 'stage'
        stage.mkdir(parents=True)
        source, destination = stage / 'artifact', out / 'artifact'
        source.mkdir()
        (source / 'keep.txt').write_text('content', encoding='utf-8')
        return source, destination, stage, out

    def test_transient_windows_directory_lock_retries_then_preserves_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, destination, stage, out = self.setup_paths(temporary)
            original = Path.rename
            calls = []
            def rename(path, target):
                calls.append(target)
                if len(calls) < 3:
                    error = PermissionError('transient scanner lock')
                    error.winerror = 32
                    raise error
                return original(path, target)
            with patch.object(Path, 'rename', rename), patch('finalize.time.sleep') as sleep:
                publish_move(source, destination, stage, out)
            self.assertEqual(len(calls), 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual((destination / 'keep.txt').read_text(encoding='utf-8'), 'content')
            self.assertFalse(source.exists())

    def test_existing_target_is_preserved_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, destination, stage, out = self.setup_paths(temporary)
            destination.mkdir()
            with patch.object(Path, 'rename') as rename, self.assertRaisesRegex(ValueError, 'exists'):
                publish_move(source, destination, stage, out)
            rename.assert_not_called()
            self.assertTrue((source / 'keep.txt').is_file())

    def test_persistent_lock_stops_at_five_attempts(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, destination, stage, out = self.setup_paths(temporary)
            error = PermissionError('still locked')
            error.winerror = 5
            with patch.object(Path, 'rename', side_effect=error) as rename, patch('finalize.time.sleep') as sleep, self.assertRaises(PermissionError):
                publish_move(source, destination, stage, out)
            self.assertEqual(rename.call_count, 5)
            self.assertEqual(sleep.call_count, 4)
            self.assertTrue((source / 'keep.txt').is_file())
            self.assertFalse(destination.exists())

    def test_destination_outside_output_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, _, stage, out = self.setup_paths(temporary)
            with patch.object(Path, 'rename') as rename, self.assertRaisesRegex(ValueError, 'escaped'):
                publish_move(source, Path(temporary) / 'escaped', stage, out)
            rename.assert_not_called()


if __name__ == '__main__':
    unittest.main()
