"""Abstract transfer/return contracts, using explore's instruction/edge schema.

Constructed sequences are not original execution or native differential evidence.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from flowstate import (Analyzer, State, Slot, TOP, ZERO, ONE, val, flags,
                       transfer, merge, instantiate, state_json)
from explore import discover


def row(p, m, op='', size=1):
    return dict(address=p, mnemonic=m, operands=op, size=size)


def program(instructions, edges, routines=(0,)):
    return dict(instructions=instructions, edges=[dict(source=a, target=b, kind=k)
                for a, b, k in edges], routines=list(routines), unresolved=[])


def serial(analysis, entries=()):
    return Analyzer(analysis, entries, intact_stack=True, irq_mode='disabled').run()


class FlowStateTests(unittest.TestCase):
    def test_cld_std_preserve_other_flag(self):
        s = State(iff=ONE)
        s = transfer(row(0, 'std'), s)
        self.assertEqual((s.df, s.iff), (ONE, ONE))
        s = transfer(row(1, 'cld'), s)
        self.assertEqual((s.df, s.iff), (ZERO, ONE))

    def test_pushf_popf_restore_actual_saved_df_if(self):
        s = State(df=ONE, iff=ZERO)
        for r in (row(0, 'pushf'), row(1, 'cld'), row(2, 'sti'), row(3, 'popf')):
            s = transfer(r, s)
        self.assertEqual((s.sp, s.df, s.iff), (0, ONE, ZERO))

    def test_popf_numeric_and_unknown_flags(self):
        s = State()
        s.push(val(0x602), 0)
        s = transfer(row(1, 'popf'), s)
        self.assertEqual((s.df, s.iff), (ONE, ONE))
        s.push(TOP, 2)
        s = transfer(row(3, 'popf'), s)
        self.assertIsNone(s.df)
        self.assertIsNone(s.iff)

    def test_word_save_identity_and_modular_sp(self):
        s = State()
        s.regs['ds'] = val(('reloc', 0x9a9))
        s = transfer(row(0x10, 'push', 'ds'), s)
        self.assertEqual(s.sp, 0xfffe)
        self.assertEqual(s.read_slot(s.sp).pushes, frozenset((0x10,)))
        s = transfer(row(0x11, 'pop', 'es'), s)
        self.assertEqual((s.sp, s.regs['es']), (0, val(('reloc', 0x9a9))))

    def test_bp_relative_stack_write_replaces_saved_word(self):
        s = State()
        s.push(val(0x1234), 0)
        s = transfer(row(1, 'mov', 'bp, sp'), s)
        s = transfer(row(2, 'mov', 'word ptr [bp], 0x4321'), s)
        s = transfer(row(3, 'pop', 'ax'), s)
        self.assertEqual(s.regs['ax'], val(0x4321))

    def test_byte_write_invalidates_overlap(self):
        s = State()
        s.push(val(0x1234), 0)
        s = transfer(row(1, 'mov', 'bp, sp'), s)
        s = transfer(row(2, 'mov', 'byte ptr [bp + 1], 0'), s)
        self.assertIsNone(s.read_slot(s.sp).value)

    def test_unproved_memory_alias_invalidates_saves(self):
        s = State()
        s.push(val(0x1234), 0)
        unknown = transfer(row(1, 'mov', 'word ptr [di], ax'), s)
        intact = transfer(row(1, 'mov', 'word ptr [di], ax'), s, intact_stack=True)
        self.assertIsNone(unknown.read_slot(0xfffe).value)
        self.assertEqual(intact.read_slot(0xfffe).value, val(0x1234))

    def test_ss_load_invalidates_old_physical_slot_and_sets_shadow(self):
        s = State()
        s.push(val(0x1234), 0)
        s.regs['ax'] = val(('reloc', 0x143e))
        s = transfer(row(1, 'mov', 'ss, ax'), s)
        self.assertEqual((s.regs['ss'], s.shadow), (val(('reloc', 0x143e)), ONE))
        self.assertIsNone(s.read_slot(s.sp).value)

    def test_relocated_immediate_segment_propagation(self):
        s = transfer(row(0, 'mov', 'dx, 0x9a9', 3), State(), relocations=(1,))
        s = transfer(row(3, 'mov', 'ds, dx'), s)
        self.assertEqual(s.regs['ds'], val(('reloc', 0x9a9)))

    def test_undeclared_int_havocs_even_df_and_ss(self):
        s = State(df=ZERO, iff=ONE)
        s.regs['ds'] = val(('reloc', 0x9a9))
        out = transfer(row(0, 'int', '0x21', 2), s)
        self.assertEqual(out, State.havoc())

    def test_declared_int_uses_real_iret_frame(self):
        s = State(df=ONE, iff=ONE)
        s.regs['cs'], s.regs['ss'] = val(('reloc', 0)), val(('reloc', 0x143e))
        s.regs['ds'] = val(('reloc', 0x9a9))
        out = transfer(row(0, 'int', '0x21', 2), s, services={0: dict(
            evidence='constructed frame contract', intact_iret_frame=True,
            preserve=['ds'], set={'ax': 7})})
        self.assertEqual((out.sp, out.df, out.iff), (0, ONE, ONE))
        self.assertEqual((out.regs['ax'], out.regs['ds']), (val(7), s.regs['ds']))
        self.assertIsNone(out.regs['es'])
        self.assertEqual(out.read_slot(0xfffa).value, val(2))

    def test_declared_int_frame_does_not_implicitly_preserve_older_saves(self):
        s = State(df=ZERO, iff=ONE)
        s.push(val(0x1234), 0)
        contract = dict(evidence='constructed service', intact_iret_frame=True,
                        return_flags={'DF': 1, 'IF': 'unknown'})
        out = transfer(row(1, 'int', '0x21', 2), s, services={1: contract})
        self.assertIsNone(out.read_slot(0xfffe).value)
        self.assertEqual(out.df, ONE)
        self.assertIsNone(out.iff)
        out = transfer(row(1, 'int', '0x21', 2), s,
                       services={1: dict(contract, preserve_caller_stack=True)})
        self.assertEqual(out.read_slot(0xfffe).value, val(0x1234))

    def test_sti_and_ss_shadow_last_one_instruction(self):
        s = transfer(row(0, 'sti'), State(iff=ZERO))
        self.assertEqual(s.shadow, ONE)
        self.assertFalse(state_json(s)['maskable_IRQ_may_land'])
        s = transfer(row(1, 'nop'), s)
        self.assertTrue(state_json(s)['maskable_IRQ_may_land'])

    def test_call_ret_read_actual_continuation_not_fallthrough(self):
        a = program([row(0, 'call', '8', 3), row(3, 'nop'), row(4, 'ret'),
                     row(8, 'std'), row(9, 'ret')],
                    [(0, 8, 'call'), (0, 3, 'fallthrough'), (3, 4, 'fallthrough'),
                     (8, 9, 'fallthrough')], (0, 8))
        result = serial(a)
        self.assertEqual(result.states[0, 3].df, ONE)
        self.assertEqual(result.states[0, 3].sp, 0)
        self.assertEqual(result.states[8, 9].sp, 0)

    def test_nonreturning_callee_has_no_assumed_call_fallthrough(self):
        a = program([row(0, 'call', '8', 3), row(3, 'std'), row(8, 'jmp', '8')],
                    [(0, 8, 'call'), (0, 3, 'fallthrough'), (8, 8, 'branch')], (0, 8))
        self.assertNotIn((0, 3), serial(a).states)

    def test_call_next_pop_delivers_real_ip(self):
        a = program([row(0, 'call', '3', 3), row(3, 'pop', 'bx'), row(4, 'ret')],
                    [(0, 3, 'call'), (0, 3, 'fallthrough'), (3, 4, 'fallthrough')], (0, 3))
        result = serial(a)
        self.assertEqual(result.states[0, 4].regs['bx'], val(3))
        self.assertEqual(result.states[0, 4].sp, 0)

    def test_constructed_ret_target_is_followed(self):
        a = program([row(0, 'push', '8'), row(1, 'ret'), row(8, 'std'), row(9, 'ret')],
                    [(0, 1, 'fallthrough'), (8, 9, 'fallthrough')])
        result = serial(a)
        self.assertEqual(result.states[0, 9].df, ONE)
        self.assertEqual(result.states[0, 8].sp, 0)

    def test_constructed_far_return_to_current_cs_is_a_transfer(self):
        a = program([row(0, 'push', 'cs'), row(1, 'push', '8'), row(2, 'retf'),
                     row(8, 'std'), row(9, 'ret')],
                    [(0, 1, 'fallthrough'), (1, 2, 'fallthrough'), (8, 9, 'fallthrough')])
        self.assertEqual(serial(a).states[0, 9].df, ONE)

    def test_unknown_caller_sp_still_pushes_a_fresh_call_return(self):
        a = program([row(0, 'int', '0x21'), row(1, 'call', '8', 3), row(4, 'ret'),
                     row(8, 'std'), row(9, 'ret')],
                    [(0, 1, 'fallthrough'), (1, 8, 'call'), (1, 4, 'fallthrough'),
                     (8, 9, 'fallthrough')], (0, 8))
        result = serial(a)
        self.assertEqual(result.states[0, 4].df, ONE)
        self.assertIsNone(result.states[0, 4].sp)

    def test_unknown_sp_call_next_does_not_invent_entry_relative_depth(self):
        a = program([row(0, 'int', '0x21'), row(1, 'call', '4', 3), row(4, 'pop', 'bx')],
                    [(0, 1, 'fallthrough'), (1, 4, 'call'), (1, 4, 'fallthrough')])
        self.assertIsNone(serial(a).states[0, 4].sp)

    def test_shared_tail_keeps_caller_save(self):
        a = program([row(0, 'push', 'ds'), row(1, 'jmp', '8'),
                     row(8, 'pop', 'es'), row(9, 'ret')],
                    [(0, 1, 'fallthrough'), (1, 8, 'branch'), (8, 9, 'fallthrough')])
        result = serial(a)
        self.assertEqual(result.states[0, 9].regs['es'], val(('in', 'ds')))

    def test_far_call_and_retf_restore_two_word_frame(self):
        a = program([row(0, 'lcall', '0, 8', 5), row(5, 'ret'), row(8, 'retf')],
                    [(0, 8, 'far_call'), (0, 5, 'fallthrough')], (0, 8))
        result = serial(a)
        self.assertEqual(result.states[0, 5].sp, 0)
        self.assertEqual(result.states[0, 5].regs['cs'], val(('in', 'cs')))

    def test_iret_restores_actual_flags_and_stack(self):
        a = program([row(0, 'cld'), row(1, 'iret')], [(0, 1, 'fallthrough')])
        result = serial(a)
        irq = State(df=ONE, iff=ZERO, polluted=True)
        irq.slots = {0: Slot(val(0x1234)), 2: Slot(val(('reloc', 0))),
                     4: Slot(flags(ONE, ONE))}
        exit_ = result.exits[0][1]
        out = instantiate(exit_.state, irq)
        self.assertEqual((out.sp, out.df, out.iff), (6, ONE, ONE))

    def test_join_does_not_choose_a_direction(self):
        a, b = State(df=ZERO), State(df=ONE)
        self.assertEqual(merge(a, b).df, frozenset((0, 1)))
        self.assertIsNone(merge(a, State()).df)

    def test_recursive_summary_reaches_finite_fixed_point(self):
        a = program([row(0, 'je', '8'), row(1, 'call', '0', 3), row(4, 'ret'),
                     row(8, 'cld'), row(9, 'ret')],
                    [(0, 8, 'branch'), (0, 1, 'fallthrough'), (1, 0, 'call'),
                     (1, 4, 'fallthrough'), (8, 9, 'fallthrough')])
        result = serial(a)
        self.assertLess(result.steps, 1000)
        # Unbounded recursion can wrap a real 16-bit stack. Widening must not
        # claim the initial return/saves survive arbitrary recursion depth.
        self.assertIn((0, 4), result.states)

    def test_irq_conservative_interference(self):
        a = program([row(0, 'sti'), row(1, 'nop'), row(2, 'nop'), row(3, 'ret')],
                    [(0, 1, 'fallthrough'), (1, 2, 'fallthrough'), (2, 3, 'fallthrough')])
        result = Analyzer(a, irq_mode='havoc').run()
        self.assertEqual(result.states[0, 2].iff, ONE)
        self.assertIsNone(result.before(result.states[0, 2]).iff)

    def test_projection_uses_dos_entry_and_actual_callee_segments(self):
        a = program([row(0, 'mov', 'dx, 0x9a9', 3), row(3, 'mov', 'ds, dx'),
                     row(4, 'call', '8', 3), row(7, 'ret'), row(8, 'ret')],
                    [(0, 3, 'fallthrough'), (3, 4, 'fallthrough'),
                     (4, 8, 'call'), (4, 7, 'fallthrough')], (0, 8))
        analyzer = Analyzer(a, relocations=(1,), irq_mode='disabled', intact_stack=True).run()
        dos = State(polluted=True)
        dos.regs.update(cs=val(('reloc', 0)), ds=val(('PSP',)), es=val(('PSP',)))
        observed, inputs = analyzer.project({0: dos})
        self.assertEqual(observed[0].regs['ds'], val(('PSP',)))
        self.assertEqual(inputs[8].regs['ds'], val(('reloc', 0x9a9)))
        self.assertEqual(inputs[8].read_slot(0).value, val(7))

    def test_reuses_discover_model_and_deterministic_results(self):
        a = discover(bytes.fromhex('fce80100c3fdc3'),
                     {'entries': [{'offset': 0}], 'code_limit': 7, 'regions': []},
                     {'accepted': []})
        one, two = serial(a), serial(a)
        self.assertEqual(one.states[0, 4].df, ONE)
        encoded = lambda r: json.dumps({str(k): state_json(v) for k, v in sorted(r.states.items())}, sort_keys=True)
        self.assertEqual(encoded(one), encoded(two))


if __name__ == '__main__':
    unittest.main()
