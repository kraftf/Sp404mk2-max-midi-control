"""
Builds Roland_SP404MK2_Control-41.maxpat from Control-40. Real fix for the
"int: inlet: bang: wrong message int" error (5x per recall) introduced by
Control-39's EFX-first hardware dispatch.

ROOT CAUSE, found via Control-40's diagnostic print taps: a subpatcher's
EXTERNAL inlet order is determined by the `inlet` objects' X-COORDINATE
(patching_rect), NOT by the "index" attribute -- contrary to this
session's earlier assumption (based on a real Max-saved reference file
that, in hindsight, only ever contained a SINGLE inlet, so it couldn't
reveal how MULTIPLE inlets get ordered relative to each other). Control-39
placed the new `in-efx-trigger` inlet at x=400.0, which sorts BETWEEN the
existing cc81 (x=350) and cc82 (x=420) inlets -- shifting the effective
external-inlet mapping for everything after it by one slot:
  - external inlet 7 (intended for cc82's bg value) actually reached
    in-efx-trigger instead -- explains the diagnostic tap showing a float
    like "0." there (cc82's current value), not a bang.
  - external inlet 9 (intended for the new EFX-only trigger bang) actually
    reached in-bg-onoff instead -- a plain inlet whose output feeds
    int-onoff's COLD inlet (int/float only). A bang landing there is
    exactly "int: inlet: bang: wrong message int", once per bus (5 buses
    = 5 identical errors per recall), and explains why EFX was never
    dispatched at all: the bang never reached int-efx's hot inlet.

FIX: move in-efx-trigger's x-coordinate to comfortably exceed every other
inlet in the subpatcher (max existing x was 490 for in-bg-onoff), so it
sorts last regardless of which ordering rule Max actually applies. No
other change needed -- the "index" field and all other wiring were
already correct; only the coordinate-based sort was wrong.

Also removes the two temporary diagnostic print objects added in
Control-40, now that the real cause has been found.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-40.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-41.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

BUSES = [1, 2, 3, 4, 5]

# --- remove Control-40's diagnostic taps ---
before_b = len(boxes)
boxes[:] = [bx for bx in boxes if bx['box']['id'] != 'obj-pv40-dbg-print-efxbussel']
assert len(boxes) == before_b - 1, 'expected to remove exactly 1 outer debug print box'

before_l = len(lines)
lines[:] = [l for l in lines
            if l['patchline']['source'][0] != 'obj-pv39-hw-efx-bussel'
            or l['patchline']['destination'][0] != 'obj-pv40-dbg-print-efxbussel']
assert len(lines) == before_l - 1, 'expected to remove exactly 1 outer debug print line'

bp1 = box_by_id['obj-pv38-hwshadow-b1']
sub1 = bp1['patcher']
before_sb = len(sub1['boxes'])
sub1['boxes'][:] = [sb for sb in sub1['boxes'] if sb['box']['id'] != 'dbg-print-efxtrigger']
assert len(sub1['boxes']) == before_sb - 1, 'expected to remove exactly 1 inner debug print box'
before_sl = len(sub1['lines'])
sub1['lines'][:] = [l for l in sub1['lines']
                     if l['patchline']['destination'] != ['dbg-print-efxtrigger', 0]]
assert len(sub1['lines']) == before_sl - 1, 'expected to remove exactly 1 inner debug print line'

# --- real fix: push in-efx-trigger's x-coordinate past every other inlet ---
for b in BUSES:
    bp = box_by_id[f'obj-pv38-hwshadow-b{b}']
    sub_boxes = {sb['box']['id']: sb['box'] for sb in bp['patcher']['boxes']}
    trig = sub_boxes['in-efx-trigger']
    assert trig['maxclass'] == 'inlet'
    max_x = max(sb['box']['patching_rect'][0] for sb in bp['patcher']['boxes']
                if sb['box']['maxclass'] == 'inlet' and sb['box']['id'] != 'in-efx-trigger')
    trig['patching_rect'] = [max_x + 200.0, trig['patching_rect'][1],
                              trig['patching_rect'][2], trig['patching_rect'][3]]

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
