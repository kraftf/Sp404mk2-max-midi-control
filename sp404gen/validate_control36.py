"""
Validates Roland_SP404MK2_Control-36.maxpat: the display-shadow-int
subpatcher pilot (see build_control36.py's module docstring for the design
and its intentionally narrow scope).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-36.maxpat')

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

def incoming(dst_id, dst_in):
    return [tuple(l['patchline']['source']) for l in lines
            if l['patchline']['destination'] == [dst_id, dst_in]]

BUSES = [1, 2, 3, 4, 5]
DIAL_PARAMS = ['cc16', 'cc17', 'cc18', 'cc80', 'cc81', 'cc82']
ALL_PARAMS = ['efx'] + DIAL_PARAMS + ['onoff']
VISIBLE = {
    'efx':   'obj-18',
    'cc16':  'obj-458', 'cc17': 'obj-466', 'cc18': 'obj-474',
    'cc80':  'obj-482', 'cc81': 'obj-490', 'cc82': 'obj-498',
    'onoff': 'obj-454',
}

# --- old sh_id objects must be gone entirely ---
for b in BUSES:
    for param in ALL_PARAMS:
        check(f'obj-pv2-sh-{param}-{b}' not in box_by_id,
              f'obj-pv2-sh-{param}-{b} should have been removed')

# --- one subpatcher per bus, correct shape ---
for b in BUSES:
    bp_id = f'obj-pv36-dispshadow-b{b}'
    check(bp_id in box_by_id, f'{bp_id} missing')
    bp = box_by_id[bp_id]
    check(bp['maxclass'] == 'newobj', f'{bp_id} should be a newobj (plain subpatcher)')
    check(bp['text'] == f'p Bus{b}DisplayShadow', f'{bp_id} wrong text: {bp["text"]}')
    check(bp['numinlets'] == 16, f'{bp_id} should have 16 inlets, got {bp["numinlets"]}')
    check(bp['numoutlets'] == 8, f'{bp_id} should have 8 outlets, got {bp["numoutlets"]}')
    check('patcher' in bp, f'{bp_id} missing embedded patcher content')
    sub = bp['patcher']
    sub_boxes = {sb['box']['id']: sb['box'] for sb in sub['boxes']}
    sub_lines = sub['lines']

    def sub_outgoing(src_id, src_out):
        return [tuple(l['patchline']['destination']) for l in sub_lines
                if l['patchline']['source'] == [src_id, src_out]]

    for i, param in enumerate(ALL_PARAMS):
        in_bg = f'in-bg-{param}'
        in_sel = f'in-sel-{param}'
        int_id = f'int-{param}'
        out_id = f'out-{param}'
        check(in_bg in sub_boxes, f'{bp_id}: {in_bg} missing')
        check(in_sel in sub_boxes, f'{bp_id}: {in_sel} missing')
        check(int_id in sub_boxes, f'{bp_id}: {int_id} missing')
        check(out_id in sub_boxes, f'{bp_id}: {out_id} missing')
        check(sub_boxes[in_bg]['maxclass'] == 'inlet', f'{bp_id}: {in_bg} not an inlet')
        check(sub_boxes[in_bg]['index'] == 2 * i + 1,
              f'{bp_id}: {in_bg} index should be {2*i+1}, got {sub_boxes[in_bg]["index"]}')
        check(sub_boxes[in_sel]['maxclass'] == 'inlet', f'{bp_id}: {in_sel} not an inlet')
        check(sub_boxes[in_sel]['index'] == 2 * i + 2,
              f'{bp_id}: {in_sel} index should be {2*i+2}, got {sub_boxes[in_sel]["index"]}')
        check(sub_boxes[int_id]['text'] == 'int 0', f'{bp_id}: {int_id} wrong text')
        check(sub_boxes[out_id]['maxclass'] == 'outlet', f'{bp_id}: {out_id} not an outlet')
        check(sub_boxes[out_id]['index'] == i + 1,
              f'{bp_id}: {out_id} index should be {i+1}, got {sub_boxes[out_id]["index"]}')
        # internal wiring: cold (bg) -> int inlet1, hot (sel) -> int inlet0, int -> outlet
        check((int_id, 1) in sub_outgoing(in_bg, 0), f'{bp_id}: {in_bg} not wired to {int_id} cold inlet')
        check((int_id, 0) in sub_outgoing(in_sel, 0), f'{bp_id}: {in_sel} not wired to {int_id} hot inlet')
        check((out_id, 0) in sub_outgoing(int_id, 0), f'{bp_id}: {int_id} not wired to {out_id}')

    # --- external wiring: main patch bg/sel sources -> this subpatcher's inlets,
    #     subpatcher outlets -> the SAME destinations sh_id used to feed ---
    for i, param in enumerate(ALL_PARAMS):
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        sel_id = f'obj-pv2-sel-{param}'
        bi = b - 1
        check((bp_id, 2 * i) in outgoing(bg_id, 0),
              f'{bg_id} should feed {bp_id} inlet {2*i}')
        check((bp_id, 2 * i + 1) in outgoing(sel_id, bi),
              f'{sel_id} outlet {bi} should feed {bp_id} inlet {2*i+1}')
        # bus 1 also feeds a debug print object (obj-pv36-dbg-print-{param}) --
        # an intentional, temporary testing aid, not part of the real signal
        # path, so allow it as an extra destination on top of the real one(s).
        actual = outgoing(bp_id, i)
        dbg_dest = (f'obj-pv36-dbg-print-{param}', 0)
        real = [d for d in actual if d != dbg_dest]
        if param == 'efx':
            check(sorted(real) == sorted([('obj-pv2-rps-efx', 0), ('obj-pv2-efx-mfan', 0)]),
                  f'{bp_id} outlet {i} (efx) should feed BOTH rps-efx and efx-mfan')
        else:
            check(real == [(VISIBLE[param], 0)],
                  f'{bp_id} outlet {i} should feed {VISIBLE[param]}')
        if b == 1:
            check(dbg_dest in actual, f'{bp_id} outlet {i} should also feed the debug print tap')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
