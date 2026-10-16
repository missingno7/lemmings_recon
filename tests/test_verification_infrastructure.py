"""Fail-closed observations shared by connected native/original campaigns."""
import copy
import unittest
import verification as v


class SharedVerificationTests(unittest.TestCase):
    def test_word_high_byte_is_physical_successor_and_separate_ea_wraps(self):
        memory=bytearray(v.SIZE)
        access=v.BusAccess({},memory,{},None,max_events=8)
        access.word_write(0x1000,0xFFFF,0xABCD,2)
        access.word_write(0x1000,0,0x1234,2)
        self.assertEqual([e[1] for e in access.events],
                         [0x1FFFF,0x20000,0x10000,0x10001])
        self.assertEqual(access.word_read(0x1000,0xFFFF,2),0xABCD)
        access.word_write(0xFFFF,0xF,0x5678,2)
        self.assertEqual((memory[0xFFFFF],memory[0]),(0x78,0x56))

    def test_event_exhaustion_is_oracle_failure_not_mutation_detection(self):
        access=v.BusAccess({},bytearray(1),{},None,max_events=1)
        access.access('read',0,2)
        with self.assertRaises(v.OracleFailure):access.access('read',0,2)
        self.assertNotIsInstance(v.OracleFailure(),v.Mismatch)

    def test_comparator_checks_defined_flags_and_ordered_observations(self):
        class Device:
            trace=[]
            def state(self):return ()
        registers={n:0 for n in v.REG_NAMES}
        ref=dict(regs=registers,status=0,memory=bytearray(1),device=Device(),
                 events=[('read',0,0,2,v.FLAGS)],providers=set(),cursor=0,
                 mask=v.FLAGS&~0x10)
        actual=copy.deepcopy(ref);actual['regs']['flags']=0x10
        v.compare_states('undefined AF',actual,ref)
        actual['regs']['flags']|=0x40
        with self.assertRaises(v.Mismatch):v.compare_states('defined ZF',actual,ref)
        actual=copy.deepcopy(ref);actual['events'][0]=('write',0,0,2,v.FLAGS)
        with self.assertRaises(v.Mismatch):v.compare_states('access kind',actual,ref)


if __name__=='__main__':unittest.main()
