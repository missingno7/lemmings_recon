"""Keep the edit-loop gate separate from full contract acceptance."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import verify

spec = importlib.util.spec_from_file_location('lemmings_coverage', ROOT / 'tools/coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class VerificationModeTests(unittest.TestCase):
    def test_commands_select_only_the_requested_gate(self):
        for args, stub, contracts in (([], True, False),
                                      (['--contracts'], True, True),
                                      (['--skip-stub'], False, False)):
            with self.subTest(args=args), patch.object(verify, 'verify') as gate:
                with contextlib.redirect_stdout(io.StringIO()):
                    verify.main(args)
                gate.assert_called_once_with(stub, contracts=contracts)

    def test_contracts_cannot_skip_unpacker_checks(self):
        with patch.object(verify, 'verify') as gate:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                verify.main(['--contracts', '--skip-stub'])
            gate.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'requires unpacker'):
            verify.verify(False, contracts=True)

    def test_failure_invalidates_only_the_requested_report(self):
        # Fail at assembly after real input identity checks, before execution.
        for contracts in (False, True):
            with self.subTest(contracts=contracts), tempfile.TemporaryDirectory(
                    prefix='verification-modes-', dir=ROOT / 'build') as directory:
                folder = Path(directory)
                static, full = folder / 'static-verification.json', folder / 'verification.json'
                static.write_bytes(b'previous static evidence')
                full.write_bytes(b'previous full evidence')
                with patch.object(verify, 'BUILD', folder), patch.object(
                        verify, 'assemble', side_effect=RuntimeError('constructed assembly failure')):
                    with self.assertRaisesRegex(RuntimeError, 'constructed assembly failure'):
                        verify.verify(contracts=contracts)
                invalidated, retained = (full, static) if contracts else (static, full)
                self.assertFalse(invalidated.exists())
                self.assertEqual(retained.read_bytes(),
                                 b'previous static evidence' if contracts else b'previous full evidence')

    def test_aggregate_rejects_static_legacy_and_incomplete_evidence(self):
        full = dict(verification_scope='contracts', bounded_unpacker_checks=True,
                    bounded_extractor_checks=True, verification_inputs={})
        reports = [dict(full, verification_scope='static'),
                   dict(full, bounded_unpacker_checks=False),
                   dict(full, bounded_extractor_checks=False),
                   {k: v for k, v in full.items() if k != 'verification_scope'}]
        for report in reports:
            with self.subTest(report=report), patch.object(coverage, 'read_json', return_value=report):
                with self.assertRaisesRegex(ValueError, '--contracts'):
                    coverage.contract_verification()

    def test_aggregate_requires_matching_full_report_inputs(self):
        with tempfile.TemporaryDirectory(prefix='verification-freshness-',
                                         dir=ROOT / 'build') as directory:
            folder = Path(directory)
            source = folder / 'source.txt'
            source.write_bytes(b'accepted input')
            report = dict(verification_scope='contracts', bounded_unpacker_checks=True,
                          bounded_extractor_checks=True,
                          verification_inputs={'source.txt': coverage.sha(source.read_bytes())})
            (folder / 'verification.json').write_text(json.dumps(report))
            with patch.object(coverage, 'BUILD', folder), patch.object(coverage, 'ROOT', folder):
                self.assertEqual(coverage.contract_verification(), report)
                source.write_bytes(b'changed input')
                with self.assertRaisesRegex(ValueError, 'Stale contract verification'):
                    coverage.contract_verification()


if __name__ == '__main__':
    unittest.main()
