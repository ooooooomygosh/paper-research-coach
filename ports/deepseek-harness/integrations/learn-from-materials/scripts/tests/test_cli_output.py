"""Regressions for Windows code pages and Poppler text encoding."""
import io
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from cli_output import configure_output
from extractor.parsers.pdf import extract_with_pdftotext, count_pages


class CliOutputTests(unittest.TestCase):
    def test_gbk_logs_escape_symbols_without_losing_chinese(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='gbk')
        configure_output([stream])
        stream.write('检查通过 ✓ ✅'); stream.flush()
        self.assertEqual(stream.encoding, 'gbk')
        self.assertEqual(buffer.getvalue().decode('gbk'), '检查通过 \\u2713 \\u2705')

    def test_utf8_and_in_memory_streams_are_preserved(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='utf-8')
        memory = io.StringIO()
        configure_output([stream, memory])
        stream.write('检查通过 ✓ ✅'); stream.flush()
        memory.write('✓')
        self.assertEqual(buffer.getvalue().decode('utf-8'), '检查通过 ✓ ✅')
        self.assertEqual(memory.getvalue(), '✓')

    def test_poppler_utf8_text_does_not_decode_localized_stderr(self):
        result = types.SimpleNamespace(returncode=0, stdout='中文材料\f第二页'.encode('utf-8'),
                                       stderr='字体提示'.encode('gbk'))
        with patch('extractor.parsers.pdf.shutil.which', return_value='pdftotext'), \
             patch('extractor.parsers.pdf.subprocess.run', return_value=result) as run:
            self.assertEqual(extract_with_pdftotext('fixture.pdf'), '中文材料\f第二页')
        self.assertEqual(run.call_args.args[0][1:3], ['-enc', 'UTF-8'])
        self.assertNotIn('text', run.call_args.kwargs)

    def test_pdfinfo_page_count_ignores_diagnostic_encoding(self):
        result = types.SimpleNamespace(returncode=0, stdout=b'Pages: 3\n', stderr='提示'.encode('gbk'))
        with patch('extractor.parsers.pdf.shutil.which', return_value='pdfinfo'), \
             patch('extractor.parsers.pdf.subprocess.run', return_value=result):
            self.assertEqual(count_pages('fixture.pdf'), 3)

    def test_capability_and_static_clis_finish_under_gbk(self):
        env = dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING='gbk')
        commands = [
            [sys.executable, str(SCRIPTS/'extract.py'), '--check'],
            [sys.executable, str(SCRIPTS/'verify_static.py'), str(SCRIPTS.parent/'examples/features-zh.html')],
            [sys.executable, str(SCRIPTS/'render_page.py'), str(SCRIPTS.parent/'examples/overview-current-zh.json'),
             '--knowledge-base', str(SCRIPTS.parent/'examples/methods-demo-zh.learnkb'),
             '--output', os.devnull, '--check-only'],
        ]
        for command in commands:
            with self.subTest(script=Path(command[1]).name):
                result = subprocess.run(command, env=env, capture_output=True)
                self.assertEqual(result.returncode, 0, (result.stdout+result.stderr).decode('gbk', errors='replace'))
                self.assertNotIn(b'UnicodeEncodeError', result.stderr)


if __name__ == '__main__':
    unittest.main()
