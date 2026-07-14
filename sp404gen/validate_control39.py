"""
Validates Roland_SP404MK2_Control-39.maxpat: the EFX-first hardware
dispatch fix (see build_control39.py's module docstring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-39.maxpat')

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

# --- Phase 1 (new EFX-only loop) exists and is correctly shaped ---
efx_uzi = box_by_id['obj-pv39-hw-efx-uzi']
check(efx_uzi['text'] == 'uzi 5', 'obj-pv39-hw-efx-uzi wrong text')
efx_t = box_by_id['obj-pv39-hw-efx-t']
check(efx_t['text'] == 't i i', 'obj-pv39-hw-efx-t wrong text')
efx_bussel = box_by_id['obj-pv39-hw-efx-bussel']
check(efx_bussel['text'] == 'select 1 2 3 4 5', 'obj-pv39-hw-efx-bussel wrong text')

check(outgoing('obj-pv2-rcl-post-t', 2) == [('obj-pv39-hw-efx-uzi', 0)],
      'rcl-post-t outlet2 (FIRST) should now start the EFX-only phase, not hw-uzi directly')
check(outgoing('obj-pv39-hw-efx-uzi', 2) == [('obj-pv39-hw-efx-t', 0)],
      'efx-uzi counter should feed efx-t')
check(outgoing('obj-pv39-hw-efx-t', 1) == [('obj-15', 0)],
      'efx-t outlet1 (FIRST) should set the MIDI channel')
check(outgoing('obj-pv39-hw-efx-t', 0) == [('obj-pv39-hw-efx-bussel', 0)],
      'efx-t outlet0 (SECOND) should bang efx-bussel')
check(outgoing('obj-pv39-hw-efx-uzi', 1) == [('obj-pv2-hw-uzi', 0)],
      'efx-uzi completion (outlet1) should start the existing 7-param phase (hw-uzi)')

# --- each bus's subpatcher: dedicated 10th inlet feeding EFX directly ---
for b in BUSES:
    bp_id = f'obj-pv38-hwshadow-b{b}'
    bp = box_by_id[bp_id]
    check(bp['numinlets'] == 10, f'{bp_id} should now have 10 inlets, got {bp["numinlets"]}')
    sub = bp['patcher']
    sub_boxes = {sb['box']['id']: sb['box'] for sb in sub['boxes']}
    check('in-efx-trigger' in sub_boxes, f'{bp_id}: in-efx-trigger missing')
    check(sub_boxes['in-efx-trigger']['maxclass'] == 'inlet', f'{bp_id}: in-efx-trigger not an inlet')
    check(sub_boxes['in-efx-trigger']['index'] == 10,
          f'{bp_id}: in-efx-trigger should be index 10, got {sub_boxes["in-efx-trigger"]["index"]}')

    def sub_outgoing(src_id, src_out):
        return [tuple(l['patchline']['destination']) for l in sub['lines']
                if l['patchline']['source'] == [src_id, src_out]]

    check(('int-efx', 0) in sub_outgoing('in-efx-trigger', 0),
          f'{bp_id}: in-efx-trigger should feed int-efx hot inlet directly')
    check(('int-efx', 0) not in sub_outgoing('trigger-fan', 7),
          f'{bp_id}: trigger-fan should no longer feed int-efx (EFX now has its own dedicated trigger)')

    # external: efx-bussel outlet(b-1) -> this bus's new inlet 9 (index 10 -> external inlet 9)
    check((bp_id, 9) in outgoing('obj-pv39-hw-efx-bussel', b - 1),
          f'obj-pv39-hw-efx-bussel outlet {b-1} should feed {bp_id} inlet 9 (the new EFX trigger)')
    # the original shared 7-param trigger (inlet 0) must still be fed by hw-bussel, unchanged
    check((bp_id, 0) in outgoing('obj-pv2-hw-bussel', b - 1),
          f'obj-pv2-hw-bussel outlet {b-1} should still feed {bp_id} inlet 0 (7-param trigger, unchanged)')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
