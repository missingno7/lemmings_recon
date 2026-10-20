"""Shared original IRQ transport: actual pinned IRET, live IVT, bounded state."""
import unittest
import verification as v

class HardwareTransportTests(unittest.TestCase):
    def machine(self,flags=0xAD7):
        c=dict(load=0x1010,seed=8)
        memory,device=v.initial_memory(c)
        r=v.default_regs(c['load'],8,flags=flags);r['ip']=0x04AA
        # A constructed IVT pointing directly to an identified original IRET
        # isolates shared transport. Game suites execute the complete handlers.
        v.put16(memory,0,8*4,0x18B1);v.put16(memory,0,8*4+2,c['load'])
        instructions={p:next(v.MD.disasm(v.IMAGE[p:p+8],p)) for p in (0x04AA,0x18B1)}
        access=v.BusAccess(c,memory,r,device,max_events=16)
        delivered=[];entries=[]
        def before(m,i):
            if i.address==0x04AA:
                if not delivered:
                    delivered.append(m.hardware_interrupt(8,returns={0x18B1}))
                    if delivered[-1]:return True
                m.stop(0);return True
            state=m.state();entries.append(state)
            self.assertEqual(state['flags']&0x300,0)
            self.assertEqual(state['sp'],(r['sp']-6)&65535)
            self.assertEqual([v.get16(memory,state['ss'],(state['sp']+2*n)&65535) for n in range(3)],
                             [0x04AA,c['load'],flags])
            return False
        machine=v.OriginalMachine(c,memory,r,device,False,instructions=instructions,access=access,
            outer_returns=(),before=before,max_steps=2)
        return machine,delivered,entries,r

    def test_live_hardware_frame_and_original_iret_restore_the_poll(self):
        machine,delivered,entries,r=self.machine()
        out=machine.run()
        self.assertEqual(delivered,[True]);self.assertEqual(len(entries),1)
        self.assertEqual(out['regs'],r)
        self.assertEqual(out['sites'],{0x18B1})
        self.assertEqual(len(out['events']),16)
        self.assertEqual(machine.hardware_frames,[])

    def test_masked_pending_irq_has_no_stack_vector_or_register_effects(self):
        machine,delivered,entries,r=self.machine(0x8D7)
        before=bytes(machine.memory);out=machine.run()
        self.assertEqual(delivered,[False]);self.assertEqual(entries,[])
        self.assertEqual(out['regs'],r);self.assertEqual(out['memory'],before)
        self.assertEqual(len(out['events']),0);self.assertEqual(out['steps'],0)

    def test_return_sites_must_be_identified_original_iret(self):
        machine,_,_,_=self.machine()
        with self.assertRaisesRegex(v.OracleFailure,'identified IRET'):
            machine.hardware_interrupt(8,returns={0x04AA})

if __name__=='__main__':unittest.main()
