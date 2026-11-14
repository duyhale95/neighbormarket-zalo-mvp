import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.deplao_compat import verify_strict_runtime


class DeplaoCompatibilityTests(unittest.TestCase):
    def test_unknown_missing_or_unpatched_engine_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(OSError):
                verify_strict_runtime(root)
            engine = root / 'src/services/workflow/WorkflowEngineService.ts'
            engine.parent.mkdir(parents=True)
            engine.write_text('unreviewed engine', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Live generation blocked'):
                verify_strict_runtime(root)

    def test_exact_source_check_normalizes_windows_newlines_and_bom(self):
        fixture = 'reviewed strict engine\n'
        digest = hashlib.sha256(fixture.encode()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / 'src/services/workflow/WorkflowEngineService.ts'
            engine.parent.mkdir(parents=True)
            engine.write_bytes(b'\xef\xbb\xbf' + fixture.replace('\n', '\r\n').encode())
            with patch('tools.deplao_compat.STRICT_ENGINE_SHA256', digest):
                self.assertEqual(verify_strict_runtime(root), digest)
                engine.write_text(fixture + 'changed', encoding='utf-8')
                with self.assertRaises(ValueError):
                    verify_strict_runtime(root)
