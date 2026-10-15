"""Sound coverage must exclude unresolved bytes and bootstrap must preserve C ASM."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sound


class SoundScopeTests(unittest.TestCase):
    def test_shared_ranges_count_bytes_once(self):
        analysis={'instructions':[dict(address=0,size=2),dict(address=3,size=2)]}
        rows=[dict(address=0,size=5,symbol_name='prefix',c_implementation='c.c',
                   c_code_ranges=[[0,2],[3,5]]),
              dict(address=3,size=2,symbol_name='tail',c_implementation='c.c')]
        self.assertEqual(sound.translated_scope(b'12345',analysis,rows),(2,4))

    def test_unknown_and_outside_bytes_fail_closed(self):
        analysis={'instructions':[dict(address=0,size=2),dict(address=3,size=2)]}
        for ranges in ([[0,5]],[[0,6]],[[-1,2]],[[0,1]]):
            with self.subTest(ranges=ranges):
                rows=[dict(address=0,size=5,symbol_name='bad',c_implementation='c.c',
                           c_code_ranges=ranges)]
                with self.assertRaises(ValueError):
                    sound.translated_scope(b'12345',analysis,rows)

    def test_bootstrap_cannot_overwrite_maintained_sound(self):
        with tempfile.TemporaryDirectory(prefix='sound-scope-',dir=sound.BUILD) as directory:
            root=Path(directory)
            (root/'src/sound').mkdir(parents=True)
            (root/'metadata').mkdir()
            source=root/'src/sound/adlib.asm'
            source.write_text('; maintained semantic contract\n')
            (root/'metadata/adlib-symbols.json').write_text(json.dumps([
                dict(c_implementation='c/sound_latches.c')]))
            with patch.object(sound,'ROOT',root),self.assertRaisesRegex(ValueError,'Refusing to overwrite'):
                sound.generate_driver('adlib',b'',{})
            self.assertEqual(source.read_text(),'; maintained semantic contract\n')


if __name__=='__main__':
    unittest.main()
