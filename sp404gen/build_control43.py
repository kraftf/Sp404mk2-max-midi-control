"""
Builds Roland_SP404MK2_Control-43.maxpat from Control-42. Real fix for the
"needs two Program Changes to select the right effect" bug.

ROOT CAUSE, confirmed by the user's Control-42 console output: hardware
dispatch's read of obj-pv2-bg-b1-efx lagged the on-screen display by
exactly one recall -- "HW-DISPATCH-efx-bus1" printed the PREVIOUS
preset's value while "Bus1-efx" (display, read later in the same
post-recall sequence) already showed the new, correct one. pattrstorage
restores its client objects on recall ASYNCHRONOUSLY (confirmed via
Cycling '74's own docs and forum reports of the same class of bug), and
the existing single `deferlow` between "recall N" and the post-recall
sequence is not consistently enough time for it to finish -- a real,
documented Max quirk, not something specific to this patch. (A Cycling
'74 forum thread hit the identical symptom and reported that replacing a
`deferlow` with an explicit `delay 500` in the same spot fixed it --
matches this fix.)

FIX: insert `pipe 500` (not `delay`, which cancels/restarts on a second
trigger before its window elapses -- `pipe` queues each triggering event
independently, safer if presets are switched again quickly) between
obj-pv2-rcl-post-t outlet 2 (the hardware-dispatch trigger) and
obj-pv39-hw-efx-uzi, giving pattrstorage's asynchronous restore a real
500ms window to finish before ANY hardware dispatch (EFX or the 7-param
phase, which is chained off EFX's own completion) reads the recalled
values. Both phases already only care about relative order between
themselves and each other, not absolute latency, so a uniform delay
in front of the whole sequence is safe -- and covers dial/toggle
parameters too in case they carry the same latent race, even though the
user has not reported it for those specifically.

Also removes the Control-42 diagnostic print now that the cause is found.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-42.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-43.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

def add_box(box):
    boxes.append({'box': box})

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                 'destination': [dst_id, dst_in]}})

# --- remove Control-42's diagnostic tap ---
before_b = len(boxes)
boxes[:] = [bx for bx in boxes if bx['box']['id'] != 'obj-pv42-dbg-print-hwefx']
assert len(boxes) == before_b - 1, 'expected to remove exactly 1 debug print box'
before_l = len(lines)
lines[:] = [l for l in lines
            if l['patchline']['source'][0] != 'obj-pv38-hwshadow-b1'
            or l['patchline']['destination'][0] != 'obj-pv42-dbg-print-hwefx']
assert len(lines) == before_l - 1, 'expected to remove exactly 1 debug print line'

# --- real fix: pipe 500 between the post-recall trigger and hw-dispatch ---
before_l2 = len(lines)
lines[:] = [l for l in lines
            if not (l['patchline']['source'] == ['obj-pv2-rcl-post-t', 2]
                    and l['patchline']['destination'] == ['obj-pv39-hw-efx-uzi', 0])]
assert len(lines) == before_l2 - 1, 'expected exactly 1 rcl-post-t->efx-uzi line to remove'

add_box({'id': 'obj-pv43-hwdispatch-pipe', 'maxclass': 'newobj', 'text': 'pipe 500',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5450.0, 2830.0, 70.0, 22.0]})
add_line('obj-pv2-rcl-post-t', 2, 'obj-pv43-hwdispatch-pipe', 0)
add_line('obj-pv43-hwdispatch-pipe', 0, 'obj-pv39-hw-efx-uzi', 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
