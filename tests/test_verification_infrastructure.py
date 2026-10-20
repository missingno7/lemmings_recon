"""Fail-closed observations shared by connected native/original campaigns."""
import copy
import unittest
import verification as v


class SharedVerificationTests(unittest.TestCase):
    def test_shared_device_trace_preserves_vga_order_state_and_budget(self):
        plain=v.new_device(0x80FD);packed=copy.deepcopy(plain);packed.trace=v.PackedDeviceTrace(4)
        memories=[bytearray(v.SIZE),bytearray(v.SIZE)]
        for dev,memory in zip((plain,packed),memories):
            dev.out(0x3C4,0x0F02,0x2D7);dev.out(0x3CE,0x0005,0xA02)
            dev.write(memory,0xA0003,0x96,0x6D7);dev.read(memory,0xA0003,0x202)
        self.assertEqual(memories[0],memories[1]);self.assertEqual(plain.state(),packed.state())
        self.assertEqual(list(packed.trace),plain.trace)
        clone=copy.deepcopy(packed.trace);clone.clear();self.assertEqual(len(clone),0)
        self.assertEqual(list(packed.trace),plain.trace)
        with self.assertRaises(v.OracleFailure):packed.trace.append(('write',0,0,0))

    def test_rep_scas_defines_flags_only_when_a_comparison_executes(self):
        for count in (0,1):
            with self.subTest(count=count):
                case=dict(load=0x1010,seed=0x8143)
                memory,device=v.initial_memory(case)
                r=v.default_regs(case['load'],1,ds=0x3000,es=0x3000)
                r.update(ip=0x8143,cx=count,ax=0,di=0x2000)
                v.put8(memory,0x3000,0x2000,0x0F)
                instructions={i.address:i for i in v.MD.disasm(v.IMAGE[0x8143:0x8147],0x8143)}
                def before(machine,instruction):
                    if instruction.address==0x8145:machine.stop(0);return True
                    return False
                access=v.BusAccess(case,memory,r,device,max_events=2)
                machine=v.OriginalMachine(case,memory,r,device,True,instructions=instructions,
                    access=access,outer_returns=(),max_steps=4,before=before)
                machine.mask=v.FLAGS&~0x10
                out=machine.run()
                self.assertEqual(out['regs']['di'],0x2000+count)
                self.assertEqual(out['mask'],v.FLAGS if count else v.FLAGS&~0x10)
                if count:self.assertTrue(out['regs']['flags']&0x10)
                else:self.assertEqual(out['regs']['flags'],r['flags'])

    def test_actual_byte_division_makes_arithmetic_flags_undefined(self):
        case=dict(load=0x1010,seed=1)
        memory,device=v.initial_memory(case)
        r=v.default_regs(case['load'],1,flags=0xAD7)
        r.update(ip=0x459C,ax=5000,cx=100)
        instructions={i.address:i for i in v.MD.disasm(v.IMAGE[0x459C:0x45A1],0x459C)}
        def before(machine,instruction):
            if instruction.address==0x459E:machine.stop(0);return True
            return False
        access=v.BusAccess(case,memory,r,device,max_events=1)
        out=v.OriginalMachine(case,memory,r,device,True,instructions=instructions,
            access=access,outer_returns=set(),max_steps=2,before=before).run()
        self.assertEqual(out['regs']['ax'],50)
        self.assertEqual(out['mask'],v.FLAGS&~0x8D5)
        self.assertEqual(out['steps'],1)
        self.assertEqual(out['regs']['flags']&0x600,r['flags']&0x600)

    def test_packed_observations_preserve_bus_order_masks_slices_and_budget_failures(self):
        rows=[]
        for packed in (False,True):
            memory=bytearray(v.SIZE)
            access=v.BusAccess({},memory,{},v.new_device(7),max_events=7,packed_events=packed)
            access.word_write(0xFFFF,0xF,0xABCD,0xFD7)
            access.word_read(0xFFFF,0xF,0x246,0xFC7)
            access.access('write',0xA0000,0x202,value=0x81)
            access.emit('out',0x3CE,0xFFFF,0x6D7,0xFC7)
            access.emit('in',0x201,0xEF,2)
            rows.append(list(access.events))
            self.assertEqual(access.events[-1],rows[-1][-1])
            self.assertEqual(access.events[::-2],rows[-1][::-2])
            self.assertEqual(list(copy.deepcopy(access.events)),rows[-1])
            with self.assertRaises(IndexError):_ = access.events[7]
            with self.assertRaises(v.OracleFailure):access.emit('in',0x201,0,2)
            self.assertEqual(len(access.events),7)
        self.assertEqual(*rows)

    def test_packed_comparator_still_detects_every_ordered_difference(self):
        class Device:
            trace=[]
            def state(self):return ()
        events=v.PackedEvents();events.append(('out',0x3CE,0x1234,0x246,v.FLAGS))
        ref=dict(regs={n:0 for n in v.REG_NAMES},status=0,memory=bytearray(1),
                 device=Device(),events=events,mask=v.FLAGS)
        actual=copy.deepcopy(ref);actual['events']=list(events)
        v.compare_states('packed/list',actual,ref)
        actual['events'][0]=('out',0x3CE,0x1235,0x246,v.FLAGS)
        with self.assertRaises(v.Mismatch):v.compare_states('packed mismatch',actual,ref)
        self.assertEqual(events.words.itemsize*len(events.words),20)

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
