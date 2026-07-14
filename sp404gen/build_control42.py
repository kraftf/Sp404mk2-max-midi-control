"""
Builds Roland_SP404MK2_Control-42.maxpat from Control-41. DIAGNOSTIC ONLY:
the x-coordinate/inlet-ordering fix in Control-41 eliminated the console
errors, but the user reports the underlying symptom is unchanged -- an
incoming Program Change still needs to be sent twice before the right
effect is selected on the actual hardware, even though bus 1's on-screen
display now shows entirely correct values on the very first press
(confirmed by the user's own console output: dial CC values genuinely
changed between presets on the first press, and EFX's disp-shadow value
also updated).

Since the DISPLAY path (Control-36, unrelated to hardware dispatch) is
confirmed correct, the remaining suspects are specific to the HARDWARE
DISPATCH value pipeline (Control-38/39/41's obj-pv38-hwshadow-b* ->
CTLOUT chain):
  1. A race with pattrstorage's own (asynchronous) restore of the EFX
     pattr client specifically -- if obj-pv2-bg-b1-efx (a live.menu,
     enum-type parameter) settles slower after "recall N" than the
     float-type dial parameters do, hw-dispatch could be reading EFX's
     OLD value even though the dial values it reads at the same moment
     are already fresh.
  2. The physical unit needing genuine processing time after receiving
     the EFX-select CC before it's ready to apply subsequent parameter
     CCs correctly -- Control-41 fixed the ORDER (EFX now dispatches to
     all 5 buses before any dial CC does) but introduced no explicit time
     gap between the two phases, which may not be enough for the
     hardware's own internal effect-switch to complete.

This adds one temporary print tap, directly on obj-pv38-hwshadow-b1's own
EFX outlet (outlet 0) -- the actual value about to be sent to hardware via
ctlout, as opposed to Control-36's on-screen display shadow -- so the
user's next test shows exactly what value hw-dispatch sends and whether it
matches what the display (correctly) shows. If they match, this points to
theory 2 (needs a delay); if hw-dispatch shows a stale/different value,
this points to theory 1 (needs pattrstorage to settle EFX before hw-dispatch
reads it). Delete once the real cause is confirmed.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-41.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-42.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']

def add_box(box):
    boxes.append({'box': box})

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                 'destination': [dst_id, dst_in]}})

add_box({'id': 'obj-pv42-dbg-print-hwefx', 'maxclass': 'newobj',
         'text': 'print HW-DISPATCH-efx-bus1',
         'numinlets': 1, 'numoutlets': 0,
         'patching_rect': [5620.0, 3020.0, 200.0, 22.0]})
add_line('obj-pv38-hwshadow-b1', 0, 'obj-pv42-dbg-print-hwefx', 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
