"""Fresh static routine/dependency views for bottom-up investigation.

Bodies follow branches/shared tails without following calls. Native ranges are
the ledger's tested domains; outgoing tails/calls outside C remain visible.
Neither a decoded leaf nor TESTED establishes whole-program semantic closure.
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
            elif kind in ('interrupt','runtime_interrupt','external_interrupt_chain'):
                services.add((pc,kind))
            elif target is not None:todo.append(target)
    return dict(sites=seen,callees=callees,boundaries=boundaries,problems=problems,services=services,
                bytes=sum(instructions[p]['size'] for p in seen))

def routine_views(analysis,ledger):
    instructions={r['address']:r for r in analysis['instructions']};outgoing={};frontiers={};callers={}
    for edge in analysis['edges']:
        outgoing.setdefault(edge['source'],[]).append(edge)
        if edge['kind'] in CALLS:callers.setdefault(edge['target'],set()).add(edge['source'])
    for item in analysis['unresolved']:frontiers.setdefault(item['address'],[]).append(item['kind'])
    # A native span is a scoped view of an existing body, not a new discovery
    # seed or a claim that its containing function has been translated.
    symbols={s['address']:s for s in ledger if s['segment']==0 and
             (s['kind']=='entry' or (s['kind']=='continuation' and s.get('c_implementation')))};views={}
    for entry in sorted(set(analysis['routines'])|set(symbols)):
        row=symbols.get(entry,dict(symbol_name=f'entry_{entry:04X}',verification_status='UNRESOLVED'))
        allowed=None
        if row.get('c_implementation'):
            ranges=row.get('c_code_ranges')
            if ranges is None:
                size=row.get('size')
                if not isinstance(size,int) or size<=0:
                    raise ValueError('Missing native extent for '+row['symbol_name'])
                ranges=[(entry,entry+size)]
            allowed={p for a,b in ranges for p in range(a,b)}
        views[entry]=body(entry,instructions,outgoing,frontiers,allowed)|dict(symbol=row,callers=callers.get(entry,set()))
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
        if view and view['symbol'].get('c_implementation'):done.add(entry);return
        active.add(entry)
        if view:
            for target in sorted(view['callees']):visit(target)
        active.remove(entry);done.add(entry);order.append(entry)
    visit(root);return order,cycles

def tag(entry,views):
    view=views.get(entry)
    if view is None:return f'{entry:04X} UNRECOVERED'
    row=view['symbol'];native=' C-domain' if row.get('c_implementation') else ''
    overlap=''
    if not native and view.get('existing_c_bytes'):
        overlap=f'; {view["existing_c_bytes"]} already-C bytes/{view["outside_c_bytes"]} outside C ranges'
    return f'{entry:04X} {row["symbol_name"]} {row["verification_status"]}{native} ({view["bytes"]} decoded bytes/{len(view["sites"])} sites{overlap})'

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
    if view['boundaries']:print(indent+'  native exits: '+','.join(f'{p:04X}' for p in sorted(view['boundaries'])))
    if view['problems']:print(indent+'  unresolved: '+str(sorted(view['problems'])))
    if depth:
        for target in sorted(view['callees']):tree(target,views,depth-1,indent+'  ',(*ancestors,entry))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',nargs='?');parser.add_argument('--tree',action='store_true')
    parser.add_argument('--depth',type=int,default=3);parser.add_argument('--bottom-up',action='store_true')
    args=parser.parse_args();views=routine_views(analyze(),read_json(ROOT/'metadata/symbols.json'))
    if args.target is None:
        for entry in sorted(views):print(tag(entry,views))
        return
    entry=address(args.target)
    if entry not in views:parser.error('Target is not a main-image routine entry or native span')
    if args.bottom_up:
        order,cycles=dependency_order(entry,views)
        print('Pending investigation order; native dependencies retain their bounded seams:')
        for target in order:
            view=views.get(target);note=''
            if target in cycles:note=' [cycle: review as a cluster]'
            elif view and not any(view[k] for k in ('callees','boundaries','problems','services')):note=' [decoded leaf: contract review required]'
            print(tag(target,views)+note)
        native={t for p in order if p in views for t in views[p]['callees']
                if t in views and views[t]['symbol'].get('c_implementation')}
        for target in sorted(native):
            view=views[target]
            unported={t for t in view['callees'] if t not in views or not views[t]['symbol'].get('c_implementation')}
            print('native dependency:',tag(target,views),
                  'exits='+','.join(f'{p:04X}' for p in sorted(view['boundaries'])),
                  'unported calls='+','.join(f'{p:04X}' for p in sorted(unported)),
                  'unresolved='+','.join(f'{p:04X}:{kind}' for p,kind in sorted(view['problems'])),
                  f'platform/IRQ sites={len(view["services"])}')
        print('This is an investigation order, not proof of native readiness or complete target domains.')
    elif args.tree:tree(entry,views,max(0,args.depth))
    else:details(entry,views)
if __name__=='__main__':main()
