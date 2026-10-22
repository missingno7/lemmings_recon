"""Fresh static routine/dependency views for bottom-up investigation.

Bodies follow branches/shared tails without following calls. Native ranges are
the ledger's tested domains; outgoing tails/calls outside C remain visible.
Neither a decoded leaf nor TESTED establishes whole-program semantic closure.
--asm follows original decoded bodies even when a narrower C domain exists.
"""
import argparse
from bisect import bisect_right
from common import ROOT,read_json
from explore import analyze
from coverage import translated_code_bytes
from where import address,rows

CALLS={'call','far_call','indirect_call'}

def body(entry,instructions,outgoing,frontiers,allowed=None):
    todo=[entry];seen=set();callees=set();boundaries=set();problems=set();services=set()
    while todo:
        pc=todo.pop()
        if pc in seen:continue
        if allowed is not None and pc not in allowed:
            boundaries.add(pc);continue
        if pc not in instructions:
            problems.add((pc,'missing decoded target'));continue
        seen.add(pc)
        for kind in frontiers.get(pc,()):problems.add((pc,kind))
        mnemonic=instructions[pc]['mnemonic']
        if mnemonic in ('in','out','insb','insw','outsb','outsw','cli','sti'):services.add((pc,mnemonic))
        for edge in outgoing.get(pc,()):
            kind,target=edge['kind'],edge['target']
            if kind in CALLS:
                if target is not None:callees.add(target)
            elif kind in ('interrupt','runtime_interrupt','external_interrupt_chain','external_interrupt_return'):
                services.add((pc,kind))
            elif target is not None:todo.append(target)
    return dict(sites=seen,callees=callees,boundaries=boundaries,problems=problems,services=services,
                bytes=sum(instructions[p]['size'] for p in seen))

def routine_views(analysis,ledger,*,original=False):
    instructions={r['address']:r for r in analysis['instructions']};outgoing={};frontiers={};callers={}
    for edge in analysis['edges']:
        outgoing.setdefault(edge['source'],[]).append(edge)
        if edge['kind'] in CALLS:callers.setdefault(edge['target'],set()).add(edge['source'])
    for item in analysis['unresolved']:frontiers.setdefault(item['address'],[]).append(item['kind'])
    # A native span is a scoped view of an existing body, not a new discovery
    # seed or a claim that its containing function has been translated.
    # Query labels over already-decoded instructions, including JMP entries and
    # overlapping code/data roles. This never feeds a seed back into analyze().
    symbols={s['address']:s for s in ledger if s['segment']==0 and
             (s['kind']=='entry' or s.get('c_implementation') or s['address'] in instructions)};views={}
    for entry in sorted(set(analysis['routines'])|set(symbols)):
        row=symbols.get(entry,dict(symbol_name=f'entry_{entry:04X}',verification_status='UNRESOLVED'))
        allowed=None
        if row.get('c_implementation') and not original:
            ranges=row.get('c_code_ranges')
            if ranges is None:
                size=row.get('size')
                if not isinstance(size,int) or size<=0:
                    raise ValueError('Missing native extent for '+row['symbol_name'])
                ranges=[(entry,entry+size)]
            allowed={p for a,b in ranges for p in range(a,b)}
        views[entry]=body(entry,instructions,outgoing,frontiers,allowed)|dict(
            symbol=row,callers=callers.get(entry,set()),original_view=original)
    # Bodies follow branch tails, including bytes already owned by native C.
    main=[s for s in ledger if s['segment']==0]
    limit=max((r['address']+r['size'] for r in analysis['instructions']),default=0)
    native_bytes=translated_code_bytes(main,analysis['instructions'],limit)
    for view in views.values():
        view['existing_c_bytes']=sum(instructions[p]['size'] for p in view['sites']
            if all(b in native_bytes for b in range(p,p+instructions[p]['size'])))
        view['outside_c_bytes']=view['bytes']-view['existing_c_bytes']
    return views

def dependency_order(root,views):
    """Postorder investigation list. Stop at scoped native dependencies, flag cycles."""
    done=set();active=set();order=[];cycles=set()
    def visit(entry):
        if entry in active:cycles.add(entry);return
        if entry in done:return
        view=views.get(entry)
        if view and view['symbol'].get('c_implementation') and not view.get('original_view'):
            done.add(entry);return
        active.add(entry)
        if view:
            for target in sorted(view['callees']):visit(target)
        active.remove(entry);done.add(entry);order.append(entry)
    visit(root);return order,cycles

def tag(entry,views):
    view=views.get(entry)
    if view is None:return f'{entry:04X} UNRECOVERED'
    row=view['symbol'];native=' C-domain' if row.get('c_implementation') and not view.get('original_view') else ''
    overlap=''
    if not native and view.get('existing_c_bytes'):
        overlap=f'; {view["existing_c_bytes"]} already-C bytes/{view["outside_c_bytes"]} outside C ranges'
    status='ASM-body' if view.get('original_view') else row['verification_status']+native
    return f'{entry:04X} {row["symbol_name"]} {status} ({view["bytes"]} decoded bytes/{len(view["sites"])} sites{overlap})'

def details(entry,views):
    view=views[entry];print(tag(entry,views))
    source=rows();offsets=[r[0] for r in source];index=bisect_right(offsets,entry)-1
    if index>=0:
        _,path,line,_=source[index];print(f'source: {path.relative_to(ROOT)}:{line}')
    print('call sites:',','.join(f'{p:04X}' for p in sorted(view['callers'])) or 'none')
    print('callees:',', '.join(tag(t,views) for t in sorted(view['callees'])) or 'none')
    for label,items in (('native exits/shared tails',view['boundaries']),('platform/IRQ sites',view['services']),('unresolved',view['problems'])):
        if items:print(label+':',sorted(items))
    if view['symbol'].get('c_implementation'):print('native contract:',view['symbol'].get('verification_evidence','scoped ledger implementation'))
    for ref in view['symbol'].get('data_references',[]):print('operand reference:',ref)
    print('Operand segment tags are syntactic; incoming DS/ES/SS ownership still requires a contract.')

def tree(entry,views,depth,indent='',ancestors=()):
    print(indent+tag(entry,views))
    if entry in ancestors:print(indent+'  [cycle/shared recursion]');return
    view=views.get(entry)
    if view is None:return
    seams(view,indent+'  ')
    if depth:
        for target in sorted(view['callees']):tree(target,views,depth-1,indent+'  ',(*ancestors,entry))

def seams(view,indent='  '):
    """Never hide an open transfer or a provider/device site behind a C tag."""
    for label,key in (('native exits/shared tails','boundaries'),('unresolved','problems'),
                      ('platform/IRQ sites','services')):
        if view[key]:
            items=(f'{p:04X}:{kind}' for p,kind in sorted(view[key])) if key!='boundaries' else (
                f'{p:04X}' for p in sorted(view[key]))
            print(indent+label+': '+', '.join(items))

def bottom_up(entry,views,*,original=False):
    order,cycles=dependency_order(entry,views)
    print('Original-body investigation order (C ranges do not stop traversal):' if original else
          'Pending investigation order; native dependencies retain their bounded seams:')
    for target in order:
        view=views.get(target);note=''
        if target in cycles:note=' [cycle: review as a cluster]'
        elif view and not any(view[k] for k in ('callees','boundaries','problems','services')):note=' [decoded leaf: contract review required]'
        print(tag(target,views)+note)
        if view:seams(view)
    native=set() if original else {t for p in order if p in views for t in views[p]['callees']
            if t in views and views[t]['symbol'].get('c_implementation')}
    # A native root is itself a stopped dependency and must still show its seams.
    if not original and views[entry]['symbol'].get('c_implementation'):native.add(entry)
    for target in sorted(native):
        view=views[target]
        unported={t for t in view['callees'] if t not in views or not views[t]['symbol'].get('c_implementation')}
        print('native dependency:',tag(target,views),
              'unported calls='+','.join(f'{p:04X}' for p in sorted(unported)))
        seams(view)
    print('This is an investigation order, not proof of native readiness or complete target domains.')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',nargs='?');parser.add_argument('--tree',action='store_true')
    parser.add_argument('--depth',type=int,default=3);parser.add_argument('--bottom-up',action='store_true')
    parser.add_argument('--asm',action='store_true',help='follow original CFG rather than clipping to C-tested ranges')
    args=parser.parse_args(argv);views=routine_views(analyze(),read_json(ROOT/'metadata/symbols.json'),original=args.asm)
    if args.target is None:
        for entry in sorted(views):print(tag(entry,views))
        return
    entry=address(args.target)
    if entry not in views:parser.error('Target is not a main-image routine entry or native span')
    if args.bottom_up:
        bottom_up(entry,views,original=args.asm)
    elif args.tree:tree(entry,views,max(0,args.depth))
    else:details(entry,views)
if __name__=='__main__':main()
