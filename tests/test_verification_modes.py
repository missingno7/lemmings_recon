"""Keep the edit-loop gate separate from full contract acceptance."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import verify
from bounded_process import temporary_build_directory

spec = importlib.util.spec_from_file_location('lemmings_coverage', ROOT / 'tools/coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class VerificationModeTests(unittest.TestCase):
    def test_inventory_never_invokes_aggregate_acceptance(self):
        with patch.object(coverage, 'inventory', return_value=({}, 'inventory')), patch.object(
                coverage, 'report', side_effect=AssertionError('aggregate must stay explicit')) as full:
            with contextlib.redirect_stdout(io.StringIO()):coverage.main(['--inventory'])
            full.assert_not_called()

    def test_static_inventory_rejects_stale_and_wrong_scope_evidence(self):
        with temporary_build_directory(prefix='inventory-evidence-', parent=ROOT/'build') as directory:
            folder=Path(directory);source=folder/'source.txt';source.write_bytes(b'accepted')
            image=b'pinned image'
            report=dict(verification_scope='static',bounded_unpacker_checks=True,canonical_sha256=coverage.sha(image),
                byte_exact_asm_bytes=len(image),verification_inputs={'source.txt':coverage.sha(source.read_bytes())})
            path=folder/'static-verification.json'
            with patch.object(coverage,'BUILD',folder),patch.object(coverage,'ROOT',folder):
                self.assertFalse(coverage.static_identity_evidence(image)['current'])
                path.write_text(json.dumps(report))
                self.assertTrue(coverage.static_identity_evidence(image)['current'])
                report['bounded_unpacker_checks']=False
                path.write_text(json.dumps(report))
                self.assertFalse(coverage.static_identity_evidence(image)['current'])
                del report['bounded_unpacker_checks']
                path.write_text(json.dumps(report))
                self.assertFalse(coverage.static_identity_evidence(image)['current'])
                report['bounded_unpacker_checks']=True;path.write_text(json.dumps(report))
                self.assertFalse(coverage.static_identity_evidence(b'other image')['current'])
                source.write_bytes(b'changed')
                self.assertEqual(coverage.static_identity_evidence(image)['stale_inputs'],['source.txt'])
                source.write_bytes(b'accepted');report['verification_scope']='contracts'
                path.write_text(json.dumps(report))
                self.assertFalse(coverage.static_identity_evidence(image)['current'])

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
            with self.subTest(contracts=contracts), temporary_build_directory(
                    prefix='verification-modes-', parent=ROOT / 'build') as directory:
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
        with temporary_build_directory(prefix='verification-freshness-',
                                         parent=ROOT / 'build') as directory:
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
