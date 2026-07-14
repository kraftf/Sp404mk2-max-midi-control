"""
Validates Roland_SP404MK2_Control-41.maxpat: the real fix for the EFX
hardware-dispatch bug (inlet ordering is x-coordinate based, not
index-based -- see build_control41.py's module docstring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-41.maxpat')

with open(PATCH) as f:
    data = json.load(f)
boxes = data['patcher']['boxes']
lines = data['patcher']['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)

BUSES = [1, 2, 3, 4, 5]

check('obj-pv40-dbg-print-efxbussel' not in box_by_id,
      'outer debug print should have been removed')

for b in BUSES:
    bp_id = f'obj-pv38-hwshadow-b{b}'
    bp = box_by_id[bp_id]
    sub_boxes = [sb['box'] for sb in bp['patcher']['boxes']]
    check('dbg-print-efxtrigger' not in [sb['id'] for sb in sub_boxes],
          f'{bp_id}: inner debug print should have been removed')

    inlets = [sb for sb in sub_boxes if sb['maxclass'] == 'inlet']
    check(len(inlets) == 10, f'{bp_id}: expected 10 inlet objects, got {len(inlets)}')
    # sorting by x-coordinate must match sorting by declared index --
    # this is the actual invariant Max relies on (confirmed the hard way)
    by_x = sorted(inlets, key=lambda sb: sb['patching_rect'][0])
    by_index = sorted(inlets, key=lambda sb: sb['index'])
    check([sb['id'] for sb in by_x] == [sb['id'] for sb in by_index],
          f'{bp_id}: inlet x-coordinate order does not match index order -- '
          f'x-order={[sb["id"] for sb in by_x]}, index-order={[sb["id"] for sb in by_index]}')

    trig = next(sb for sb in inlets if sb['id'] == 'in-efx-trigger')
    max_other_x = max(sb['patching_rect'][0] for sb in inlets if sb['id'] != 'in-efx-trigger')
    check(trig['patching_rect'][0] > max_other_x,
          f'{bp_id}: in-efx-trigger x ({trig["patching_rect"][0]}) should exceed '
          f'every other inlet x ({max_other_x})')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
