"""Abstract transfer/return contracts, using explore's instruction/edge schema.

Constructed sequences are not original execution or native differential evidence.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from flowstate import (Analyzer, State, Slot, TOP, ZERO, ONE, val, flags,
                       transfer, merge, instantiate, state_json, getreg, setreg,
                       ServiceModel, platform_profile, loader_state, interrupt_entry,
                       driver_transform, proof_obligations, report, SerialDriverServices,
                       df_census)
from explore import discover


def row(p, m, op='', size=1):
    return dict(address=p, mnemonic=m, operands=op, size=size)


def program(instructions, edges, routines=(0,)):
    return dict(instructions=instructions, edges=[dict(source=a, target=b, kind=k)
                for a, b, k in edges], routines=list(routines), unresolved=[])


def serial(analysis, entries=()):
    return Analyzer(analysis, entries, intact_stack=True, irq_mode='disabled').run()


class FlowStateTests(unittest.TestCase):
    def test_decoded_std_census_includes_all_components_and_protected_views(self):
        from flowstate import load_component
        from common import ROOT, read_json
        found = {}
        for component in ('main', 'adlib', 'tandysnd', 'pcspeaker'):
            analysis, _, _ = load_component(component)
            found[component] = [r['address'] for r in df_census(analysis)['std']]
        protected = df_census(read_json(ROOT/'metadata/protection-cfg.json'))
        self.assertEqual(found, dict(main=['1BB0'], adlib=[], tandysnd=[], pcspeaker=[]))
        self.assertEqual(protected['std'], [])
        self.assertEqual([(r['address'], r['view']) for r in protected['cld']], [('08D2', 'tf_on')])
        self.assertEqual([(r['address'], r['view']) for r in protected['strings']], [('08D3', 'tf_on')])

    def test_original_std_has_cld_before_any_string_consumer(self):
        from flowstate import load_component
        analysis, _, _ = load_component('main')
        ins = {r['address']: r for r in analysis['instructions']}
        # The entire straight-line transient window and the CALL's real child
        # prefix, rather than an inference from a later normal-return CLD.
        path = (0x1bb0, 0x1bb1, 0x1bb2, 0x1bb4, 0x1bb7, 0x1bb9,
                0x1d2e, 0x1d2f, 0x1d30, 0x1d31, 0x1d32, 0x1d33, 0x1d34)
        edges = {(e['source'], e['target']) for e in analysis['edges']}
        for source, target in zip(path, path[1:]):
            self.assertIn((source, target), edges)
        state = State(df=ZERO)
        for p in path:
            self.assertFalse(any(x in ins[p]['mnemonic'] for x in ('lods', 'stos', 'movs', 'cmps', 'scas')))
            state = transfer(ins[p], state, intact_stack=True)
        self.assertEqual(state.df, ZERO)
        self.assertEqual(ins[0x1c78]['mnemonic'], 'cld')
        self.assertEqual(ins[0x1c79]['mnemonic'], 'ret')
        self.assertIn((0x1c78, 0x1c79), edges)

    def test_explicit_original_driver_binding_preserves_both_df_values_in_both_modes(self):
        for mode in ('CONSERVATIVE', 'PROFILE'):
            for component, vector in (('adlib', 0x61), ('tandysnd', 0x61), ('pcspeaker', 0x60)):
                model = SerialDriverServices(mode, bindings={vector: component})
                for function in ((0, 1, 3) if component == 'pcspeaker' else range(6)):
                    for df in (ZERO, ONE):
                        with self.subTest(mode=mode, component=component, function=function, df=df):
                            s = State.symbolic()
                            s.df = df
                            setreg(s, 'ah', val(function))
                            ins = row(0x100, 'int', hex(vector), 2)
                            declaration = model.resolve(ins, s)
                            self.assertEqual(declaration['profile_entries'], [])
                            out = transfer(ins, s, intact_stack=True, services=model)
                            self.assertEqual((out.df, out.sp), (df, 0))
                            self.assertEqual(out.regs['ds'], s.regs['ds'])
                self.assertIsNone(model.resolve(row(0, 'int', hex(vector)), State()))
                bad = State()
                setreg(bad, 'ah', val(0xff))
                self.assertIsNone(model.resolve(row(0, 'int', hex(vector)), bad))

    def test_driver_bindings_cannot_enter_concurrent_or_alias_scopes(self):
        model = SerialDriverServices(bindings={0x61: 'adlib'})
        a = program([row(0, 'nop')], [])
        for kwargs in ({}, {'intact_stack': True}, {'irq_mode': 'disabled'}):
            with self.assertRaisesRegex(ValueError, 'serial intact-stack'):
                Analyzer(a, services=model, **kwargs)
        with self.assertRaises(ValueError):
            SerialDriverServices(bindings={0x60: 'adlib'})
        s = State()
        setreg(s, 'ah', ZERO)
        with self.assertRaisesRegex(ValueError, 'intact-stack'):
            transfer(row(0, 'int', '0x61'), s, services=model)

    def test_first_arrival_stop_is_not_an_assumed_return_or_global_invariant(self):
        a = program([row(0, 'nop'), row(1, 'std'), row(2, 'jmp', '0')],
                    [(0, 1, 'fallthrough'), (1, 2, 'fallthrough'), (2, 0, 'branch')])
        bounded = Analyzer(a, intact_stack=True, irq_mode='disabled', stop_before=(1,)).run()
        self.assertEqual(bounded.states[0, 1].df, val(('in', 'df')))
        self.assertNotIn((0, 2), bounded.states)
        self.assertFalse(bounded.exits[0])
        self.assertEqual(serial(a).states[0, 1].df, frozenset((('in', 'df'), 1)))

    def test_original_protected_fill_cld_is_restored_by_cleanup_popf(self):
        from common import ROOT, read_json
        original = read_json(ROOT/'metadata/protection-cfg.json')
        # Static summaries of two TF-on helper bodies. This does not compose
        # dynamic INT1/INT3, disk services, or an actual protection invocation.
        instructions = [r for r in original['instructions'] if r['state'] == 'tf_on'
                        and (0x8cb <= r['address'] < 0x8d7 or 0x94a <= r['address'] < 0x96f)]
        sites = {r['address'] for r in instructions}
        a = dict(instructions=instructions, routines=[0x8cb, 0x94a], unresolved=[],
                 edges=[e for e in original['edges'] if e['source'] in sites and e['target'] in sites
                        and e['state'] == e['target_state'] == 'tf_on'])
        z = serial(a)
        for df in (ZERO, ONE):
            s = State.symbolic()
            s.df = df
            filled = instantiate(z.exits[0x8cb][0x8d6].state, s)
            cleaned = instantiate(z.exits[0x94a][0x96e].state, s)
            self.assertEqual(filled.df, ZERO)
            self.assertEqual(cleaned.df, df)

    def test_original_timer_inner_popf_and_outer_iret_are_distinct(self):
        from flowstate import load_component
        original, _, _ = load_component('main')
        instructions = [r for r in original['instructions'] if 0x18a7 <= r['address'] <= 0x18b1]
        sites = {r['address'] for r in instructions}
        a = dict(instructions=instructions, routines=[0x18a7], unresolved=[],
                 edges=[e for e in original['edges'] if e['source'] in sites and e['target'] in sites])
        z = serial(a)
        s = State(df=ZERO, polluted=True)
        s.slots = {0: Slot(flags(ONE, ZERO)), 20: Slot(val(0x1234)),
                   22: Slot(val(0x1010)), 24: Slot(flags(ZERO, ONE))}
        before_iret = instantiate(z.states[0x18a7, 0x18b1], s)
        after_iret = instantiate(z.exits[0x18a7][0x18b1].state, s)
        self.assertEqual(before_iret.df, ONE)
        self.assertEqual((after_iret.df, after_iret.sp), (ZERO, 26))

    def test_original_startup_postdecode_closure_has_no_df_writer_or_service(self):
        from flowstate import load_component
        from graph import routine_views
        from common import ROOT, read_json
        original, _, _ = load_component('main')
        views = routine_views(original, read_json(ROOT/'metadata/symbols.json'), original=True)
        closure, pending = set(), [0x59bb, 0x5cc1, 0x5ac1, 0x57d1]
        while pending:
            entry = pending.pop()
            if entry in closure:
                continue
            closure.add(entry)
            pending.extend(views[entry]['callees'])
        sites = set().union(*(views[e]['sites'] for e in closure))
        for entry in closure:
            self.assertFalse(views[entry]['problems'])
        instructions = [r for r in original['instructions'] if r['address'] in sites]
        self.assertFalse([r for r in instructions if r['mnemonic'] in
                          ('std', 'cld', 'popf', 'iret', 'int', 'int3')])
        self.assertEqual({r['address'] for r in instructions
                          if any(x in r['mnemonic'] for x in ('lods', 'stos', 'movs', 'scas', 'cmps'))},
                         {0x5815, 0x5bba, 0x5be2, 0x5ce5, 0x5d6e, 0x5d7f})
        # These actual caller sets connect the neutral bodies to the normal
        # DAT reset handoffs at58E0/58F9/590F/598A. No global root input assumed.
        for entry, callers in ((0x59bb, {0x58e5}), (0x5cc1, {0x58e8}),
                               (0x5ac1, {0x58fe}), (0x57d1, {0x5927, 0x59a1})):
            self.assertEqual(views[entry]['callers'], callers)

    def test_loader_flags_are_original_code_in_both_modes(self):
        a = program([row(0, 'nop')], [])
        result = report(a, b'\x90', mode='BOTH')
        for mode in ('CONSERVATIVE', 'PROFILE'):
            root = result['modes'][mode]['root_states']['0000']
            self.assertEqual((root['DF'], root['IF']), (0, 1))
            # Entry boundary fact is distinct from an enabled-IRQ arrival.
            self.assertEqual(result['modes'][mode]['states'][
                result['modes'][mode]['instructions']['0000']['decoded_concurrent']]['DF'], 'unknown')

    def test_driver_vector_root_has_cpu_if_tf_clear_in_both_modes(self):
        a = program([row(0, 'nop')], [])
        for mode in ('CONSERVATIVE', 'PROFILE'):
            root = report(a, b'\x90', component='adlib', mode=mode)['root_states']['0000']
            self.assertEqual((root['IF'], root['TF']), (0, 0))
            self.assertEqual(root['DF'], 'unknown')

    def test_known_ah_survives_unknown_al_and_substitution(self):
        s = State()
        s = transfer(row(0, 'mov', 'ah, 0x3f'), s)
        self.assertEqual(getreg(s, 'ah'), val(0x3f))
        self.assertIsNone(getreg(s, 'al'))
        symbolic = State.symbolic()
        setreg(symbolic, 'ah', val(0x3f))
        self.assertEqual(getreg(instantiate(symbolic, s), 'ah'), val(0x3f))

    def test_profile_and_conservative_do_not_share_service_effects(self):
        s = State(df=ONE, iff=ONE)
        s.regs.update(ax=val(0x3f00), ds=val(0x1234), es=val(0x5678))
        conservative = transfer(row(0, 'int', '0x21', 2), s, services=ServiceModel())
        profile = transfer(row(0, 'int', '0x21', 2), s, services=ServiceModel('PROFILE'))
        self.assertIsNone(conservative.df)
        self.assertEqual(profile.df, ONE)  # preserve DF1, never normalize to0
        self.assertEqual(conservative.regs['ds'], val(0x1234))  # documented DOS non-result register
        self.assertIsNone(profile.regs['ax'])  # byte count/error is external input

    def test_bios_function_identity_and_outputs(self):
        model = ServiceModel('PROFILE')
        for ax, expected in ((0x1a00, '10:AX=1A00'), (0x0f00, '10:AH=000F'),
                             (0x000d, '10:AH=0000'), (0x0580, '10:AH=0005')):
            s = State(df=ZERO, iff=ONE)
            s.regs['ax'] = val(ax)
            declaration = model.resolve(row(0, 'int', '0x10', 2), s)
            self.assertEqual(declaration['function'], expected)
            self.assertEqual(declaration['profile_entries'], [expected])
        s.regs['ax'] = val(0x1a01)
        self.assertIsNone(model.resolve(row(0, 'int', '0x10', 2), s))

    def test_ega_subfunction_must_be_bl10(self):
        s = State()
        setreg(s, 'ah', val(0x12))
        self.assertIsNone(ServiceModel('PROFILE').resolve(row(0, 'int', '0x10'), s))
        setreg(s, 'bl', val(0x10))
        self.assertEqual(ServiceModel('PROFILE').resolve(row(0, 'int', '0x10'), s)['function'], '10:AH=0012')

    def test_unknown_selector_is_never_filled_from_site_inventory(self):
        for mode in ('CONSERVATIVE', 'PROFILE'):
            self.assertEqual(transfer(row(0x1413, 'int', '0x10', 2), State(),
                                     services=ServiceModel(mode)), State.havoc())

    def test_every_declared_function_transforms_in_both_modes(self):
        for mode in ('CONSERVATIVE', 'PROFILE'):
            model = ServiceModel(mode)
            for key, definition in platform_profile()['services'].items():
                with self.subTest(mode=mode, function=key):
                    s = State(df=ONE, iff=ONE)
                    s.regs = {r: val(0x1234) for r in s.regs}
                    if definition['selector']:
                        setreg(s, definition['selector'], val(definition['value']))
                    for reg, value in definition['qualifiers'].items():
                        setreg(s, reg, val(value))
                    ins = row(0, 'int', hex(definition['interrupt']), 2)
                    declaration = model.resolve(ins, s)
                    self.assertIsNotNone(declaration)
                    out = transfer(ins, s, intact_stack=True, services=model)
                    self.assertEqual(out.df, ONE if mode == 'PROFILE' else TOP)
                    for reg in definition['outputs']:
                        self.assertIsNone(getreg(out, reg))

    def test_function_results_override_preservation(self):
        s = State(df=ZERO, iff=ONE)
        s.regs.update(ax=val(0x3509), ds=val(0x1234), es=val(0x7777), bx=val(0x8888))
        out = transfer(row(0, 'int', '0x21', 2), s, services=ServiceModel('PROFILE'))
        self.assertIsNone(out.regs['es'])
        self.assertIsNone(out.regs['bx'])
        self.assertEqual(out.regs['ds'], s.regs['ds'])

    def test_absolute_disk_extra_flags_word_is_not_iret_balance(self):
        for mode in ('CONSERVATIVE', 'PROFILE'):
            s = State(df=ONE, iff=ONE)
            out = transfer(row(0, 'int', '0x25', 2), s, services=ServiceModel(mode))
            self.assertEqual(out.sp, 0xfffe)
            self.assertEqual(out.pop().value, flags(ONE, ONE))
            self.assertEqual(out.sp, 0)

    def test_irq_entry_clears_if_retains_df_and_iret_restores_frame(self):
        original = State(df=ONE, iff=ONE, tf=ONE)
        original.regs['cs'] = val(0x1010)
        irq = interrupt_entry(original, 0x100, 0x1234, val(0x2000))
        self.assertEqual((irq.df, irq.iff, irq.tf, irq.sp), (ONE, ZERO, ZERO, 0xfffa))
        self.assertEqual(irq.read_slot(0xfffe).value, flags(ONE, ONE, ONE))
        a = serial(program([row(0, 'cld'), row(1, 'iret')], [(0, 1, 'fallthrough')]))
        out = instantiate(a.exits[0][1].state, irq)
        self.assertEqual((out.df, out.iff, out.tf, out.sp), (ONE, ONE, ONE, 0))

    def test_profile_assumptions_cannot_be_overridden_per_site(self):
        with self.assertRaisesRegex(ValueError, 'metadata/platform-profile.json only'):
            report(program([row(0, 'nop')], []), b'\x90', services={0: {}}, mode='PROFILE')

    def test_service_inventory_matches_every_decoded_int_site(self):
        from flowstate import load_component
        from common import ROOT, read_json
        analysis, _, _ = load_component('main')
        raw = {r['address'] for r in analysis['instructions'] if r['mnemonic'] in ('int', 'int3')}
        declared = platform_profile()['interrupt_sites']
        self.assertEqual(raw, {int(r['address'], 16) for r in declared if r['view'] == 'raw'})
        protected = read_json(ROOT/'metadata/protection-cfg.json')['instructions']
        self.assertEqual({(r['address'], r['state']) for r in protected if r['mnemonic'] in ('int', 'int3')},
                         {(int(r['address'], 16), r['view']) for r in declared if r['view'] != 'raw'})
        for site in declared:
            self.assertTrue(site['producer'])

    def test_modes_never_disable_concurrent_irq_or_alias_obligations(self):
        a = program([row(0, 'sti'), row(1, 'nop'), row(2, 'ret')],
                    [(0, 1, 'fallthrough'), (1, 2, 'fallthrough')])
        for mode in ('CONSERVATIVE', 'PROFILE'):
            analyzer = Analyzer(a, services=ServiceModel(mode)).run()
            self.assertIsNone(analyzer.before(analyzer.states[0, 2]).df)
        self.assertTrue(all(x['profile_closes'] is False for x in proof_obligations()))

    def test_dynamic_tandy_probe_restore_uses_saved_bl_as_bios_ah(self):
        s = State()
        s.push(val(0xc001), 0)
        for ins in (row(1, 'pop', 'ax'), row(2, 'mov', 'ah, 5'), row(3, 'xchg', 'al, ah')):
            s = transfer(ins, s)
        self.assertEqual(s.regs['ax'], val(0x0105))
        self.assertIsNone(ServiceModel('PROFILE').resolve(row(0x626, 'int', '0x10'), s))

    def test_driver_original_code_transformers_preserve_inherited_flags(self):
        for component, functions in (('adlib', range(6)), ('tandysnd', range(6)), ('pcspeaker', (0, 1, 3))):
            for function in functions:
                with self.subTest(component=component, function=function):
                    s = State.symbolic()
                    s.df, s.iff = ONE, ZERO
                    out = driver_transform(component, function, s)
                    self.assertEqual((out.df, out.iff, out.sp), (ONE, ZERO, 0))
                    self.assertEqual(out.regs['ds'], s.regs['ds'])
        self.assertEqual(driver_transform('pcspeaker', 2, State()), State.havoc())

    def test_profile_cannot_bind_a_dangling_driver_vector(self):
        s = State(df=ZERO, iff=ONE)
        s.regs['ax'] = val(0x300)
        for mode in ('CONSERVATIVE', 'PROFILE'):
            self.assertEqual(transfer(row(0, 'int', '0x61'), s,
                                     services=ServiceModel(mode)), State.havoc())

    def test_termination_has_no_service_fallthrough(self):
        a = program([row(0, 'mov', 'ax, 0x4c00'), row(1, 'int', '0x21'), row(2, 'std')],
                    [(0, 1, 'fallthrough'), (1, 2, 'fallthrough')])
        for mode in ('CONSERVATIVE', 'PROFILE'):
            self.assertNotIn((0, 2), Analyzer(a, services=ServiceModel(mode), irq_mode='disabled').run().states)

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
