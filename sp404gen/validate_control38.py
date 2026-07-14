"""
Validates Roland_SP404MK2_Control-38.maxpat: the hardware-dispatch shadow
subpatcher pass (see build_control38.py's module docstring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-38.maxpat')

with open(PATCH) as f:
    data = json.load(f)
boxes = data['patcher']['boxes']
lines = data['patcher']['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)

def outgoing(src_id, src_out):
    return [tuple(l['patchline']['destination']) for l in lines
            if l['patchline']['source'] == [src_id, src_out]]

BUSES = [1, 2, 3, 4, 5]
DIAL_PARAMS = ['cc16', 'cc17', 'cc18', 'cc80', 'cc81', 'cc82']
ALL_PARAMS = ['efx'] + DIAL_PARAMS + ['onoff']
CTLOUT = {
    'efx':   'obj-30',
    'cc16':  'obj-459', 'cc17': 'obj-467', 'cc18': 'obj-475',
    'cc80':  'obj-483', 'cc81': 'obj-491', 'cc82': 'obj-499',
    'onoff': 'obj-456',
}

for b in BUSES:
    for param in ALL_PARAMS:
        check(f'obj-pv2-hwh-{param}-{b}' not in box_by_id,
              f'obj-pv2-hwh-{param}-{b} should have been removed')

for b in BUSES:
    bp_id = f'obj-pv38-hwshadow-b{b}'
    check(bp_id in box_by_id, f'{bp_id} missing')
    bp = box_by_id[bp_id]
    check(bp['maxclass'] == 'newobj', f'{bp_id} should be a newobj (plain subpatcher)')
    check(bp['text'] == f'p Bus{b}HwShadow', f'{bp_id} wrong text: {bp["text"]}')
    check(bp['numinlets'] == 9, f'{bp_id} should have 9 inlets, got {bp["numinlets"]}')
    check(bp['numoutlets'] == 8, f'{bp_id} should have 8 outlets, got {bp["numoutlets"]}')
    check('patcher' in bp, f'{bp_id} missing embedded patcher content')
    sub = bp['patcher']
    sub_boxes = {sb['box']['id']: sb['box'] for sb in sub['boxes']}
    sub_lines = sub['lines']

    def sub_outgoing(src_id, src_out):
        return [tuple(l['patchline']['destination']) for l in sub_lines
                if l['patchline']['source'] == [src_id, src_out]]

    check('in-trigger' in sub_boxes, f'{bp_id}: in-trigger missing')
    check(sub_boxes['in-trigger']['maxclass'] == 'inlet', f'{bp_id}: in-trigger not an inlet')
    check(sub_boxes['in-trigger']['index'] == 1, f'{bp_id}: in-trigger should be index 1')
    check('trigger-fan' in sub_boxes, f'{bp_id}: trigger-fan missing')
    check(sub_boxes['trigger-fan']['text'] == 't b b b b b b b b',
          f'{bp_id}: trigger-fan wrong text')
    check(sub_outgoing('in-trigger', 0) == [('trigger-fan', 0)],
          f'{bp_id}: in-trigger should feed trigger-fan')

    for i, param in enumerate(ALL_PARAMS):
        in_bg = f'in-bg-{param}'
        int_id = f'int-{param}'
        out_id = f'out-{param}'
        check(in_bg in sub_boxes, f'{bp_id}: {in_bg} missing')
        check(sub_boxes[in_bg]['maxclass'] == 'inlet', f'{bp_id}: {in_bg} not an inlet')
        check(sub_boxes[in_bg]['index'] == i + 2,
              f'{bp_id}: {in_bg} index should be {i+2}, got {sub_boxes[in_bg]["index"]}')
        check(int_id in sub_boxes and sub_boxes[int_id]['text'] == 'int 0',
              f'{bp_id}: {int_id} missing or wrong text')
        check(out_id in sub_boxes and sub_boxes[out_id]['maxclass'] == 'outlet',
              f'{bp_id}: {out_id} missing or not an outlet')
        check(sub_boxes[out_id]['index'] == i + 1,
              f'{bp_id}: {out_id} index should be {i+1}, got {sub_boxes[out_id]["index"]}')
        check((int_id, 0) in sub_outgoing('trigger-fan', 7 - i),
              f'{bp_id}: trigger-fan outlet {7-i} should feed {int_id} hot inlet')
        check((int_id, 1) in sub_outgoing(in_bg, 0),
              f'{bp_id}: {in_bg} should feed {int_id} cold inlet')
        check((out_id, 0) in sub_outgoing(int_id, 0),
              f'{bp_id}: {int_id} should feed {out_id}')

    # external wiring
    check((bp_id, 0) in outgoing('obj-pv2-hw-bussel', b - 1),
          f'obj-pv2-hw-bussel outlet {b-1} should feed {bp_id} shared trigger inlet 0')
    for i, param in enumerate(ALL_PARAMS):
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        check((bp_id, i + 1) in outgoing(bg_id, 0),
              f'{bg_id} should feed {bp_id} inlet {i+1}')
        if param == 'onoff':
            scale_id = f'obj-pv2-hwscale-{param}-{b}'
            check(outgoing(bp_id, i) == [(scale_id, 0)],
                  f'{bp_id} outlet {i} (onoff) should feed {scale_id}')
        else:
            check(outgoing(bp_id, i) == [(CTLOUT[param], 0)],
                  f'{bp_id} outlet {i} should feed {CTLOUT[param]}')

    # SAFETY NET (added after Control-41's real bug): Max determines a
    # subpatcher's external inlet/outlet order by patching_rect X-COORDINATE,
    # NOT by the declared "index" field -- confirmed the hard way when a new
    # inlet's x-position silently shifted every inlet after it.
    all_sub_boxes = [sb['box'] for sb in bp['patcher']['boxes']]
    for kind in ('inlet', 'outlet'):
        items = [sb for sb in all_sub_boxes if sb['maxclass'] == kind]
        by_x = [sb['id'] for sb in sorted(items, key=lambda s: s['patching_rect'][0])]
        by_index = [sb['id'] for sb in sorted(items, key=lambda s: s['index'])]
        check(by_x == by_index,
              f'{bp_id}: {kind} x-coordinate order {by_x} does not match index order {by_index}')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
