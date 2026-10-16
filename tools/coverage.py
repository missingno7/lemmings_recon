"""Reproducible, separate byte/translation/execution accounting."""
import argparse
from common import ROOT,BUILD,read_json,write_json,sha
from explore import analyze
from unpack import unpack,ASSET,relocated

def contract_verification():
    """Only a fresh complete contract report can support aggregate coverage."""
    verified=read_json(BUILD/'verification.json')
    if (verified.get('verification_scope')!='contracts' or
            not verified.get('bounded_unpacker_checks') or
            not verified.get('bounded_extractor_checks')):
        raise ValueError('Full contract checks required for coverage; run tools/verify.py --contracts')
    for path,digest in verified['verification_inputs'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale contract verification for '+path+'; run tools/verify.py --contracts')
    return verified

def translated_code_bytes(symbols,instructions,image_size):
    """Union complete decoded instructions across explicit, possibly shared tails.

    A ledger entry's size may describe only its physical entry prefix. Its C
    domain can include a noncontiguous shared tail before or after that prefix.
    The decoded image, rather than entry+size, owns those instruction bounds.
    """
    bounds=[(row['address'],row['address']+row['size']) for row in instructions]
    starts={start for start,_ in bounds}
    ends={end for _,end in bounds}
    decoded={p for row in instructions
             for p in range(row['address'],row['address']+row['size'])}
    covered=set()
    for symbol in symbols:
        if not symbol.get('c_implementation'):continue
        name=symbol['symbol_name']
        ranges=symbol.get('c_code_ranges')
        if ranges is None:
            size=symbol.get('size')
            if not isinstance(size,int) or size<=0:
                raise ValueError('Missing translated extent for '+name)
            ranges=[(symbol['address'],symbol['address']+size)]
        for start,end in ranges:
            if not 0<=start<end<=image_size:
                raise ValueError('Translated range outside image for '+name)
            if start not in starts or end not in ends:
                raise ValueError('Partial instruction in translated range for '+name)
            span=set(range(start,end))
            if span-decoded:
                raise ValueError('Unresolved/non-instruction translated bytes for '+name)
            complete={p for a,b in bounds if start<=a<b<=end for p in range(a,b)}
            if span-complete:
                raise ValueError('Partial instruction in translated range for '+name)
            covered.update(span)
    return covered

def report():
    verified=contract_verification()
    analysis=analyze()
    m=dict(analysis['metrics'])
    image,oracle=unpack(ASSET.read_bytes())
    built=(BUILD/'asm/program.bin').read_bytes()
    if built!=image or verified['canonical_sha256']!=sha(image):
        raise ValueError('Run tools/verify.py --contracts before reporting coverage')
    for field in ('reconstructed_asm_bytes','byte_exact_asm_bytes'):
        m[field]=verified[field]
    symbols=read_json(ROOT/'metadata/symbols.json')
    translated=[s for s in symbols if s.get('c_implementation')]
    m['translated_c_routines']=len(translated)
    code_bytes=translated_code_bytes(symbols,analysis['instructions'],len(image))
    m['translated_c_code_bytes']=len(code_bytes)
    d=read_json(BUILD/'differential.json')
    paths={'checksum.c':'c/checksum.c','checksum.h':'c/checksum.h',
           'lemmings_sym.h':'c/lemmings_sym.h','regs.h':'c/regs.h','symbols.json':'metadata/symbols.json',
           'checksum.py':'tests/checksum.py','difftest.py':'tools/difftest.py','cbuild.py':'tools/cbuild.py'}
    for name,path in paths.items():
        if d['input_hashes'][name]!=sha((ROOT/path).read_bytes()):
            raise ValueError('Stale differential report for '+path+'; run tools/difftest.py --all')
    if d['oracle']['relocated_image_sha256']!=sha(relocated(image,oracle['relocations'],int(d['oracle']['load_segment'],16))):
        raise ValueError('Differential oracle identity changed')
    executed={int(x,16) for r in d['routines'] for x in r['executed_instruction_addresses']}
    dat=read_json(BUILD/'dat-differential.json')
    for path,digest in dat['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT differential report for '+path+'; run tools/difftest.py --all')
    if dat['image_sha256']!=sha(image):raise ValueError('DAT differential oracle changed')
    executed.update(dat['executed_instruction_addresses'])
    io=read_json(BUILD/'dat-io-differential.json')
    for path,digest in io['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT read differential report for '+path+'; run tools/difftest.py --all')
    if io['image_sha256']!=sha(image):raise ValueError('DAT read differential oracle changed')
    executed.update(io['executed_instruction_addresses'])
    section=read_json(BUILD/'dat-section-differential.json')
    for path,digest in section['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT section differential report for '+path+'; run tools/difftest.py --all')
    if section['image_sha256']!=sha(image):raise ValueError('DAT section differential oracle changed')
    executed.update(section['executed_instruction_addresses'])
    cache=read_json(BUILD/'dat-cache-differential.json')
    allocation=read_json(BUILD/'cache-allocation-differential.json')
    video=read_json(BUILD/'video-restore-differential.json')
    display_status=read_json(BUILD/'display-status-differential.json')
    display_start=read_json(BUILD/'display-start-differential.json')
    display_setup=read_json(BUILD/'display-setup-differential.json')
    text_glyph=read_json(BUILD/'text-glyph-differential.json')
    text_stream=read_json(BUILD/'text-stream-differential.json')
    display_pages=read_json(BUILD/'display-pages-differential.json')
    background=read_json(BUILD/'background-drawing-differential.json')
    palette_channels=read_json(BUILD/'palette-channels-differential.json')
    palette_rows=read_json(BUILD/'palette-rows-differential.json')
    palette_ports=read_json(BUILD/'palette-ports-differential.json')
    palette_row_select=read_json(BUILD/'palette-row-select-differential.json')
    palette_transition=read_json(BUILD/'palette-transition-differential.json')
    retry_input=read_json(BUILD/'retry-input-differential.json')
    if retry_input.get('access_guard_exit')!=86 or not retry_input.get('null_bus_deadline_verified'):
        raise ValueError('Retry input guard probes must complete before C coverage')
    for extra in (display_status,display_start,display_setup,text_glyph,text_stream,display_pages,background,palette_channels,palette_rows,palette_ports,palette_row_select,palette_transition,retry_input):
        for path,digest in extra['input_hashes'].items():
            if sha((ROOT/path).read_bytes())!=digest:
                raise ValueError('Stale display differential report for '+path)
        if extra['image_sha256']!=sha(image):raise ValueError('Display differential oracle changed')
        executed.update(extra['executed_instruction_addresses'])
    vectors=read_json(BUILD/'vector-restore-differential.json')
    timer=read_json(BUILD/'timer-restore-differential.json')
    cleanup=read_json(BUILD/'fatal-cleanup-differential.json')
    file_error=read_json(BUILD/'file-error-differential.json')
    for path,digest in file_error['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale file error differential report for '+path)
    if file_error['image_sha256']!=sha(image):
        raise ValueError('File error differential oracle changed')
    executed.update(file_error['executed_instruction_addresses'])
    for path,digest in cleanup['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale fatal cleanup differential report for '+path)
    if cleanup['image_sha256']!=sha(image):
        raise ValueError('Fatal cleanup differential oracle changed')
    executed.update(cleanup['executed_instruction_addresses'])
    for path,digest in timer['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale timer restoration differential report for '+path)
    if timer['image_sha256']!=sha(image):
        raise ValueError('Timer restoration differential oracle changed')
    executed.update(timer['executed_instruction_addresses'])
    for path,digest in vectors['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale vector restoration differential report for '+path)
    if vectors['image_sha256']!=sha(image):
        raise ValueError('Vector restoration differential oracle changed')
    executed.update(vectors['executed_instruction_addresses'])
    for path,digest in video['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale video restoration differential report for '+path)
    if video['image_sha256']!=sha(image):
        raise ValueError('Video restoration differential oracle changed')
    executed.update(video['executed_instruction_addresses'])
    for path,digest in allocation['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale cache allocation differential report for '+path)
    if allocation['image_sha256']!=sha(image):
        raise ValueError('Cache allocation differential oracle changed')
    executed.update(allocation['executed_instruction_addresses'])
    for path,digest in cache['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT cache differential report for '+path+'; run tools/difftest.py --all')
    if cache['image_sha256']!=sha(image):raise ValueError('DAT cache differential oracle changed')
    executed.update(cache['executed_instruction_addresses'])
    files=read_json(BUILD/'dat-files-differential.json')
    for path,digest in files['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT file differential report for '+path+'; run tools/difftest.py --all')
    if files['image_sha256']!=sha(image):raise ValueError('DAT file differential oracle changed')
    executed.update(files['executed_instruction_addresses'])
    resource=read_json(BUILD/'dat-load-differential.json')
    for path,digest in resource['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale DAT resource differential report for '+path+'; run tools/difftest.py --all')
    if resource['image_sha256']!=sha(image):raise ValueError('DAT resource differential oracle changed')
    executed.update(resource['executed_instruction_addresses'])
    raw=read_json(BUILD/'resource-raw-differential.json')
    raw_full=read_json(BUILD/'resource-raw-full-differential.json')
    for path,digest in raw_full['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale raw full differential report for '+path)
    if raw_full['image_sha256']!=sha(image):
        raise ValueError('Raw full differential oracle changed')
    executed.update(raw_full['executed_instruction_addresses'])
    for path,digest in raw['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale raw resource differential report for '+path+'; run tools/difftest.py --all')
    if raw['image_sha256']!=sha(image):raise ValueError('Raw resource differential oracle changed')
    executed.update(raw['executed_instruction_addresses'])
    rle=read_json(BUILD/'resource-rle-differential.json')
    for path,digest in rle['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale resource RLE differential report for '+path+'; run tools/difftest.py --all')
    if rle['image_sha256']!=sha(image):raise ValueError('Resource RLE differential oracle changed')
    executed.update(rle['executed_instruction_addresses'])
    blit=read_json(BUILD/'special-blit-differential.json')
    for path,digest in blit['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale special VGA blit differential report for '+path+'; run tools/difftest.py --all')
    if blit['image_sha256']!=sha(image):raise ValueError('Special VGA blit differential oracle changed')
    executed.update(blit['executed_instruction_addresses'])
    setup=read_json(BUILD/'special-setup-differential.json')
    for path,digest in setup['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale special graphics setup differential report for '+path+'; run tools/difftest.py --all')
    if setup['image_sha256']!=sha(image):raise ValueError('Special graphics setup differential oracle changed')
    executed.update(setup['executed_instruction_addresses'])
    decimal=read_json(BUILD/'decimal-digits-c-differential.json')
    status_icons=read_json(BUILD/'status-icons-differential.json')
    sprite_bank=read_json(BUILD/'sprite-bank-differential.json')
    entity_drawing=read_json(BUILD/'entity-drawing-differential.json')
    entity_sprite_dispatch=read_json(BUILD/'entity-sprite-dispatch-differential.json')
    entity_sprite_planes=read_json(BUILD/'entity-sprite-planes-differential.json')
    entity_sprite_wide=read_json(BUILD/'entity-sprite-wide-differential.json')
    entity_sprite_aligned=read_json(BUILD/'entity-sprite-aligned-differential.json')
    entity_sprite_shifted=read_json(BUILD/'entity-sprite-shifted-differential.json')
    entity_points=read_json(BUILD/'entity-points-differential.json')
    entity_strip=read_json(BUILD/'entity-strip-differential.json')
    entity_minimap=read_json(BUILD/'entity-minimap-differential.json')
    view_visibility=read_json(BUILD/'view-visibility-differential.json')
    entity_dirty=read_json(BUILD/'entity-dirty-differential.json')
    status_copy=read_json(BUILD/'status-copy-differential.json')
    status_initialize=read_json(BUILD/'status-initialize-differential.json')
    object_drawing_tick=read_json(BUILD/'object-drawing-tick-differential.json')
    object_animation=read_json(BUILD/'object-animation-differential.json')
    status_display=read_json(BUILD/'status-display-differential.json')
    status_display_full=read_json(BUILD/'status-display-full-differential.json')
    status_text=read_json(BUILD/'status-text-differential.json')
    status_count=read_json(BUILD/'status-count-differential.json')
    status_glyph=read_json(BUILD/'status-glyph-differential.json')
    minimap_viewport=read_json(BUILD/'minimap-viewport-differential.json')
    minimap_status=read_json(BUILD/'minimap-status-differential.json')
    decimal_field=read_json(BUILD/'decimal-field-differential.json')
    entity_select=read_json(BUILD/'entity-select-differential.json')
    entity_select_actions=read_json(BUILD/'entity-select-actions-differential.json')
    selection=read_json(BUILD/'resource-select-differential.json')
    selection_full=read_json(BUILD/'resource-select-full-differential.json')
    objects=read_json(BUILD/'object-graphics-differential.json')
    coordinates=read_json(BUILD/'object-coordinates-differential.json')
    cells=read_json(BUILD/'object-cells-differential.json')
    steel=read_json(BUILD/'steel-cells-differential.json')
    state=read_json(BUILD/'object-state-differential.json')
    cells_bus=read_json(BUILD/'object-cells-bus-differential.json')
    steel_bus=read_json(BUILD/'steel-cells-bus-differential.json')
    coordinates_bus=read_json(BUILD/'object-coordinates-bus-differential.json')
    state_bus=read_json(BUILD/'object-state-bus-differential.json')
    finish=read_json(BUILD/'level-finish-differential.json')
    initialization=read_json(BUILD/'level-initialize-differential.json')
    clear=read_json(BUILD/'vga-clear-differential.json')
    layout=read_json(BUILD/'drawing-layout-differential.json')
    drawing=read_json(BUILD/'level-drawing-differential.json')
    header=read_json(BUILD/'level-header-differential.json')
    sample=read_json(BUILD/'minimap-sample-differential.json')
    mmrow=read_json(BUILD/'minimap-row-differential.json')
    mmcolumn=read_json(BUILD/'minimap-column-differential.json')
    clip=read_json(BUILD/'drawing-clip-differential.json')
    dirty=read_json(BUILD/'drawing-dirty-differential.json')
    inputs=read_json(BUILD/'drawing-inputs-differential.json')
    dispatch=read_json(BUILD/'drawing-dispatch-differential.json')
    source=read_json(BUILD/'drawing-source-differential.json')
    plan=read_json(BUILD/'drawing-plan-differential.json')
    opaque=read_json(BUILD/'aligned-opaque-differential.json')
    render=read_json(BUILD/'drawing-render-differential.json')
    masked=read_json(BUILD/'aligned-masked-differential.json')
    masked_render=read_json(BUILD/'drawing-masked-render-differential.json')
    protected=read_json(BUILD/'aligned-protected-differential.json')
    effects=read_json(BUILD/'aligned-mask-effects-differential.json')
    readmask=read_json(BUILD/'aligned-read-mask-differential.json')
    aligned_render=read_json(BUILD/'drawing-aligned-render-differential.json')
    shifted_effects=read_json(BUILD/'shifted-mask-effects-differential.json')
    shifted_render=read_json(BUILD/'drawing-shifted-render-differential.json')
    shifted_opaque=read_json(BUILD/'shifted-opaque-differential.json')
    shifted_masked=read_json(BUILD/'shifted-masked-differential.json')
    shifted_protected=read_json(BUILD/'shifted-protected-differential.json')
    shifted_readmask=read_json(BUILD/'shifted-read-mask-differential.json')
    bitmap=read_json(BUILD/'drawing-bitmap-differential.json')
    terrain_inputs=read_json(BUILD/'terrain-inputs-differential.json')
    terrain=read_json(BUILD/'terrain-drawing-differential.json')
    commands=read_json(BUILD/'terrain-commands-differential.json')
    streams=read_json(BUILD/'terrain-stream-differential.json')
    object_draw=read_json(BUILD/'object-drawing-differential.json')
    redraw=read_json(BUILD/'level-redraw-differential.json')
    entity_pattern=read_json(BUILD/'entity-pattern-differential.json')
    entity_pixel=read_json(BUILD/'entity-pixel-differential.json')
    entity_pixel_bus=read_json(BUILD/'entity-pixel-bus-differential.json')
    entity_vga=read_json(BUILD/'entity-vga-differential.json')
    entity_stroke=read_json(BUILD/'entity-stroke-differential.json')
    mask_generators=read_json(BUILD/'mask-generators-differential.json')
    generated_graphics=read_json(BUILD/'generated-graphics-differential.json')
    entity_mask=read_json(BUILD/'entity-mask-differential.json')
    entity_mask_rows=read_json(BUILD/'entity-mask-rows-differential.json')
    coordinate_pixel=read_json(BUILD/'coordinate-pixel-differential.json')
    entity_countdown=read_json(BUILD/'entity-countdown-differential.json')
    entity_interactions=read_json(BUILD/'entity-interactions-differential.json')
    entity_finish=read_json(BUILD/'entity-finish-differential.json')
    entity_zero_state=read_json(BUILD/'entity-zero-state-differential.json')
    entity_state4=read_json(BUILD/'entity-state4-differential.json')
    entity_cadence=read_json(BUILD/'entity-cadence-differential.json')
    entity_state8=read_json(BUILD/'entity-state8-differential.json')
    entity_state2=read_json(BUILD/'entity-state2-differential.json')
    entity_state10=read_json(BUILD/'entity-state10-differential.json')
    entity_state20=read_json(BUILD/'entity-state20-differential.json')
    entity_state40=read_json(BUILD/'entity-state40-differential.json')
    entity_state80=read_json(BUILD/'entity-state80-differential.json')
    entity_state100=read_json(BUILD/'entity-state100-differential.json')
    entity_state200=read_json(BUILD/'entity-state200-differential.json')
    entity_state400=read_json(BUILD/'entity-state400-differential.json')
    entity_late_states=read_json(BUILD/'entity-late-states-differential.json')
    entity_state800=read_json(BUILD/'entity-state800-differential.json')
    entity_update=read_json(BUILD/'entity-update-differential.json')
    entity_create=read_json(BUILD/'entity-create-differential.json')
    entity_action_sound=read_json(BUILD/'entity-action-sound-differential.json')
    entity_actions_basic=read_json(BUILD/'entity-actions-basic-differential.json')
    entity_actions_advanced=read_json(BUILD/'entity-actions-advanced-differential.json')
    entity_action_map=read_json(BUILD/'entity-action-map-differential.json')
    entity_action_dispatch=read_json(BUILD/'entity-action-dispatch-differential.json')
    entity_batch=read_json(BUILD/'entity-batch-differential.json')
    entity_pattern_bus=read_json(BUILD/'entity-pattern-bus-differential.json')
    for label,extra in (('sprite bank producer',sprite_bank),('entity drawing loop',entity_drawing),('entity sprite dispatch',entity_sprite_dispatch),('multiplane entity sprites',entity_sprite_planes),('wide entity sprite',entity_sprite_wide),('aligned entity sprite',entity_sprite_aligned),('shifted entity sprites',entity_sprite_shifted),('entity points',entity_points),('entity strip',entity_strip),('entity minimap',entity_minimap),('view visibility',view_visibility),('entity dirty',entity_dirty),('status copy',status_copy),('status initialize',status_initialize),('object drawing tick',object_drawing_tick),('object animation',object_animation),('status display',status_display),('status display full',status_display_full),('status text',status_text),('status count',status_count),('status glyph',status_glyph),
                        ('status icons',status_icons),('minimap viewport',minimap_viewport),
                        ('minimap status prefix',minimap_status),('decimal digits',decimal),('decimal fields',decimal_field),
                        ('entity selection',entity_select),('entity selection/action handoff',entity_select_actions),
                        ('resource selection',selection),
                        ('object graphics',objects),('object coordinates',coordinates),
                        ('object cells',cells),('steel cells',steel),('object state',state),
                        ('object cells bus',cells_bus),('steel cells bus',steel_bus),
                        ('object coordinates bus',coordinates_bus),('object state bus',state_bus),
                        ('level finish',finish),
                        ('level initialization',initialization),
                        ('VGA clear',clear),('drawing layout',layout),('level drawing',drawing),
                        ('level header',header),
                        ('minimap sample',sample),('minimap row',mmrow),('minimap column',mmcolumn),
                        ('drawing clip',clip),('drawing dirty',dirty),('drawing inputs',inputs),
                        ('drawing dispatch',dispatch),('drawing source',source),('drawing plan',plan),
                        ('aligned opaque',opaque),('connected opaque draw',render),
                        ('aligned masked',masked),('connected masked draw',masked_render),
                        ('aligned protected',protected),('aligned mask effects',effects),
                        ('aligned read mask',readmask),('connected aligned draw',aligned_render),
                        ('shifted mask effects',shifted_effects),('connected shifted draw',shifted_render),
                        ('shifted opaque',shifted_opaque),('shifted masked',shifted_masked),
                        ('shifted protected',shifted_protected),('shifted read mask',shifted_readmask),
                        ('actual bitmap entry',bitmap),('terrain inputs',terrain_inputs),
                        ('connected terrain drawing',terrain),
                        ('terrain command readers',commands),('terrain streams',streams),
                        ('object drawing',object_draw),('level redraw',redraw),
                        ('entity interaction pattern',entity_pattern),
                        ('entity pixel sample',entity_pixel),
                        ('entity pixel sample bus',entity_pixel_bus),
                        ('entity VGA helpers',entity_vga),
                        ('entity stroke',entity_stroke),
                        ('mask generators',mask_generators),
                        ('generated graphics',generated_graphics),
                        ('clipped entity mask',entity_mask),
                        ('entity mask rows',entity_mask_rows),
                        ('coordinate pixel',coordinate_pixel),
                        ('entity countdown',entity_countdown),
                        ('entity interactions',entity_interactions),
                        ('entity finish tails',entity_finish),
                        ('entity zero state',entity_zero_state),
                        ('entity state0004',entity_state4),
                        ('entity cadence states',entity_cadence),
                        ('entity state0008',entity_state8),
                        ('entity state0002',entity_state2),
                        ('entity state0010',entity_state10),
                        ('entity state0020',entity_state20),
                        ('entity state0040',entity_state40),
                        ('entity state0080',entity_state80),
                        ('entity state0100',entity_state100),
                        ('entity state0200',entity_state200),
                        ('entity state0400',entity_state400),
                        ('entity late states',entity_late_states),
                        ('entity state0800',entity_state800),
                        ('entity record update',entity_update),
                        ('entity record creation',entity_create),
                        ('entity action feedback',entity_action_sound),
                        ('entity basic actions',entity_actions_basic),
                        ('entity advanced actions',entity_actions_advanced),
                        ('entity interaction-map action',entity_action_map),
                        ('entity action dispatch prefix',entity_action_dispatch),
                        ('entity creation/update prefix',entity_batch),
                        ('entity pattern bus',entity_pattern_bus)):
        for path,digest in extra['input_hashes'].items():
            if sha((ROOT/path).read_bytes())!=digest:
                raise ValueError('Stale '+label+' differential report for '+path+'; run tools/difftest.py --all')
        if extra['image_sha256']!=sha(image):raise ValueError(label+' differential oracle changed')
    executed.update(decimal['instruction_sites'])
    executed.update(entity_pattern['executed_instruction_addresses'])
    executed.update(entity_pixel['executed_instruction_addresses'])
    executed.update(entity_pixel_bus['executed_instruction_addresses'])
    executed.update(entity_vga['executed_instruction_addresses'])
    executed.update(entity_stroke['executed_instruction_addresses'])
    executed.update(mask_generators['executed_instruction_addresses'])
    executed.update(generated_graphics['executed_instruction_addresses'])
    executed.update(entity_mask['executed_instruction_addresses'])
    executed.update(entity_mask_rows['executed_instruction_addresses'])
    executed.update(coordinate_pixel['executed_instruction_addresses'])
    executed.update(entity_countdown['executed_instruction_addresses'])
    executed.update(entity_interactions['executed_instruction_addresses'])
    executed.update(entity_finish['executed_instruction_addresses'])
    executed.update(entity_zero_state['executed_instruction_addresses'])
    executed.update(entity_state4['executed_instruction_addresses'])
    executed.update(entity_cadence['executed_instruction_addresses'])
    for extra in (entity_state8,entity_state2,entity_state10,entity_state20,entity_state40,entity_state80,entity_state100,entity_state200,entity_state400,entity_late_states,entity_state800,entity_update,entity_create,entity_action_sound,entity_actions_basic,entity_actions_advanced,entity_action_map,entity_action_dispatch,entity_batch,entity_pattern_bus):
        executed.update(extra['executed_instruction_addresses'])
    executed.update(status_icons['executed_instruction_addresses'])
    executed.update(status_count['executed_instruction_addresses'])
    executed.update(status_text['executed_instruction_addresses'])
    executed.update(sprite_bank['executed_instruction_addresses'])
    executed.update(entity_drawing['executed_instruction_addresses'])
    executed.update(entity_sprite_dispatch['executed_instruction_addresses'])
    executed.update(entity_sprite_planes['executed_instruction_addresses'])
    executed.update(entity_sprite_wide['executed_instruction_addresses'])
    executed.update(entity_sprite_aligned['executed_instruction_addresses'])
    executed.update(entity_sprite_shifted['executed_instruction_addresses'])
    executed.update(entity_points['executed_instruction_addresses'])
    executed.update(entity_strip['executed_instruction_addresses'])
    executed.update(entity_minimap['executed_instruction_addresses'])
    executed.update(view_visibility['executed_instruction_addresses'])
    executed.update(entity_dirty['executed_instruction_addresses'])
    executed.update(status_copy['executed_instruction_addresses'])
    executed.update(status_initialize['executed_instruction_addresses'])
    executed.update(object_drawing_tick['executed_instruction_addresses'])
    executed.update(object_animation['executed_instruction_addresses'])
    executed.update(status_display['executed_instruction_addresses'])
    executed.update(status_display_full['executed_instruction_addresses'])
    executed.update(status_glyph['executed_instruction_addresses'])
    executed.update(minimap_viewport['executed_instruction_addresses'])
    executed.update(minimap_status['executed_instruction_addresses'])
    executed.update(decimal_field['executed_instruction_addresses'])
    executed.update(entity_select['executed_instruction_addresses'])
    executed.update(entity_select_actions['executed_instruction_addresses'])
    executed.update(selection['executed_instruction_addresses'])
    for path,digest in selection_full['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale full resource selector differential report for '+path)
    if selection_full['image_sha256']!=sha(image):raise ValueError('Full resource selector oracle changed')
    executed.update(selection_full['executed_instruction_addresses'])
    executed.update(objects['instruction_sites'])
    executed.update(coordinates['instruction_sites'])
    executed.update(cells['instruction_sites'])
    executed.update(steel['instruction_sites'])
    executed.update(state['executed_instruction_addresses'])
    for extra in (cells_bus,steel_bus,coordinates_bus,state_bus,finish,initialization):
        executed.update(extra['executed_instruction_addresses'])
    for extra in (clear,layout,drawing,header,sample,mmrow,mmcolumn):executed.update(extra['executed_instruction_addresses'])
    executed.update(clip['executed_instruction_addresses'])
    executed.update(dirty['instruction_sites'])
    executed.update(inputs['executed_instruction_addresses'])
    for extra in (dispatch,source,plan,opaque,render,masked,masked_render,protected,effects,readmask,aligned_render,shifted_effects,shifted_render,shifted_opaque,shifted_masked,shifted_protected,shifted_readmask,bitmap):executed.update(extra['executed_instruction_addresses'])
    for extra in (terrain_inputs,terrain,commands,streams,object_draw,redraw):executed.update(extra['executed_instruction_addresses'])
    reports=(d,dat,io,section,cache,files,resource,raw,rle,blit,setup,decimal,selection,objects,coordinates,cells,steel,state,clear,layout,drawing,sample,mmrow,mmcolumn,clip,dirty,inputs,dispatch,source,plan,opaque,render,masked,masked_render,protected,effects,readmask,aligned_render,shifted_effects,shifted_render,shifted_opaque,shifted_masked,shifted_protected,shifted_readmask,bitmap)
    reports+=sprite_bank,entity_drawing,entity_sprite_dispatch,entity_sprite_planes,entity_sprite_wide,entity_sprite_aligned,entity_sprite_shifted,entity_points,entity_strip,entity_minimap,view_visibility,entity_dirty,status_copy,status_initialize,object_drawing_tick,object_animation,status_display,status_display_full,status_text,status_count,status_glyph,status_icons,minimap_viewport,minimap_status
    reports+=decimal_field,entity_select,entity_select_actions
    reports+=terrain_inputs,terrain,commands,streams,object_draw,redraw
    reports+=(header,allocation,video,vectors,timer,cleanup,file_error,raw_full,selection_full)
    reports+=(display_status,display_start,display_setup,text_glyph,text_stream,display_pages,background,palette_channels,palette_rows,palette_ports,palette_row_select,palette_transition,retry_input)
    reports+=(cells_bus,steel_bus,coordinates_bus,state_bus,finish,initialization)
    reports+=(entity_pattern,entity_pixel,entity_pixel_bus,entity_vga,entity_stroke,mask_generators,generated_graphics,entity_mask,entity_mask_rows,coordinate_pixel,entity_countdown)
    reports+=(entity_interactions,entity_finish,entity_zero_state,entity_state4,entity_cadence,entity_state8,entity_state2,entity_state10,entity_state20,entity_state40,entity_state80,entity_state100,entity_state200,entity_state400,entity_late_states,entity_state800,entity_update,entity_create,entity_action_sound,entity_actions_basic,entity_actions_advanced,entity_action_map,entity_action_dispatch,entity_batch,entity_pattern_bus)
    m['differential_cases']=sum(r['case_count'] for r in reports)
    m['mutations_detected']=sum(r['mutation_count'] for r in reports)
    decoded_sites={instruction['address'] for instruction in analysis['instructions']}
    if executed-decoded_sites:
        raise ValueError('C differential report includes undecoded instruction sites: '+
                         ','.join(f'{p:04X}' for p in sorted(executed-decoded_sites)))
    m['original_instructions_executed']=len(executed)
    m['unresolved_main_code_candidate_bytes']=sum(r['end']-r['start'] for r in analysis['regions'] if r['classification']=='unresolved' and r['start']<0x9a90)
    m['unresolved_main_code_candidate_runs']=sum(r['classification']=='unresolved' and r['start']<0x9a90 for r in analysis['regions'])
    m['unresolved_image_bytes']=len(image)-m['classified_bytes']
    m['unresolved_direct_targets']=sum(e['target'] is not None and not e.get('resolved',False) for e in analysis['edges'])
    m['unresolved_indirect_transfers']=sum(r['kind']=='indirect_or_far_transfer' for r in analysis['unresolved'])
    m['runtime_control_frontiers']=sum(r['kind'].startswith('runtime_modified') for r in analysis['unresolved'])
    m['sound']=verified['sound']
    pc=read_json(BUILD/'pcspeaker-differential.json')
    for path,digest in pc['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale PC-speaker differential report for '+path+'; run tools/difftest.py --all')
    if pc['image_sha256']!=m['sound']['pcspeaker']['image_sha256']:
        raise ValueError('PC-speaker differential oracle changed')
    m['sound']['pcspeaker']['differential_c_instructions']=len(pc['executed_instruction_addresses'])
    controls=read_json(BUILD/'sound-latches-differential.json')
    for path,digest in controls['input_hashes'].items():
        if sha((ROOT/path).read_bytes())!=digest:
            raise ValueError('Stale sound control differential report for '+path)
    if (set(controls['components'])!={'adlib','tandysnd'} or
            controls['translated_code_bytes']!=sum(
                s['translated_code_bytes'] for s in controls['components'].values())):
        raise ValueError('Sound control component coverage is incomplete')
    for name,component in controls['components'].items():
        if component['image_sha256']!=m['sound'][name]['image_sha256']:
            raise ValueError('Sound control oracle changed: '+name)
        if component['translated_code_bytes']!=m['sound'][name]['c_bytes']:
            raise ValueError('Sound control C byte scope changed: '+name)
        m['sound'][name]['differential_c_instructions']=len(component['executed_instruction_addresses'])
    m['all_images_translated_c_routines']=m['translated_c_routines']+sum(s['c_routines'] for s in m['sound'].values())
    m['all_images_translated_c_bytes']=m['translated_c_code_bytes']+pc['translated_code_bytes']+controls['translated_code_bytes']
    m['all_images_differential_cases']=m['differential_cases']+pc['case_count']+controls['case_count']
    m['all_images_mutations_detected']=m['mutations_detected']+pc['mutation_count']+controls['mutation_count']
    c_executed=len(executed)+len(pc['executed_instruction_addresses'])+sum(
        len(s['executed_instruction_addresses']) for s in controls['components'].values())
    m['all_images_original_c_instructions_executed']=c_executed
    m['protection']=verified['protection']
    m['indirect']=verified['indirect']
    m['interrupts']=verified['interrupts']
    m['dat_io']=verified['dat_io']
    m['decimal_digits_contracts']=verified['decimal_digits_contracts']
    m['cache_allocation_contracts']=verified['cache_allocation_contracts']
    m['video_restore_contracts']=verified['video_restore_contracts']
    m['vector_restore_contracts']=verified['vector_restore_contracts']
    m['timer_restore_contracts']=verified['timer_restore_contracts']
    m['fatal_cleanup_contracts']=verified['fatal_cleanup_contracts']
    m['file_error_contracts']=verified['file_error_contracts']
    m['resource_raw_full_contracts']=verified['resource_raw_full_contracts']
    state_insns=m['protection']['stream_metrics']['instructions']+m['protection']['int1_instruction_count']
    m['state_specific_decoded_instructions']=state_insns
    combined_bytes=m['byte_exact_asm_bytes']+sum(s['byte_exact_asm_bytes'] for s in m['sound'].values())
    combined_insns=m['instructions']+state_insns+sum(s['instructions'] for s in m['sound'].values())
    m['all_images_byte_exact_asm_bytes']=combined_bytes
    m['all_images_decoded_instructions']=combined_insns
    write_json(BUILD/'coverage.json',m)
    text=f'''# Reconstruction completeness

Main-image identity is established. Full static, C and native completion are not.
Regenerate this report with tools/verify.py --contracts, tools/difftest.py --all, then tools/coverage.py
--write-doc. No dynamic gameplay coverage is used.

| Metric | Value |
|---|---:|
| Canonical image bytes | {m['image_bytes']:,} |
| Classified image bytes | {m['classified_bytes']:,} |
| Decoded instruction bytes | {m['decoded_instruction_bytes']:,} |
| Reconstructed ASM bytes | {m['reconstructed_asm_bytes']:,} |
| Byte-exact ASM bytes | {m['byte_exact_asm_bytes']:,} |
| Identified routine entry candidates | {m['identified_entry_candidates']} |
| Translated C routines | {m['translated_c_routines']} |
| Translated C code bytes | {m['translated_c_code_bytes']} |
| Differential cases | {m['differential_cases']} |
| Mutation checks detected | {m['mutations_detected']} |
| Original instruction coverage | {len(executed)} / {m['instructions']:,} decoded ({100*len(executed)/m['instructions']:.3f}%) |
| Unresolved image bytes / runs | {m['unresolved_image_bytes']:,} / {m['unresolved_byte_runs']} |
| Unresolved runs inside provisional code frame | {m['unresolved_main_code_candidate_runs']} ({m['unresolved_main_code_candidate_bytes']:,} bytes) |
| Resolved static CFG edges, including fallthrough | {m['resolved_edges']:,} |
| Unresolved direct targets / indirect transfers | {m['unresolved_direct_targets']} / {m['unresolved_indirect_transfers']} |
| Runtime-modified control-flow frontiers | {m['runtime_control_frontiers']} |
| Additional state-specific main instruction sites | {state_insns} |
| Known conditional indirect edges | {m['indirect']['conditional_edges']} |

The decoded instruction denominator is incomplete: unknown runs in the main and
sound-driver images may add executable bytes. Entry candidates include historical leads,
shared tails and manually investigated code; they are not proven disjoint functions.
The complete region partition labels uncertainty rather than claiming classification.
There are {verified['encoding_exceptions']:,} main-image decoded instructions expressed as explicit encoding exceptions.

Gate A passes for the main EXE: deterministic static unpack, full byte comparison,
63 independently checked relocations, entry/stack state and input identity. Gate B
has an exact buildable initial ASM image, but remains open for code/data, indirect
transfer, external-driver and semantic closure. Gates C/D have the checksum,
resource/decoder/file/read/cache/allocation/leaf, special VGA strip and PC-speaker helper clusters.
The two checksum, thirteen DAT, cache allocation, video/vector/timer restoration, fatal cleanup/file-error printing, raw-resource, RLE, four special VGA strip and
special graphics setup, decimal helper, resource selection, four object-record
main routines, the four-call object-state span, VGA clear, drawing-layout setter
and connected level-drawing/minimap callers, the live level-header prefix,
clipping/dirty leaves and the scoped
planar preparation/geometry/dispatch/source spans, all six aligned bodies and
all six shifted bodies, the actual8822 entry, packed terrain caller, two command loops,
object-drawing suffix and full394F redraw composition
are TESTED within docs/checksum.md,
docs/dat.md, docs/dat-io.md, docs/dat-section.md, docs/dat-cache.md, docs/cache-allocation.md, docs/video-restore.md, docs/vector-restore.md, docs/timer-restore.md, docs/fatal-cleanup.md, docs/file-error.md, docs/resource-raw-full.md, docs/dat-files.md,
docs/dat-load.md, docs/resource-raw.md, docs/resource-rle.md, docs/special-blit.md,
docs/special-setup.md, docs/decimal-digits.md, docs/resource-select.md and
docs/object-records.md, docs/interaction-cells.md, docs/vga-clear.md,
docs/drawing-layout.md, docs/level-drawing.md, docs/minimap.md,
docs/drawing-clip.md, docs/drawing-dirty.md, docs/drawing-inputs.md,
docs/drawing-dispatch.md, docs/drawing-source.md, docs/drawing-plan.md,
docs/aligned-opaque.md, docs/aligned-masked.md, docs/aligned-protected.md,
docs/aligned-read-mask.md, docs/aligned-mask-effects.md, docs/shifted-mask-effects.md
docs/shifted-opaque.md, docs/shifted-masked.md, docs/shifted-protected.md,
docs/shifted-read-mask.md, docs/drawing-render.md, docs/terrain-stream.md,
docs/object-drawing.md, docs/level-redraw.md and docs/level-header.md's domains; remaining
main entry candidates are UNTRANSLATED. CS:8363 reachability remains UNRESOLVED despite
its complete bounded instruction/branch coverage. Gate E is not started.

The checksum tests execute 44/44 cluster instruction addresses and all 10 static
branch edges. They compare registers, defined flags and the entire 1 MiB memory,
including push/pop residue, across poisoned fixtures. AF is excluded only on the
phase-wrap path, where the last XOR makes it architecturally undefined.

The DAT leaf suite covers 33/33 instructions and all six local branch edges in
470 cases. It compares full memory, registers and defined flags, including zero
bit counts (256 iterations), zero incremented match counts (65,536 iterations),
live overlapping copies and overwritten saved registers. Three compiled mutants
are detected. Cache allocation, retry UI and fatal cleanup remain UNTRANSLATED;
the strict static extractor's validation rules are not substituted for original
runtime behavior. See dat.md.

Loaded sound-component images reconstruct exactly, with separate static accounting:

| Image | Exact ASM bytes | Classified bytes | Decoded instructions | Entry candidates | Unresolved transfers | C routines |
|---|---:|---:|---:|---:|---:|---:|
'''
    for name,s in m['sound'].items():
        text+=f'| {name} | {s["byte_exact_asm_bytes"]:,} | {s["classified_bytes"]:,} | {s["instructions"]} | {s["identified_entry_candidates"]} | {s["unresolved_transfers"]} | {s["c_routines"]} |\n'
    text+=f'''
Across all four component images, {combined_bytes:,} ASM bytes are exact and {combined_insns:,}
instructions have been decoded. C differential coverage is {c_executed} / {combined_insns:,}
({100*c_executed/combined_insns:.3f}%) of this still-incomplete decoded inventory. There are
{m['all_images_translated_c_routines']} tested C routines occupying {m['all_images_translated_c_bytes']} original code bytes across images,
with {m['all_images_differential_cases']} differential cases and {m['all_images_mutations_detected']} compiled mutations detected. Six bounded
DAT extraction checks exercise 145 main-image instructions; these are extractor
verification, not C translation coverage and not driver execution tests.

All 16 legacy AdLib signatures at segment 2911 match the static extraction. The
seventeenth external lead is F000:FF53 firmware/environment code, not a driver entry.
All three sound dispatch tables lack sufficient bounds checks; their out-of-table paths
remain unresolved. Driver code/data closure and behavioral translation are open.
Main INT3 protection has independently checked state-specific views: 372 stream
instructions (325 TF-on, 47 TF-off) and 29 transformed INT1 instructions. The
original handlers pass 19 constructed-frame cases and checks at every one of the
325 derived TF-on instruction points, comparing full memory, registers and defined
flags. These checks execute only 61 handler instruction sites; the disk-check body
has not been executed. The two raw-image control frontiers remain represented in
the separate protection CFG. Platform contracts, memory aliases and skipped code
still need review; see protection.md. No protected routine has been translated to C.
No public executable or proprietary asset is tracked. See executable.md for local
provenance, control-frontier.json for addresses, and next-work.md for proof obligations.

Callback evidence traces all 32 recovered object-record pointer stores to nine
drawing callback slots and identifies four display probes, three input callbacks
and the code-input BP callback. The 18 known indirect edges are present in the CFG,
while all five near-callback target domains remain explicitly incomplete. Thirty-two
bounded caller fixtures cover 214 original caller instruction sites with declared
callee boundaries. They check routing and save/restore behavior, including DF-set
traversal and unlisted live pointers; they are not C coverage or callee tests.
See indirect-callbacks.md for alias and incoming-state obligations.

The PC-speaker image is MAIN.DAT section 5: 758 separately reconstructed payload
bytes loaded over canonical zeros at main 08420..08715. Component byte totals count
both stored main bytes and the payload image; they are not unique runtime-memory
bytes. Original extraction is checked at the actual overlay destination at two loads.
The payload's trailing 161 bytes and single pre-entry byte remain UNKNOWN. Its three
closed helpers (effect selection, tick and stop) now have C11 cores and near-call
adapters. The PC-speaker suite compares full memory/registers, defined flags and
port traces in 335 cases, covers all 60 helper instruction sites and all 17 branches,
and detects three compiled mutations. The IRQ dispatcher remains UNTRANSLATED;
none of its unresolved target paths has been silently replaced. See pcspeaker.md.

Two saved INT08 chains now have explicit external IRET edges and original return
continuations. Nineteen bounded tail cases check complete memory and saved-register/
flag results across loads, stack wrap and external clobbers. Nineteen installed-
handler fixtures check 0F6F/0F70/18F8 and their declared service boundaries. These
are caller/handler checks, not full timer, BIOS, C or game execution coverage.
See interrupts.md for provider contracts and the menu wrapper's unsaved ES effect.

The complete DAT read wrapper at 1D2E..1E1B now has {m['dat_io']['case_count']}
bounded original-code cases, covering all {m['dat_io']['original_instruction_sites']} instructions and
{m['dat_io']['branch_edges']} branch edges under declared DOS fixtures. Full memory/register/flag
checks expose direct-read errors, short reads, cache creation and hits, saved-frame
aliases, ignored cache-fill errors and pointer/count wrap. This is provider-contract
evidence, not C translation or actual DOS execution coverage; see dat-io.md.
The same original wrapper also has a C11 core and near-call adapter, verified in
{io['case_count']} native differential cases covering all 106 sites and 12 branches, with
three compiled mutations detected. Its narrow DOS file-size/read services have
declared register-preservation contracts. The skipped UNKNOWN byte at 1D7C is
excluded from translated-byte accounting. Full DOS/FCB platform behavior and the
other resource-loading routines remain open.

The DAT section decoder and its read-distance/shared-copy entry now call C cores
directly. {section['case_count']} integrated differential cases execute all 235 decoder,
leaf and read-wrapper sites and all 32 local decoder/leaf branch edges. They
compare full memory, registers, defined flags and service traces, including real
sound sections and malformed constructed headers. Three compiled section mutations
are detected. Only AF after final AND DH,DH is excluded; read-error flags are fully
compared. The fatal jump to 04D0 is an explicit exit with its original saved frame,
not a translated cleanup routine. Four skipped UNKNOWN bytes are excluded from
translated-byte accounting. Direct helper calls retain original return-word residue;
overwriting those active return words is outside the current verification domain.
See dat-section.md for unsigned termination, ignored high size words and aliases.

DAT filename preparation, cache selection and startup cache disabling now have
C11 cores: {cache['case_count']} cases cover all 96 instruction sites and 18 branch edges,
with three compiled mutations detected. Full memory/register/defined-flag checks
preserve wrapped padding counts, DF, the last-byte mismatch hit, record-pointer
wrap and saved-register aliases. No host filename normalization or corrected
string comparison is substituted. The UNKNOWN cache allocation code remains
open; see dat-cache.md.

File open/check wrappers now have C cores: {files['case_count']} cases cover all 69
wrapper sites and 16 wrapper edges, with three compiled mutations detected.
Native cache calls are exercised inside CheckDatFile. DOS open/attributes and
the original game retry callee at 4B1C are declared verification boundaries;
the retry callee's rendering/input body is not translated or counted as executed.
The 1949 fatal transfer preserves the original outer save frame and message offset.
See dat-files.md for clobbers, aliases and remaining caller/platform ownership.

The resource-loader caller and its shared segment-preserving decoder tail now
call native file and decoder cores directly. {resource['case_count']} integrated cases
cover all 30 caller instruction sites and eight caller branch edges, with three
compiled mutations detected. Full memory/register/defined-flag and service/callee
traces preserve ignored open carry, live saved-DS corruption and both fatal frames.
Two cases start at the constructed post-check continuation to test caller branches
without asserting that a normal CheckDatFile return can produce carry. The UNKNOWN
1B97 byte is excluded; overlapping shared-tail bytes/sites are counted once.
DOS and 4B1C retry bodies remain declared seams; fatal cleanup and higher resource
ownership are still open. See dat-load.md.

The raw-resource open/read/close routine at 1916 now has a C11 core: {raw['case_count']}
cases cover all 27 instruction sites and eight branch edges, with three compiled
mutations detected. Full memory/register/defined-flag and service traces preserve
short reads, partial AH writes, live restored-segment corruption and all three
distinct fatal frames/message offsets. Its 49 C-covered bytes exclude two UNKNOWN
skipped bytes; the shared 1949 error-print path remains untranslated. Actual DOS
behavior across segment ends and higher resource ownership remain open.
See resource-raw.md.

The resource RLE routine at 1B42 has a C11 core: {rle['case_count']} cases cover all
29 instruction sites and 14 branch edges, with three compiled mutations detected.
Full memory/register/defined-flag checks preserve all 256 control-byte meanings,
DF, live input/output overlap, cursor/segment wrap and repeat-byte corruption
when the original segment update replaces AL. These are constructed terminated
streams; complete graphics/resource ownership remains open. See resource-rle.md.

The four special-resource strip entries at 8238/8243/8249/824F share a C11 core.
{blit['case_count']} cases cover all 122 original instruction sites and 22 branch edges,
with three compiled mutations detected. Full RAM, registers, defined flags,
device planes/latches/registers and port/MMIO traces preserve the four-plane strip
layout, mask construction, incoming DF, interrupt-enable changes and live stack
aliases. Sixteen cases use the pinned VGASPEC streams; an independent expected
plane check also verifies untouched video memory in the forward cases. The three
skipped UNKNOWN bytes remain excluded; shared bytes and sites are counted once.
This is a bounded device fixture, not a native VGA backend or IRQ scheduler.
Platform ownership and SDL3 remain open. See special-blit.md.

The special graphics setup caller at 1A7B now connects metadata copies, four
RLE/strip calls and two normal graphics DAT sections through direct native cores.
{setup['case_count']} integrated cases execute all 87 caller sites and 621 dependency/caller
sites. Full RAM/register/defined-flag/device/service-trace comparisons include
four paired VGASPEC/VGAGR inputs, both DF values in declared fixtures, cache paths,
stack wrap, saved-DS corruption, retry and four decoder fatal exits. Independent
expected metadata and four-strip plane contents also pass in the forward cases.
Three compiled mutations are detected. The unchecked final close result remains
unchecked; original fatal frames stay live. This adds 199 C-covered caller bytes;
dependency bytes/sites are counted once. DOS, retry UI, VGA backend and IRQ delivery
remain declared seams. Allocation and full native startup are
still open. See special-setup.md.

The decimal filename helper at 4BC2..4BE6 now has a native C11 core. Its
{decimal['case_count']} original-versus-C cases cover all 19 sites and four branch edges,
all AL values, poisoned AH/control flags, cursor/stack/physical wrap and overwritten
live return words. Three compiled mutations are detected. The separate 260-case
original-only contract check remains extractor evidence and is not added to C coverage.
See decimal-digits.md. The source is split into
maintained physical modules with exact end assertions, and fresh call/dependency
views guide the next cluster. See bottom-up.md. All80 pinned LEVEL sections also
match static extraction and bounded original/native decoding, including13 valid
zero-initial-bit headers; these cases are part of the DAT section C suite above.

The resource selection caller at 197D..1A7A now composes the native decimal,
raw-resource, file/cache and section decoder cores directly. Its
{selection['case_count']} integrated cases cover all 108 caller sites and nine branch edges.
Full memory/register/defined-flag/service comparisons preserve unchecked order-byte
wrap, repeated in-place level decoding, odd override copies, DF, short/long ground
reads, live saved-counter/order/DS aliases, unchecked closes and distinct fatal frames.
Paired original LEVEL/ground/odd/VGAGR/VGASPEC inputs also pass, with independent
record expectations. Three compiled mutations are detected. The 253 C-covered
caller bytes exclude the skipped UNKNOWN NOP; dependency bytes/sites are counted
once. DOS, 4B1C retry UI and 1949/04D0 fatal bodies remain explicit unported seams.
Object/terrain ownership and native startup remain open; see resource-select.md.

Two closed level-object helpers now have native C11 cores. The graphics-record
copy at 378A has {objects['case_count']} cases covering all 26 sites and four edges;
the type-one coordinate collector at 389F has {coordinates['case_count']} cases
covering all 63 sites and 12 edges. Each suite includes all 80 supplied LEVEL
sections; the graphics copy also uses the matching GROUND inputs. Full RAM,
registers and defined-flag comparisons retain stale slots, incoming DF, wrapped
unchecked type lookup, live saved-cursor/counter and return aliases, counts 0..32,
zero-X acceptance, and the original default repeated+0A store/+0C stale bug.
Six compiled mutations are detected. These disjoint 221 bytes add 89 original
instruction sites; shared upstream dependencies remain counted once. The helper
ASM is grouped at its unchanged physical position in level_objects.asm with
start/end assertions. The larger 36B6/394F setup/drawing pipelines remain
untranslated. See object-records.md.

The SS interaction-cell writers at 37C2/3839 now have native cores with
{cells['case_count']}/{steel['case_count']} cases, 54/47 sites and 9/8 branch edges.
Zero object dimensions mean 256 iterations; all 256 packed steel dimensions,
byte3-only presence, unchecked template lookup, live row-save/input/return aliases,
offset and 20-bit wrap are retained. Each suite includes all 80 original LEVEL
sections; object cases pair their GROUND inputs. Six compiled mutants are detected.
No separate cell map replaces SS, which also owns the stack and VGA mirrors.

The 376A..3775 span now connects the four native object helpers directly in
{state['case_count']} cases, covering four caller/194 integrated sites and 33 integrated
edges. Independent SS-window and graphics/coordinate output checks pass all 80
LEVEL/GROUND pairs. Changed callee RET words after each of the four calls expose
their actual target before any target instruction executes. Normal continuation
is 3776; the outer 36B6 RET remains live. Three compiled mutants are detected.
This adds 12 caller bytes without claiming a complete 36B6 translation. Full setup,
VGA/IRQ ownership and far drawing remain open; see interaction-cells.md.

The VGA clear at 4DF8 and far drawing-layout setter at 8808 now have native
cores in {clear['case_count']}/{layout['case_count']} cases, covering 25/10 sites.
The 368E initialization and 36AD clear tail connect them directly in
{drawing['case_count']} cases, covering 14 caller/49 integrated sites and the
single tail-JMP edge. Full RAM/register/defined-flag and device comparisons
preserve live SS mirrors/CALL frames/RET targets, incoming DF and IF,
truncated pitch/low extent, wrapped segment publication and aperture aliases.
Independent plane footprints, untouched bytes, port words and layout fields pass.
These four entries add 129 unique C bytes and 49 sites; nine compiled mutants
are detected. The layout suite isolates two SP-boundary cases as body comparison
plus permissive adapter-model checks, not original-hardware far-return equivalence.
The connected suite independently records and isolates Unicorn's RETF read-hook
artifact without patching return targets. CPU-family stack-limit faults, IRQ
delivery, minimap, terrain and the broader level consumers remain open. See
vga-clear.md, drawing-layout.md and level-drawing.md.

The closed minimap sample/row/column at 7A39/7A25/796F now compose native cores
in {sample['case_count']}/{mmrow['case_count']}/{mmcolumn['case_count']} cases, covering all 96 sites and fourteen
integrated edges. Two complete thirteen-call cycles compare original and native
on the same evolving RAM/device state with both DF values. Full RAM/register/
defined-flag, ordered port/MMIO and independent whole-plane checks preserve the
population>8 threshold, separate ES byte wrap, live SS save/RET/counter aliases,
signed column comparison, DF-sensitive CS clear, twenty accumulated/nineteen
displayed rows and final latch reads. Nine compiled mutants are detected. The
{sample['native_exhaustive_population_vectors']:,} native source-population vectors remain separate from original differential
and instruction coverage. This adds 235 unique C bytes; the dedicated flat
minimap.asm module keeps byte order and UNKNOWN classifications unchanged.
IRQ/device timing, executing-code corruption, CPU-family segment-limit faults,
terrain/far drawing and broader level consumers remain open; see minimap.md and
minimap-vga.md.

The clipping and dirty-cell leaves at 9967/9A15 now compose directly in the
scoped 882D..885D preparation span, with {clip['case_count']}/{dirty['case_count']}/{inputs['case_count']} original/native cases.
The leaves cover 73/63 sites and 29/16 edges; the connected span covers 18 caller/
154 integrated sites and 51 edges. Full RAM/register/defined-flag and ordered byte
checks retain signed versus sign-only clipping, byte-rounded zero counts, live
DS/SS field/save aliases and changed childRET targets. Nine compiled mutants are
detected. These add 344 unique C bytes and 154 sites. The original 8822 prologue's
seven sites are separate evidence in these preparation-only suites; 885E dispatch
and88AB RETF remain boundaries of that API. The actual-entry suite below verifies
the native prologue and abort return. The decoded 9996 NOP remains outside
the normal-entry tests without a dead-code claim. An independent original MUL/
MOV observation records Unicorn's transient memory-hook CF/OF artifact; bus
flags use original instruction-boundary snapshots, with all defined bits checked.
VGA devices, IRQ delivery, executing-code corruption and CPU-family faults
remain open for this RAM scope. See drawing-clip.md, drawing-dirty.md and
drawing-inputs.md.

The destination-positioning and path selector at 885E, shared 939E tail and
four source-row spans at 88BF/9140/93A7/9810 now compose directly with the
native 882D preparation. The dispatch/source/connection suites pass
{dispatch['case_count']}/{source['case_count']}/{plan['case_count']} original/native cases, with 41/92/287 original sites.
They retain live page/pitch/shift words, packed count truncation, reverse-source
wrap, two separate vertical-skip reads, PUSH/store/POP control aliases and
4000/8000/20/40 priority. Independent geometry/cursor/stride/body expectations
cover all eight residues and low-bit modes, overlapping effect flags and both
reverse states. Nine compiled mutants are detected. This adds 348 unique bytes
and 133 sites; the connected wrapper adds no caller bytes. Original 8822 prologue
sites remain separate. Incoming 88A6 ZF-to-88AB is tested as its own bounded entry
state and excluded from the normal-entry connection without a dead-code claim.
The planar family now has a flat physical module at 8822..9A8F with exact end
assertions. Selected VGA bodies, far returns, IRQ/device semantics, self
modification and broader level consumers retain explicit domains. The complete
normal-entry connection is described below. See drawing-dispatch.md, drawing-source.md and drawing-plan.md.

The aligned opaque body at 983B now has a native core composed with drawing
preparation. The body/connection suites pass {opaque['case_count']}/{render['case_count']} original/native cases,
including four plane passes, count wrap, DF, live segment/stack aliases, latch
reads, ordered port/MMIO/SS accesses and CLI/STI effects. The 149 normal-entry
body sites add 298 unique C bytes; UNKNOWN 98F4/9932 remain excluded without
dead-code claims, and the 988B shared entry retains separate incoming-state
obligations. The connection adds no bytes and keeps original 8822 prologue sites
outside this older scoped suite. Six compiled mutants are detected.
Asynchronous IRQ delivery, executing-code mutation and CPU-family faults remain
outside the native domains; the actual8822 connection is described below. See aligned-opaque.md and
drawing-render.md for the exact tested domains and return-oracle observations.

The default aligned masked body at 93F6 has a native core in
{masked['case_count']} standalone cases and a preparation connection in
{masked_render['case_count']} cases. Its 326 unique bytes/166 sites exclude
UNKNOWN 94C7/9507. The first pass advances BX independently of DF and uses a
live per-byte VGA mask; later passes OR source bytes into destination latches.
Original CLI/STI timing, INC/ADD flags, DS/SS saves and far-return words remain
live. The general renderer API also retains the opaque 983B branch; the older
opaque-scoped API preserves its explicit masked-body seam. The connection runs
{masked_render['masked_body_case_count']} masked draws and
{masked_render['opaque_body_case_count']} opaque draws; two saved-BP aliases select
the explicit 969C effect seam in this API. Six compiled mutants are detected. Original 8822
prologue sites remain excluded from this older suite. See aligned-masked.md and
drawing-render.md.

The four other aligned bodies add 721 unique translated bytes: protected953E
(349, excluding UNKNOWN9659), read-mask969C (155), effect20 (109) and effect40
(108). They pass {protected['case_count']}/{readmask['case_count']}/{effects['case_count']}
standalone cases and {aligned_render['case_count']} all-aligned preparation
connections. The connection covers {len(aligned_render['executed_instruction_addresses'])}
integrated sites and {len(aligned_render['branch_edges'])} edges; sites are unioned,
not summed. All original body RETFs receive actual single-step probes. Plane-3
comparison/protection, live savedDX/DS, explicit byte OUT/IN replies and the
20/40 row-cursor asymmetry remain original behavior. Missing byte providers
leave969C explicit. These four suites detect twelve compiled mutants. See
aligned-protected.md, aligned-read-mask.md, aligned-mask-effects.md and
drawing-render.md for constructed-state domains and IRQ/device timing limits.
The original8822 prologue and other shifted bodies remain outside these older
scoped suites; the new full-entry report verifies them below.

The shifted20/40 bodies at8FF7/909C add329 translated bytes/168 original sites,
including their two far-return adapters. They pass
{shifted_effects['case_count']} standalone original/native cases and
{shifted_render['case_count']} preparation connections. Their scratch masks are
copied through live DS/ES with incoming DF, then shifted forward through SHR/RCR
carry chains. Both variants advance SI between rows. The relocated09A9 operand,
live saves, decremented destination-row word and unchecked count/shift wraps
remain original behavior. The connection covers seven shift residues, DF,
reversal, enable masks and the preserved older API/provider/unported-body seams.
The two suites detect six compiled mutants. See shifted-mask-effects.md,
shifted-drawing.md and drawing-render.md. Scratch names identify runtime bases,
not proven allocation extents; their stored UNKNOWN bytes remain unresolved.

The shifted default masked890E, protected8B42, read-mask8D66 and opaque916B
bodies add2,328 decoded C bytes/1,310 known sites, including far-return adapters.
Their standalone suites pass {shifted_masked['case_count']}/{shifted_protected['case_count']}/{shifted_readmask['case_count']}/{shifted_opaque['case_count']}
cases and detect twelve mutants. UNKNOWN8ADD/8CF4/8F8D/9339 stay excluded.
Copies and sentinels follow DF while carry chains and mask reads go forward.
Source shifts and mask shifts reread the live shift byte separately; backward
copies may overwrite live row fields. The read-mask path caches all rows before
drawing and keeps its word-port DX changes; protection leaves BX untouched.
See shifted-masked.md, shifted-protected.md, shifted-read-mask.md and
shifted-opaque.md for boundary hashes, return probes and unchecked domains.

The actual8822 native entry now composes its seven-instruction prologue,
preparation, all twelve bodies and88AB no-draw far return in {bitmap['case_count']}
cases. It covers {len(bitmap['executed_instruction_addresses'])} integrated
original sites and {len(bitmap['branch_edges'])} observed edges, and detects three
renderer mutants. The prologue and88AB add12 unique translated bytes/eight sites;
shared body sites/bytes are unioned with leaf and earlier connection evidence.
Independent packed-bit models verify whole-plane footprints, including live
stride changes caused by backward scratch copies. Full RAM/register/defined
flags and ordered bus/ports/VGA state match original execution. Older scopes,
changed child return and missing aligned969C byte-provider seams remain visible.
UNKNOWN bytes, shared988B other incoming states, allocation/producer domains,
asynchronous IRQ/device scheduling and broader gameplay integration remain open.

DrawPackedTerrainPiece at7C67 now derives the original control/coordinates and
reads a live eightbyte GROUNDterrain record before calling the native8822 core.
Its {terrain_inputs['case_count']} prefix cases cover all33 caller-prefix sites/four
conditional edges; {terrain['case_count']} connected cases cover36 caller sites and
{len(terrain['executed_instruction_addresses'])} integrated sites. The full connection
uses every supplied GROUNDterrain record (320 metadata records) with constructed
source bytes. Independent packed-input, whole-plane and untouched-record checks
complement whole RAM/register/defined-flag/orderedbus/VGA comparison. Six direct
core-boundary probes verify ready/changednear/changedfar statuses. Eight mutation
checks are detected across the prefix/connection suites. This adds85 unique C
bytes; shared renderer sites/bytes are unioned, not summed.
The far CALL writes CS then7CBA; changed live IP/CS stop before any target executes.
Normal return pops live savedSI before the caller's nearRET. Tests retain signed
SAR-y, ignored selectorbit6, x/control bits, reversal, scratch/stack aliases and
physical/offset wraps. The actual original RETF is executed with its documented
read-hook observation, then hooks are restored before caller continuation. IRQ,
device/producer/allocation ownership and wider level callers remain open. See
terrain-drawing.md; no game was booted and no assets were changed.

The374F/395F terrain command loops now call the native7C67/8822 chain directly.
{commands['case_count']} prefix cases and24 original MOV-SI probes verify separate
big-endian byte loads, fullFFFF sentinel, flags and offset/physical wraps.
{streams['case_count']} full-stream cases include all80 pinned LEVEL streams at
both entries with the matching GROUND metadata, constructed graphics and the
visible1664x164 viewport. WholeRAM/register/definedflags/orderedbus/VGA checks
retain liveDS/SI and changed child returns; each ordinary rendered body also
gets an independent whole-plane check. Both loops add54 unique original C bytes
and20 sites. Source allocation, native device/IRQ ownership and the surrounding
36B6 initialization and broader platform ownership remain open. See terrain-stream.md
for tested domains and caps.

The397D object suffix now composes the native8822 core in
{object_draw['case_count']} adapter cases and{object_draw['core_boundary_case_count']}
additional core-boundary probes. All33 caller sites,all4 caller edges and all6
aligned body families execute,including all80 pinned LEVEL/GROUND entry states.
Those suffix fixtures model the preceding378A copy; they do not count that
copy as executed. Full RAM/register/defined-flag/bus/VGA and independent input/
plane checks preserve live DS,SI/DI/CX saves,changed near/far returns,bit0 clearing
and the original65,536-iteration zero-byte-count behavior. Four mutants are
detected. Its81 translated bytes overlap the full redraw caller below.

RedrawLevel at394F now directly composes initialization,normal terrain or
special setup,record copying and object drawing. {redraw['case_count']} adapter
and{redraw['core_boundary_case_count']} core-boundary cases cover all50 caller
sites,all10 caller edges and{len(redraw['executed_instruction_addresses'])}
integrated sites;three compiled mutations are detected. Four paired real
VGASPEC/VGAGR inputs,both fatal transfers,provider stops,live DS and altered
clear/layout/copy return words retain their explicit boundaries. The126
translated caller bytes exclude UNKNOWN395E and overlap the27-byte redraw
terrain loop and81-byte object suffix. These byte ranges and all dependency
instruction sites are unioned,never summed. Special/DAT/RLE direct-RAM accesses
remain within the declared ordinary-RAM/intact-internal-return domain;parent
and bus-aware child events,VGA state,whole RAM and declared DOS effects are
checked separately. IRQ/timing,retry UI and arbitrary provider/alias behavior
remain open. See object-drawing.md and level-redraw.md.
'''
    return m,text

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write-doc',action='store_true')
    a=p.parse_args()
    metrics,text=report()
    if a.write_doc:
        (ROOT/'docs/completeness.md').write_text(text,encoding='utf-8')
    print(text)
