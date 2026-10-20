"""Source planning must describe what the native compiler actually consumes."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import cbuild
from bounded_process import temporary_build_directory

class SourcePlanningTests(unittest.TestCase):
    def test_alias_clusters_resolve_to_existing_implementations(self):
        self.assertEqual([p.name for p in cbuild.source_files('palette_timer')],['palette_ports.c'])
        for cluster in ('game_timer','menu_timer','timer_install','timer_tail'):
            files=cbuild.source_files(cluster)
            self.assertEqual(files[0].name,'timer_tail.c')
            self.assertTrue(all(p.is_file() for p in files))
            self.assertEqual(len(files),len(set(files)))
    def test_main_composes_the_actual_timer_closure_once(self):
        main=cbuild.source_files('main_menu')
        self.assertTrue(set(cbuild.source_files('menu_timer'))<=set(main))
        self.assertTrue(set(cbuild.source_files('keyboard_input'))<=set(main))
        self.assertEqual(len(main),len(set(main)))
        self.assertTrue(all(p.is_file() for p in main))
    def test_build_uses_resolved_sources_and_numeric_mutation(self):
        with temporary_build_directory(prefix='cbuild-test-',parent=ROOT/'build') as directory:
            with patch.object(cbuild,'compiler',return_value='compiler-fixture'),patch.object(cbuild,'run_bounded') as run:
                cbuild.build(Path(directory)/'unused.dll',103,'main_menu')
            argv=run.call_args.args[0]
            self.assertEqual([Path(p) for p in argv if p.endswith('.c')],list(cbuild.source_files('main_menu')))
            self.assertIn('-DPALETTE_PUBLISH_MUTATION=3',argv)
            self.assertIn('-DMAIN_MENU_MUTATION=0',argv)
            self.assertEqual(run.call_args.kwargs['timeout'],60)
            self.assertEqual(run.call_args.kwargs['memory_mib'],256)
    def test_palette_manifest_pins_used_symbols_without_status_annotations(self):
        sys.path.insert(0,str(ROOT/'tests'))
        import palette_transition
        paths=palette_transition.input_hashes(True)
        self.assertNotIn('metadata/symbols.json',paths)
        for path in ('c/lemmings_sym.h','src/palette_frontends.asm',
                     'src/input_menu_and_retry.asm','metadata/oracle.json',
                     'tests/verification.py','c/palette_transition.c'):
            self.assertIn(path,paths)

    def test_unknown_cluster_fails_before_planning(self):
        with self.assertRaises(ValueError):cbuild.source_files('unidentified_game')

if __name__=='__main__':unittest.main()
