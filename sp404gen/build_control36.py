"""
Builds Roland_SP404MK2_Control-36.maxpat from Control-35. PILOT for reducing
the patch's overall box count by grouping repeated per-bus structures into
subpatchers, per the user's request ("the size is very big... group things
that get repeated... maybe try bpatchers").

SCOPE OF THIS PILOT (deliberately narrow -- see SESSION_STATE.md for the
full risk analysis): only the "display-shadow int" cluster is converted --
40 boxes (obj-pv2-sh-{param}-{b}, 8 params x 5 buses), the single biggest
repeated cluster that carries ZERO pattr/parameter risk. Each one is a
plain `int 0` fed by a continuous cold tap from its bus's pattr client
(obj-pv2-bg-b{b}-{param}) and a hot bang from that param's bus-select fan
(obj-pv2-sel-{param}), outputting to the visible control (or, for 'efx',
to obj-pv2-rps-efx + obj-pv2-efx-mfan) whenever that bus is the one being
displayed. Plain patch-cord semantics throughout, no pattr binding
involved -- the safest possible first target to prove the mechanism.

NOT touched in this pass, on purpose:
  - obj-pv2-bg-b{b}-{param} (the 40 actual pattr clients): parameter_enable=1
    objects whose pattrstorage @subscribemode 1 auto-discovery is the
    entire, hard-won (9 rounds of debugging) 128-preset system. Whether
    that auto-discovery still finds pattr clients nested inside a
    subpatcher is a real, untested unknown -- deliberately deferred until
    this lower-risk pilot is confirmed working in real Max.
  - obj-pv2-hwh-{param}-{b} (the 40 hardware-dispatch shadow ints): same
    plain-int structure as the display shadows and equally safe to convert,
    but left alone for this pilot to keep the diff small and reviewable.

WHY PLAIN SUBPATCHERS ("p ..."), NOT bpatcher: bpatcher's whole reason to
exist is showing a live embedded UI inside the parent view. Nothing in
this cluster has any visible UI -- it's pure hidden data-shuffling -- so a
plain subpatcher gives the identical box-count reduction with a simpler,
lower-risk JSON shape (content embedded directly in the box via a nested
"patcher" key, no separate file, no bpatcher-specific name/args wiring).

JSON SCHEMA VERIFIED AGAINST A REAL MAX-SAVED FILE (not guessed): the
sp404mk2_2.0_BusFX_v6.amxd reference file (this session's earlier upload)
contains real `p 127 to 100` subpatcher boxes, confirming (a) subpatcher
content nests directly under the box as a "patcher" key with the same
fileversion/appversion/classnamespace/boxes/lines shape as the top level,
and (b) `inlet`/`outlet` objects carry an explicit 1-based "index" field
that determines their numbered position on the containing box -- NOT
inferred from x-coordinate position, which was the original (riskier)
assumption before checking.

Per-bus subpatcher content (16 inlets, 8 outlets, in ALL_PARAMS order):
  inlet 2i   (index i*2+1) = bg_id[param] value, continuous (cold tap)
  inlet 2i+1 (index i*2+2) = sel_id[param] bus-select bang (hot tap)
  int 0, wired: inlet(2i) -> cold inlet 1, inlet(2i+1) -> hot inlet 0
  outlet i   (index i+1)   = int 0's output
Main patch keeps every existing external wire's semantics, just re-pointed
at the new subpatcher box's corresponding inlet/outlet instead of the
removed obj-pv2-sh-{param}-{b} object directly.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-35.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-36.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
APPVERSION = p['appversion']

BUSES = [1, 2, 3, 4, 5]
DIAL_PARAMS = ['cc16', 'cc17', 'cc18', 'cc80', 'cc81', 'cc82']
ALL_PARAMS = ['efx'] + DIAL_PARAMS + ['onoff']
VISIBLE = {
    'efx':   'obj-18',
    'cc16':  'obj-458', 'cc17': 'obj-466', 'cc18': 'obj-474',
    'cc80':  'obj-482', 'cc81': 'obj-490', 'cc82': 'obj-498',
    'onoff': 'obj-454',
}

box_by_id = {b['box']['id']: b['box'] for b in boxes}
for param in ALL_PARAMS:
    assert f'obj-pv2-sel-{param}' in box_by_id, f'obj-pv2-sel-{param} missing'
for b in BUSES:
    for param in ALL_PARAMS:
        assert f'obj-pv2-sh-{param}-{b}' in box_by_id, f'obj-pv2-sh-{param}-{b} missing'
        assert f'obj-pv2-bg-b{b}-{param}' in box_by_id, f'obj-pv2-bg-b{b}-{param} missing'

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                 'destination': [dst_id, dst_in]}})

removed_boxes = 0
removed_lines = 0

for b in BUSES:
    sh_ids = {param: f'obj-pv2-sh-{param}-{b}' for param in ALL_PARAMS}
    sh_id_set = set(sh_ids.values())

    before_b = len(boxes)
    boxes[:] = [bx for bx in boxes if bx['box']['id'] not in sh_id_set]
    removed_boxes += before_b - len(boxes)

    before_l = len(lines)
    lines[:] = [l for l in lines
                if l['patchline']['source'][0] not in sh_id_set
                and l['patchline']['destination'][0] not in sh_id_set]
    removed_lines += before_l - len(lines)

    # ---- build the subpatcher content ----
    sub_boxes = []
    sub_lines = []
    def sadd_box(bx):
        sub_boxes.append({'box': bx})
    def sadd_line(src_id, src_out, dst_id, dst_in):
        sub_lines.append({'patchline': {'source': [src_id, src_out],
                                         'destination': [dst_id, dst_in]}})

    for i, param in enumerate(ALL_PARAMS):
        in_bg = f'in-bg-{param}'
        in_sel = f'in-sel-{param}'
        int_id = f'int-{param}'
        out_id = f'out-{param}'
        sadd_box({'id': in_bg, 'maxclass': 'inlet', 'numinlets': 0, 'numoutlets': 1,
                  'outlettype': [''], 'index': 2 * i + 1, 'comment': f'{param} bg value (cold)',
                  'patching_rect': [i * 70.0, 20.0, 30.0, 30.0]})
        sadd_box({'id': in_sel, 'maxclass': 'inlet', 'numinlets': 0, 'numoutlets': 1,
                  'outlettype': [''], 'index': 2 * i + 2, 'comment': f'{param} bus-select bang (hot)',
                  'patching_rect': [i * 70.0 + 35.0, 20.0, 30.0, 30.0]})
        sadd_box({'id': int_id, 'maxclass': 'newobj', 'text': 'int 0',
                  'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
                  'patching_rect': [i * 70.0, 80.0, 40.0, 22.0]})
        sadd_box({'id': out_id, 'maxclass': 'outlet', 'numinlets': 1, 'numoutlets': 0,
                  'index': i + 1, 'comment': f'{param} display value',
                  'patching_rect': [i * 70.0, 140.0, 30.0, 30.0]})
        sadd_line(in_bg, 0, int_id, 1)   # cold: store only
        sadd_line(in_sel, 0, int_id, 0)  # hot: re-output on bus-select bang
        sadd_line(int_id, 0, out_id, 0)

    sub_patcher = {
        'fileversion': 1,
        'appversion': APPVERSION,
        'classnamespace': 'box',
        'rect': [100.0, 100.0, 700.0, 220.0],
        'bglocked': 0,
        'openinpresentation': 0,
        'default_fontsize': 12.0,
        'default_fontface': 0,
        'default_fontname': 'Arial',
        'gridonopen': 1,
        'gridsize': [15.0, 15.0],
        'gridsnaponopen': 1,
        'objectsnaponopen': 1,
        'statusbarvisible': 2,
        'toolbarvisible': 1,
        'lefttoolbarpinned': 0,
        'toptoolbarpinned': 0,
        'righttoolbarpinned': 0,
        'bottomtoolbarpinned': 0,
        'toolbars_unpinned_last_save': 0,
        'tallnewobj': 0,
        'boxanimatetime': 200,
        'enablehscroll': 1,
        'enablevscroll': 1,
        'devicewidth': 0.0,
        'description': '',
        'digest': '',
        'tags': '',
        'style': '',
        'subpatcher_template': '',
        'assistshowspatchername': 0,
        'boxes': sub_boxes,
        'lines': sub_lines,
    }

    bp_id = f'obj-pv36-dispshadow-b{b}'
    boxes.append({'box': {
        'id': bp_id, 'maxclass': 'newobj',
        'text': f'p Bus{b}DisplayShadow',
        'numinlets': 16, 'numoutlets': 8,
        'outlettype': [''] * 8,
        'patching_rect': [40.0, 6400.0 + (b - 1) * 30.0, 500.0, 22.0],
        'patcher': sub_patcher,
    }})

    for i, param in enumerate(ALL_PARAMS):
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        sel_id = f'obj-pv2-sel-{param}'
        bi = b - 1
        add_line(bg_id, 0, bp_id, 2 * i)        # cold: same continuous tap as before
        add_line(sel_id, bi, bp_id, 2 * i + 1)  # hot: same per-bus select outlet as before
        if param == 'efx':
            add_line(bp_id, i, 'obj-pv2-rps-efx', 0)
            add_line(bp_id, i, 'obj-pv2-efx-mfan', 0)
        else:
            add_line(bp_id, i, VISIBLE[param], 0)

# --- debug aid for real-Max testing: print every one of Bus1's subpatcher
#     outlets to the Max console, labeled per param, so switching to bus 1
#     and watching the console directly confirms values are flowing through
#     the new subpatcher correctly, instead of having to trust it blind.
#     (Per the user's own feedback on the CC-preset bug: a visible readout
#     during testing beats several rounds of "still not working".) Delete
#     these 8 objects once the pilot is confirmed working. ---
DEBUG_BUS = 1
bp1_id = f'obj-pv36-dispshadow-b{DEBUG_BUS}'
for i, param in enumerate(ALL_PARAMS):
    pr_id = f'obj-pv36-dbg-print-{param}'
    boxes.append({'box': {
        'id': pr_id, 'maxclass': 'newobj', 'text': f'print Bus{DEBUG_BUS}-{param}',
        'numinlets': 1, 'numoutlets': 0,
        'patching_rect': [560.0, 6400.0 + i * 25.0, 160.0, 22.0],
    }})
    add_line(bp1_id, i, pr_id, 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines '
      f'(removed {removed_boxes} boxes / {removed_lines} lines, '
      f'added 5 subpatchers)')
