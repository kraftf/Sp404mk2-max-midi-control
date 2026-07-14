"""
Builds Roland_SP404MK2_Control-40.maxpat from Control-39. DIAGNOSTIC ONLY:
adds two `print` taps to pin down the exact cause of the "int: inlet: bang:
wrong message int" error the user is seeing 5 times per recall (once per
bus) since Control-39's EFX-first hardware dispatch fix.

The new EFX-only dispatch phase (obj-pv39-hw-efx-uzi/-t/-bussel) mirrors
the already-proven obj-pv2-hw-uzi/-t/-bussel pattern object-for-object
(identical text/inlets/outlets/outlettype, confirmed by direct comparison),
and the per-bus subpatcher's new dedicated EFX-trigger inlet (index 10,
wired straight to that bus's int-efx hot inlet) was re-verified against
the actual committed JSON to carry no stray connections. Both re-checks
came back clean, so rather than guess again blind, these two taps will
show exactly what message is arriving where:
  1. obj-pv40-dbg-print-efxbussel: taps obj-pv39-hw-efx-bussel's outlet 0
     (bus 1's match) directly in the main patch -- confirms what `select`
     is actually sending out (expected: bare bang).
  2. obj-pv40-dbg-print-efxtrigger: a `print` object added INSIDE bus 1's
     hw-shadow subpatcher, tapping in-efx-trigger's own output before it
     reaches int-efx -- confirms what actually arrives at that inlet from
     inside the subpatcher's perspective (should be identical to #1, but
     confirms nothing is transformed/misrouted crossing the subpatcher
     boundary).
Delete both once the real cause is found.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-39.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-40.maxpat')

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

# --- tap 1: obj-pv39-hw-efx-bussel outlet 0 (bus 1), in the main patch ---
add_box({'id': 'obj-pv40-dbg-print-efxbussel', 'maxclass': 'newobj',
         'text': 'print EFX-BUSSEL-bus1',
         'numinlets': 1, 'numoutlets': 0,
         'patching_rect': [5620.0, 2980.0, 180.0, 22.0]})
add_line('obj-pv39-hw-efx-bussel', 0, 'obj-pv40-dbg-print-efxbussel', 0)

# --- tap 2: in-efx-trigger's own output, inside bus 1's hw-shadow subpatcher ---
bp1 = box_by_id['obj-pv38-hwshadow-b1']
sub = bp1['patcher']
sub['boxes'].append({'box': {
    'id': 'dbg-print-efxtrigger', 'maxclass': 'newobj', 'text': 'print EFX-TRIGGER-inside-b1',
    'numinlets': 1, 'numoutlets': 0,
    'patching_rect': [400.0, 180.0, 180.0, 22.0],
}})
sub['lines'].append({'patchline': {'source': ['in-efx-trigger', 0],
                                    'destination': ['dbg-print-efxtrigger', 0]}})

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
