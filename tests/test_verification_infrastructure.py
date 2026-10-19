"""Fail-closed observations shared by connected native/original campaigns."""
import copy
import unittest
import verification as v


class SharedVerificationTests(unittest.TestCase):
    def test_original_retf_executes_actual_words_with_offset_and_physical_wrap(self):
        site=0x953D
        instruction=next(v.MD.disasm(v.IMAGE[site:site+1],site))
        self.assertEqual(instruction.mnemonic,'retf')
        for load in v.LOADS:
            for ss,sp in ((0x5000,0x9000),(0x3000,0xFFFD),(0x3000,0xFFFE),(0x3000,0xFFFF),(0xFFFF,0xF),(0xA000,0x8000)):
                with self.subTest(load=load,ss=ss,sp=sp):
                    case=dict(load=load,seed=load)
                    memory,device=v.initial_memory(case)
                    r=v.default_regs(load,load,ss=ss,sp=sp,flags=0xD7);r['ip']=site
                    v.put16(memory,ss,sp,0xD00D,device)
                    v.put16(memory,ss,(sp+2)&0xFFFF,0x6201,device)
                    access=v.BusAccess(case,memory,r,device,max_events=4)
                    machine=v.OriginalMachine(case,memory,r,device,False,instructions={site:instruction},
                        access=access,outer_returns={site},max_steps=1,
                        far_returns={site:{(0x6201,0xD00D)}})
                    if sp>=0xFFFE:
                        with self.assertRaisesRegex(v.OracleFailure,'RETF reference limitation'):machine.run()
                        self.assertEqual(memory[v.physical(load,site)],0xCB)
                        continue
                    out=machine.run()
                    expected=dict(r,cs=0x6201,ip=0xD00D,sp=(sp+4)&0xFFFF)
                    self.assertEqual(out['regs'],expected)
                    self.assertEqual((out['steps'],out['sites']),(1,{site}))
                    self.assertEqual(out['far_return_events'],4)
                    self.assertEqual([e[1] for e in access.events],
                        [((v.physical(ss,(sp+2*w)&0xFFFF)+b)&v.MASK) for w in range(2) for b in range(2)])
                    self.assertEqual(memory[v.physical(load,site)],0xCB)

    def test_retf_read_provider_can_change_the_live_segment_and_stop_after_return(self):
        site=0x953D;case=dict(load=0x1010,seed=0)
        memory,device=v.initial_memory(case)
        r=v.default_regs(case['load'],0,flags=0xD7);r['ip']=site
        v.put16(memory,r['ss'],r['sp'],0xD00D)
        v.put16(memory,r['ss'],r['sp']+2,0x6201)
        class Access(v.BusAccess):
            def access(self,kind,address,flags,mask=v.FLAGS,value=None):
                got=super().access(kind,address,flags,mask,value)
                if address==v.physical(r['ss'],r['sp']) and 'segment' not in self.providers:
                    self.patch(r['ss'],r['sp']+2,0x6B71,'segment')
                return got
        access=Access(case,memory,r,device,max_events=4)
        instruction=next(v.MD.disasm(v.IMAGE[site:site+1],site))
        out=v.OriginalMachine(case,memory,r,device,False,instructions={site:instruction},
            access=access,outer_returns={site},max_steps=1,changed_return_status=9,
            far_returns={site:{(0x6201,0xD00D)}}).run()
        self.assertEqual((out['status'],out['regs']['cs'],out['regs']['ip'],out['regs']['sp']),
                         (9,0x6B71,0xD00D,r['sp']+4))

    def test_retf_later_read_does_not_reconsume_an_overwritten_ip_word(self):
        site=0x953D;case=dict(load=0x1010,seed=1)
        memory,device=v.initial_memory(case)
        r=v.default_regs(case['load'],1,flags=0xD7);r['ip']=site
        v.put16(memory,r['ss'],r['sp'],0xD00D)
        v.put16(memory,r['ss'],r['sp']+2,0x6201)
        class Access(v.BusAccess):
            def access(self,kind,address,flags,mask=v.FLAGS,value=None):
                got=super().access(kind,address,flags,mask,value)
                if address==v.physical(r['ss'],r['sp']+2) and 'old-ip' not in self.providers:
                    self.patch(r['ss'],r['sp'],0xBEEF,'old-ip')
                return got
        access=Access(case,memory,r,device,max_events=4)
        instruction=next(v.MD.disasm(v.IMAGE[site:site+1],site))
        out=v.OriginalMachine(case,memory,r,device,False,instructions={site:instruction},
            access=access,outer_returns={site},max_steps=1,
            far_returns={site:{(0x6201,0xD00D)}}).run()
        self.assertEqual((out['status'],out['regs']['ip']),(0,0xD00D))
        self.assertEqual(v.get16(out['memory'],r['ss'],r['sp']),0xBEEF)

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
