"""Unchanged read-hook injections must not corrupt original REP flags."""
import unittest
import verification as v

class OriginalRepFlagsTests(unittest.TestCase):
    def test_original_add_and_rep_preserve_af_and_actual_copy_order(self):
        instructions={p:next(v.MD.disasm(v.IMAGE[p:p+8],p)) for p in (0x37B2,0x37B4,0x37B6)}
        for backward,overlap in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(backward=backward,overlap=overlap):
                c=dict(load=0x1010,seed=0x37B4)
                memory,device=v.initial_memory(c)
                r=v.default_regs(c['load'],c['seed'],ds=0x19B9,flags=0x202|(0x400 if backward else 0))
                source=0x1CF7;dest=source+(-1 if backward else 1) if overlap else 0x17CB
                r.update(ip=0x37B2,si=0x1B4B,ax=0x1AC,di=dest,cx=28,es=r['ds'])
                expected=bytearray(memory);step=-1 if backward else 1
                for n in range(28):
                    expected[v.physical(r['es'],dest+step*n)]=expected[v.physical(r['ds'],source+step*n)]
                access=v.BusAccess(c,memory,r,device,max_events=56)
                def before(m,i):
                    if i.address==0x37B6:m.stop(0);return True
                    return False
                out=v.OriginalMachine(c,memory,r,device,False,instructions=instructions,access=access,
                    outer_returns=(),before=before,max_steps=64,unhooked_movsb={0x37B4}).run()
                self.assertEqual(out['memory'],expected)
                self.assertEqual(out['regs']['flags'],0x212|(0x400 if backward else 0))
                self.assertEqual(out['regs']['cx'],0)
                self.assertEqual(len(out['events']),56)
                self.assertTrue(all(e[3]==out['regs']['flags'] for e in out['events']))

    def test_physical_wrap_and_zero_count_retain_original_execution(self):
        instructions={p:next(v.MD.disasm(v.IMAGE[p:p+8],p)) for p in (0x37B2,0x37B4,0x37B6)}
        for count in (0,1,28):
            c=dict(load=0x1010,seed=7);memory,device=v.initial_memory(c)
            r=v.default_regs(c['load'],7,ds=0xFFFF,flags=0x202)
            r.update(ip=0x37B2,si=0x1B4B,ax=0x1AC,di=0x17CB,cx=count,es=0xFFFF)
            expected=bytearray(memory)
            for n in range(count):expected[v.physical(r['es'],r['di']+n)]=expected[v.physical(r['ds'],0x1CF7+n)]
            access=v.BusAccess(c,memory,r,device,max_events=56)
            def before(m,i):
                if i.address==0x37B6:m.stop(0);return True
                return False
            out=v.OriginalMachine(c,memory,r,device,False,instructions=instructions,access=access,
                outer_returns=(),before=before,max_steps=64,unhooked_movsb={0x37B4}).run()
            self.assertEqual(out['memory'],expected);self.assertEqual(out['regs']['flags'],0x212)
            self.assertEqual(len(out['events']),2*count)

if __name__=='__main__':unittest.main()
