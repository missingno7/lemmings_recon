"""Dependency selection must retain shared tails, open domains and cycles."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from graph import body,dependency_order

class GraphTests(unittest.TestCase):
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
