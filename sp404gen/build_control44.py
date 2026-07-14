"""
Builds Roland_SP404MK2_Control-44.maxpat from Control-43. Fixes a real
regression introduced by Control-43's own fix, reported after testing:
recalling bus 1 left the MIDI channel stuck on 5, and EFX stopped being
sent to hardware at all.

ROOT CAUSE: Control-43 inserted `pipe 500` directly between the
hardware-dispatch trigger (obj-pv2-rcl-post-t outlet 2) and the EFX-only
dispatch phase, delaying ONLY hardware dispatch by 500ms. But
obj-pv2-rcl-post-t's OTHER outlet (outlet 0, LAST -- the display refresh)
fires immediately, undelayed, as before. This inverts the relative timing
the whole design depended on: hardware dispatch loops obj-15 (the MIDI
channel) through 1..5 while sending each bus's state, and Control-33's own
fix (`obj-pv33-busN-t`) specifically relies on the display refresh running
AFTER hardware dispatch to restore obj-15 back to whichever bus is
currently on screen. With hardware dispatch now delayed 500ms behind
display refresh instead of running before it, display refresh's own
restoration fires and passes long before hardware dispatch even starts --
so by the time hardware dispatch finally loops through channels 1-5, its
own left-over channel (5, the last bus processed) is the last word,
permanently, until the next recall. (Root cause of EFX specifically not
sending at all was not independently isolated -- likely a downstream
consequence of channel 5 being wrong for whatever the user was checking;
this fix restores the ordering invariant either way and should be
retested.)

FIX: move the delay to sit in front of the ENTIRE post-recall sequence
instead of just the hardware-dispatch branch, so hardware dispatch and
display refresh are delayed BY THE SAME AMOUNT and their relative order
(hardware dispatch, then display refresh, per Control-33's own documented
requirement) is preserved exactly as before -- only the absolute start
time of the whole sequence moves later, giving pattrstorage's
asynchronous restore the same 500ms head start either way. Concretely:
obj-pv43-hwdispatch-pipe (Control-43's now-misplaced delay) is removed and
its direct wiring restored; a new `pipe 500` is inserted between
obj-pv2-rcl-defer and obj-pv2-rcl-post-t instead, so `rcl-post-t` itself
(and therefore ALL of its outlets together) fires 500ms later, not just
one of its branches.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-43.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-44.maxpat')

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

# --- undo Control-43's misplaced pipe: remove it and restore direct wiring ---
before_b = len(boxes)
boxes[:] = [bx for bx in boxes if bx['box']['id'] != 'obj-pv43-hwdispatch-pipe']
assert len(boxes) == before_b - 1, 'expected to remove exactly 1 box (obj-pv43-hwdispatch-pipe)'

before_l = len(lines)
lines[:] = [l for l in lines
            if l['patchline']['source'][0] != 'obj-pv2-rcl-post-t'
            or l['patchline']['destination'] != ['obj-pv43-hwdispatch-pipe', 0]]
lines[:] = [l for l in lines
            if l['patchline']['source'] != ['obj-pv43-hwdispatch-pipe', 0]]
assert len(lines) == before_l - 2, 'expected to remove exactly 2 lines (both sides of the old pipe)'

add_line('obj-pv2-rcl-post-t', 2, 'obj-pv39-hw-efx-uzi', 0)  # restored: direct, undelayed

# --- real fix: delay the WHOLE post-recall sequence uniformly, in front
#     of rcl-post-t, so hw-dispatch and display-refresh stay in their
#     original relative order (hw-dispatch first, display-refresh last) ---
before_l2 = len(lines)
lines[:] = [l for l in lines
            if not (l['patchline']['source'] == ['obj-pv2-rcl-defer', 0]
                    and l['patchline']['destination'] == ['obj-pv2-rcl-post-t', 0])]
assert len(lines) == before_l2 - 1, 'expected exactly 1 rcl-defer->rcl-post-t line to remove'

add_box({'id': 'obj-pv44-postrecall-pipe', 'maxclass': 'newobj', 'text': 'pipe 500',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 2880.0, 70.0, 22.0]})
add_line('obj-pv2-rcl-defer', 0, 'obj-pv44-postrecall-pipe', 0)
add_line('obj-pv44-postrecall-pipe', 0, 'obj-pv2-rcl-post-t', 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
