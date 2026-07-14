"""
Builds Roland_SP404MK2_Control-39.maxpat from Control-38. Fixes a hardware
MIDI-dispatch ordering bug reported after real testing: recalling a preset
via incoming Program Change required pressing PC twice for the right
effect to be selected -- the first PC correctly dispatched the dial/CC
values but not the EFX-select, so those values landed on whatever effect
was PREVIOUSLY active on the hardware; only the second PC (which now also
re-sent the already-correct EFX selection alongside the values) produced
the right result. The user's own diagnosis: "EFX select should be sent
first of all for all busses" -- confirmed as the right fix once traced.

ROOT CAUSE (pre-existing since Control-32, NOT introduced by the Control-36
/Control-38 subpatcher passes -- those preserved this exact per-bus
dispatch order unchanged, just relocated the same objects into
subpatchers): the post-recall hardware dispatch loop (obj-pv2-hw-uzi ->
obj-pv2-hw-bussel) iterates bus-by-bus, and for EACH bus dispatches ALL 8
params together (EFX-select bundled in with the 6 CC dials + on/off toggle)
before moving to the next bus. A real effects unit needs its active effect
TYPE selected before per-effect parameter CCs are meaningful -- sending a
dial's CC value before the EFX-select CC lands on whichever effect was
already active, not the one being switched to. Since this loop dispatches
per-bus (not per-parameter-across-all-buses), bus 2's dial values could
arrive appended to bus 1's dispatch block while bus 2's own EFX-select
hasn't been sent yet in a global sense -- but more directly, WITHIN a
single bus's own dispatch, `t`'s fan-out order among independent outlets
is not something this codebase otherwise relies on for correctness, and
here it happened to matter: EFX must land on the hardware before that same
bus's CC dial values, and per the user's own request, for ALL buses before
ANY of the CC dial values across ALL buses (matching how a performer
switching presets live needs the effect selection to be unambiguous before
any parameter tweaks apply).

FIX: split hardware dispatch into two explicit sequential passes across
all 5 buses, using a new, second uzi 5 / select-1-2-3-4-5 loop identical
in shape to the existing one:
  PHASE 1 (NEW): for buses 1-5, set the MIDI channel then dispatch ONLY
    the EFX-select value.
  PHASE 2 (existing hw-uzi/hw-bussel, untouched dispatch logic): for buses
    1-5, set the MIDI channel then dispatch the remaining 7 params
    (6 CC dials + on/off toggle) -- EFX removed from this phase.
Phase 1 is sequenced to run to full completion (all 5 buses) via uzi's own
completion bang before Phase 2 starts, exactly the same "uzi completion
bang, not a naive immediate bang" idiom already used elsewhere in this
codebase for phase sequencing (e.g. obj-pv2-rcl-post-t itself).

Each per-bus subpatcher (obj-pv38-hwshadow-b{N}, from Control-38) gets a
new, dedicated 10th inlet (index 10) wired straight to that bus's EFX int
object's hot inlet, replacing its previous internal trigger-fan connection
(trigger-fan's efx outlet is simply left unwired -- 7 params now share the
existing trigger-fan, EFX has its own path). No other per-bus subpatcher
content changes.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-38.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-39.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

BUSES = [1, 2, 3, 4, 5]

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                 'destination': [dst_id, dst_in]}})

def add_box(box):
    boxes.append({'box': box})

# --- modify each bus's subpatcher: add a dedicated EFX-trigger inlet,
#     detach EFX from the shared 7-param trigger-fan ---
for b in BUSES:
    bp_id = f'obj-pv38-hwshadow-b{b}'
    bp = box_by_id[bp_id]
    assert bp['numinlets'] == 9, f'{bp_id}: expected 9 inlets, got {bp["numinlets"]}'
    sub = bp['patcher']
    sub_boxes = sub['boxes']
    sub_lines = sub['lines']

    before = len(sub_lines)
    sub_lines[:] = [l for l in sub_lines
                     if not (l['patchline']['source'] == ['trigger-fan', 7]
                             and l['patchline']['destination'] == ['int-efx', 0])]
    assert len(sub_lines) == before - 1, f'{bp_id}: expected exactly 1 trigger-fan->int-efx line removed'

    sub_boxes.append({'box': {
        'id': 'in-efx-trigger', 'maxclass': 'inlet', 'numinlets': 0, 'numoutlets': 1,
        'outlettype': [''], 'index': 10, 'comment': 'efx-only hw-dispatch bang (hot)',
        'patching_rect': [400.0, 20.0, 30.0, 30.0],
    }})
    sub_lines.append({'patchline': {'source': ['in-efx-trigger', 0],
                                     'destination': ['int-efx', 0]}})

    bp['numinlets'] = 10

# --- new Phase 1: EFX-only dispatch across all 5 buses, same shape as the
#     existing hw-uzi/hw-t/hw-bussel loop ---
add_box({'id': 'obj-pv39-hw-efx-uzi', 'maxclass': 'newobj', 'text': 'uzi 5',
         'numinlets': 2, 'numoutlets': 3, 'outlettype': ['bang', 'bang', 'int'],
         'patching_rect': [5450.0, 2860.0, 50.0, 22.0]})
add_box({'id': 'obj-pv39-hw-efx-t', 'maxclass': 'newobj', 'text': 't i i',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5450.0, 2900.0, 40.0, 22.0]})
add_box({'id': 'obj-pv39-hw-efx-bussel', 'maxclass': 'newobj', 'text': 'select 1 2 3 4 5',
         'numinlets': 1, 'numoutlets': 6, 'outlettype': ['', '', '', '', '', ''],
         'patching_rect': [5450.0, 2940.0, 140.0, 22.0]})

# obj-pv2-rcl-post-t outlet2 (FIRST, per Control-33's `t b b b` extension)
# used to bang obj-pv2-hw-uzi directly; now it starts the NEW efx-only
# phase first instead
before = len(lines)
lines[:] = [l for l in lines
            if not (l['patchline']['source'] == ['obj-pv2-rcl-post-t', 2]
                    and l['patchline']['destination'] == ['obj-pv2-hw-uzi', 0])]
assert len(lines) == before - 1, 'expected exactly 1 rcl-post-t->hw-uzi line to remove'
add_line('obj-pv2-rcl-post-t', 2, 'obj-pv39-hw-efx-uzi', 0)  # FIRST: start EFX-only phase
add_line('obj-pv39-hw-efx-uzi', 2, 'obj-pv39-hw-efx-t', 0)
add_line('obj-pv39-hw-efx-t', 1, 'obj-15', 0)                # set MIDI channel first
add_line('obj-pv39-hw-efx-t', 0, 'obj-pv39-hw-efx-bussel', 0)  # then bang this bus's EFX trigger
for b in BUSES:
    bp_id = f'obj-pv38-hwshadow-b{b}'
    add_line('obj-pv39-hw-efx-bussel', b - 1, bp_id, 9)  # inlet 9 = the new index-10 efx trigger
# once all 5 buses' EFX has been dispatched, THEN run the existing 7-param phase
add_line('obj-pv39-hw-efx-uzi', 1, 'obj-pv2-hw-uzi', 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
