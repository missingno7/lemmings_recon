"""Aggregate acceptance requires every registry receipt, including composition."""
import contextlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from bounded_process import temporary_build_directory
from difftest import SUITES,Suite
spec=importlib.util.spec_from_file_location('receipt_coverage',ROOT/'tools/coverage.py')
coverage=importlib.util.module_from_spec(spec);spec.loader.exec_module(coverage)


class ReceiptTests(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self):
        with temporary_build_directory(prefix='receipt-accounting-',parent=ROOT/'build') as directory:
            root=Path(directory);(root/'metadata').mkdir();(root/'tests').mkdir();(root/'assets').mkdir()
            (root/'metadata/sound-oracle.json').write_text('{}')
            (root/'assets/vgalemmi.exe').write_bytes(b'packed fixture')
            for name in ('leaf','parent','host_vga','sound_latches','pcspeaker'):
                (root/f'tests/{name}.py').write_text('fixture '+name)
            image=b'image fixture'
            def report(name,**changes):
                row=dict(image='main',image_sha256=coverage.sha(image),case_count=1,
                         executed_instruction_addresses=[16],input_hashes={
                             f'tests/{name}.py':coverage.sha((root/f'tests/{name}.py').read_bytes()),
                             'assets/vgalemmi.exe':coverage.sha((root/'assets/vgalemmi.exe').read_bytes())})
                row.update(changes);(root/(name+'.json')).write_text(json.dumps(row));return row
            with patch.object(coverage,'ROOT',root),patch.object(coverage,'BUILD',root):
                yield root,image,report

    def test_registry_declares_one_required_receipt_and_role_per_suite(self):
        self.assertEqual(len({s.report_path for s in SUITES}),len(SUITES))
        self.assertTrue(all(s.accounting_role in ('instruction','component','composition','protected') for s in SUITES))
        by_name={s.name:s for s in SUITES}
        for name in ('startup','game_frame','game_loop','resource_retry','pcspeaker_dispatch','host_journey'):
            self.assertTrue(by_name[name].report_path.endswith('.json'))
        self.assertEqual(by_name['host_journey'].accounting_role,'composition')

    def test_missing_new_composition_receipt_cannot_escape_reconciliation(self):
        suites=[Suite('leaf',1,1,'leaf.json','instruction'),Suite('parent',1,1,'parent.json','composition')]
        with self.assertRaisesRegex(ValueError,'omitted required suites parent'):
            coverage.reconcile_receipts({'leaf':{}},suites)
        with self.fixture() as (_,image,report):
            report('leaf')
            with self.assertRaisesRegex(ValueError,'Missing required native receipt: parent'):
                coverage.registry_receipts(image,{},suites=suites)

    def test_composition_is_required_but_gives_no_extra_instruction_or_byte_credit(self):
        suites=[Suite('leaf',1,1,'leaf.json','instruction'),Suite('parent',1,1,'parent.json','composition')]
        with self.fixture() as (_,image,report):
            report('leaf');report('parent',executed_instruction_addresses=[16,99],translated_code_bytes=9999)
            receipts=coverage.registry_receipts(image,{},suites=suites)
            self.assertEqual(set(receipts),{'leaf','parent'})
            self.assertEqual(set.union(*(r['main_sites'] for r in receipts.values())),{16})
            self.assertEqual(receipts['parent']['main_sites'],set())
            self.assertNotIn('translated_code_bytes',receipts['parent'])

    def test_stale_composition_inputs_and_failed_host_receipts_fail_closed(self):
        suite=Suite('host_vga',1,1,'host_vga.json','composition')
        with self.fixture() as (root,image,report):
            report('host_vga',accepted=True)
            self.assertIn('host_vga',coverage.registry_receipts(image,{},suites=[suite]))
            (root/'tests/host_vga.py').write_text('changed provider')
            with self.assertRaisesRegex(ValueError,'Stale native receipt host_vga'):
                coverage.registry_receipts(image,{},suites=[suite])
            report('host_vga',accepted=False)
            with self.assertRaisesRegex(ValueError,'Failed native receipt'):
                coverage.registry_receipts(image,{},suites=[suite])

    def test_source_scope_and_image_identity_are_mandatory(self):
        suite=Suite('leaf',1,1,'leaf.json','instruction')
        with self.fixture() as (root,image,report):
            row=report('leaf',image_sha256='wrong')
            with self.assertRaisesRegex(ValueError,'oracle identity changed'):
                coverage.registry_receipts(image,{},suites=[suite])
            row=report('leaf');del row['input_hashes']['tests/leaf.py']
            (root/'leaf.json').write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'scope/source'):
                coverage.registry_receipts(image,{},suites=[suite])

    def test_component_sites_remain_separate_from_identical_main_offsets(self):
        suites=[Suite('leaf',1,1,'leaf.json','instruction'),
                Suite('pcspeaker',1,1,'pcspeaker.json','component'),
                Suite('sound_latches',1,1,'sound_latches.json','component')]
        with self.fixture() as (root,image,report):
            pins={name:dict(image_sha256=coverage.sha(name.encode())) for name in ('pcspeaker','adlib','tandysnd')}
            (root/'metadata/sound-oracle.json').write_text(json.dumps(pins))
            report('leaf')
            report('pcspeaker',image='pcspeaker',image_sha256=pins['pcspeaker']['image_sha256'],
                   child_instruction_addresses=[16,17])
            row=report('sound_latches',components={name:dict(pins[name],executed_instruction_addresses=[16])
                                                  for name in ('adlib','tandysnd')})
            del row['image_sha256'];del row['image']
            (root/'sound_latches.json').write_text(json.dumps(row))
            receipts=coverage.registry_receipts(image,{},suites=suites)
            self.assertEqual(receipts['leaf']['main_sites'],{16})
            self.assertEqual(receipts['pcspeaker']['main_sites'],set())
            self.assertEqual(receipts['pcspeaker']['component_sites'],{'pcspeaker':{16,17}})
            self.assertEqual(receipts['sound_latches']['component_sites'],{'adlib':{16},'tandysnd':{16}})


if __name__=='__main__':unittest.main()
