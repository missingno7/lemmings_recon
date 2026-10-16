"""Dependency selection must retain shared tails, open domains and cycles."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from graph import body,dependency_order,routine_views

class GraphTests(unittest.TestCase):
    def test_explicit_native_ranges_do_not_require_a_physical_entry_size(self):
        analysis=dict(instructions=[dict(address=0,mnemonic='nop',size=1),
                                    dict(address=1,mnemonic='ret',size=1)],
                      edges=[dict(source=0,target=1,kind='fallthrough')],
                      unresolved=[],routines=[0])
        entry=dict(address=0,segment=0,kind='entry',size=None,symbol_name='SharedParent',
                   verification_status='TESTED',c_implementation='fixture.c',c_code_ranges=[[0,2]])
        self.assertEqual(routine_views(analysis,[entry])[0]['sites'],{0,1})
        del entry['c_code_ranges']
        with self.assertRaisesRegex(ValueError,'Missing native extent'):
            routine_views(analysis,[entry])

    def test_native_continuation_has_a_scope_without_closing_its_parent(self):
        analysis=dict(instructions=[dict(address=p,mnemonic=m,size=n) for p,m,n in
            ((0,'nop',1),(1,'call',3),(4,'nop',1),(5,'ret',1),(8,'ret',1))],
            edges=[dict(source=a,target=b,kind=k) for a,b,k in
                ((0,1,'fallthrough'),(1,8,'call'),(1,4,'fallthrough'),(4,5,'fallthrough'))],
            unresolved=[],routines=[0,8])
        ledger=[dict(address=0,segment=0,kind='entry',size=6,symbol_name='Parent',verification_status='UNTRANSLATED'),
                dict(address=1,segment=0,kind='continuation',size=3,symbol_name='NativeSpan',verification_status='TESTED',c_implementation='fixture.c'),
                dict(address=4,segment=0,kind='continuation',size=0,symbol_name='Resume',verification_status='UNRESOLVED')]
        views=routine_views(analysis,ledger)
        self.assertEqual(views[1]['sites'],{1});self.assertEqual(views[1]['boundaries'],{4})
        self.assertEqual(views[1]['callees'],{8});self.assertNotIn(4,views)
        self.assertEqual(views[0]['sites'],{0,1,4,5})
        self.assertFalse(views[0]['symbol'].get('c_implementation'))

    def test_shared_tail_and_call_have_different_ownership(self):
        instructions={p:dict(mnemonic=m,size=1) for p,m in ((0,'call'),(1,'jmp'),(3,'ret'),(9,'ret'))}
        edges={0:[dict(kind='call',target=9),dict(kind='fallthrough',target=1)],1:[dict(kind='branch',target=3)]}
        view=body(0,instructions,edges,{3:['fixture frontier']})
        self.assertEqual(view['sites'],{0,1,3});self.assertEqual(view['callees'],{9})
        self.assertEqual(view['problems'],{(3,'fixture frontier')})
        scoped=body(0,instructions,edges,{},allowed={0,1})
        self.assertEqual(scoped['boundaries'],{3});self.assertEqual(scoped['sites'],{0,1})

    def test_bottom_up_stops_at_native_domain_and_marks_cycle(self):
        def view(callees,native=False):return dict(callees=set(callees),symbol={'c_implementation':'fixture.c'} if native else {})
        views={0:view([1,4]),1:view([2]),2:view([]),4:view([9],True),9:view([])}
        self.assertEqual(dependency_order(0,views),([2,1,0],set()))
        views={0:view([1]),1:view([0])}
        order,cycles=dependency_order(0,views)
        self.assertEqual(set(order),{0,1});self.assertEqual(cycles,{0})

if __name__=='__main__':unittest.main()
