"""Dependency selection must retain shared tails, open domains and cycles."""
import sys
import contextlib
import io
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from graph import body,dependency_order,routine_views,tag,bottom_up,tree

class GraphTests(unittest.TestCase):
    def test_original_view_exposes_untranslated_suffix_and_follows_native_children(self):
        analysis=dict(instructions=[dict(address=p,mnemonic=m,size=n) for p,m,n in
            ((0,'nop',1),(1,'call',3),(4,'ret',1),(8,'ret',1))],
            edges=[dict(source=a,target=b,kind=k) for a,b,k in
                ((0,1,'fallthrough'),(1,8,'call'),(1,4,'fallthrough'))],
            unresolved=[],routines=[0,8])
        ledger=[dict(address=0,segment=0,kind='entry',size=None,symbol_name='Prefix',
                    verification_status='TESTED',c_implementation='fixture.c',c_code_ranges=[[0,1]]),
                dict(address=1,segment=0,kind='continuation',size=3,symbol_name='Suffix',verification_status='UNRESOLVED'),
                dict(address=8,segment=0,kind='entry',size=1,symbol_name='Child',
                    verification_status='TESTED',c_implementation='fixture.c')]
        scoped=routine_views(analysis,ledger)
        self.assertEqual(scoped[0]['sites'],{0})
        self.assertEqual(scoped[1]['sites'],{1,4})
        views=routine_views(analysis,ledger,original=True)
        self.assertEqual(views[0]['sites'],{0,1,4})
        self.assertEqual(views[1]['callees'],{8})
        self.assertEqual(dependency_order(0,views),([8,0],set()))
        self.assertIn('ASM-body',tag(0,views));self.assertNotIn('TESTED C-domain',tag(0,views))
        self.assertEqual((views[0]['existing_c_bytes'],views[0]['outside_c_bytes']),(1,4))

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
        self.assertEqual(views[1]['callees'],{8});self.assertEqual(views[4]['sites'],{4,5})
        self.assertEqual(views[0]['sites'],{0,1,4,5})
        self.assertFalse(views[0]['symbol'].get('c_implementation'))

    def test_native_tail_overlap_is_not_reported_as_new_translation_work(self):
        analysis=dict(instructions=[dict(address=0,mnemonic='jmp',size=2),
            dict(address=8,mnemonic='ret',size=1)],
            edges=[dict(source=0,target=8,kind='branch')],unresolved=[],routines=[0,8])
        ledger=[dict(address=0,segment=0,kind='entry',size=None,symbol_name='Prefix',verification_status='UNTRANSLATED'),
            dict(address=8,segment=0,kind='entry',size=1,symbol_name='NativeTail',verification_status='TESTED',c_implementation='fixture.c')]
        views=routine_views(analysis,ledger)
        self.assertEqual(views[0]['sites'],{0,8})
        self.assertEqual((views[0]['bytes'],views[0]['existing_c_bytes'],views[0]['outside_c_bytes']),(3,1,2))
        self.assertIn('1 already-C bytes/2 outside C ranges',tag(0,views))
        self.assertEqual(views[8]['outside_c_bytes'],0)

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

    def test_maintained_labels_are_query_views_without_discovery_seeds(self):
        from common import ROOT,read_json
        from explore import analyze
        analysis=analyze();seeds=list(analysis['routines']);sites=list(analysis['instructions'])
        ledger=read_json(ROOT/'metadata/symbols.json')
        for original in (False,True):
            views=routine_views(analysis,ledger,original=original)
            for address,name in ((0xFB,'EnterLoadedLevelGame'),(0x105,'GameFrameSwapAndPace')):
                self.assertEqual(views[address]['symbol']['symbol_name'],name)
                self.assertIn(address,views[address]['sites'])
        self.assertEqual(analysis['routines'],seeds)
        self.assertEqual(analysis['instructions'],sites)
        # An undecoded named location remains unknown; navigation never decodes it.
        ledger.append(dict(address=0xFFFF,segment=0,kind='label',symbol_name='Unknown'))
        self.assertNotIn(0xFFFF,routine_views(analysis,ledger,original=True))

    def test_bottom_up_keeps_real_frontier_and_device_sites(self):
        from common import ROOT,read_json
        from explore import analyze
        views=routine_views(analyze(),read_json(ROOT/'metadata/symbols.json'),original=True)
        out=io.StringIO()
        with contextlib.redirect_stdout(out):bottom_up(0x706F,views,original=True)
        self.assertIn('715B:indirect_closed_legitimate',out.getvalue())
        self.assertIn('platform/IRQ sites:',out.getvalue())

    def test_native_root_and_tree_print_service_and_external_return_sites(self):
        analysis=dict(instructions=[dict(address=0,mnemonic='out',size=1),
                                    dict(address=1,mnemonic='iret',size=1)],
                      edges=[dict(source=0,target=1,kind='fallthrough'),
                             dict(source=1,target=None,kind='external_interrupt_return')],
                      unresolved=[dict(address=1,kind='open domain')],routines=[0])
        ledger=[dict(address=0,segment=0,kind='label',size=2,symbol_name='NativeRoot',
                     verification_status='TESTED',c_implementation='fixture.c')]
        views=routine_views(analysis,ledger)
        for render in (lambda:bottom_up(0,views),lambda:tree(0,views,0)):
            out=io.StringIO()
            with contextlib.redirect_stdout(out):render()
            for site in ('0000:out','0001:external_interrupt_return','0001:open domain'):
                self.assertIn(site,out.getvalue())

if __name__=='__main__':unittest.main()
