"""
Builds Roland_SP404MK2_Control-38.maxpat from Control-37. Second pass of
the subpatcher-ization started in Control-36 (see that build script's
docstring for the full risk analysis and why this is being done
incrementally): converts the hardware-dispatch shadow cluster
(obj-pv2-hwh-{param}-{b}, 40 boxes) into 5 per-bus subpatchers, the same
safe pattern already confirmed working in real Max for the display-shadow
cluster. Same reasoning applies here: plain `int 0` objects wired with
ordinary patch cords, zero pattr/parameter_enable involvement, so this
carries the same low risk as the already-confirmed Control-36 pilot.

Structural difference from the display-shadow cluster: there, each of the
8 params had its OWN per-param "select" trigger (obj-pv2-sel-{param}, one
outlet per bus). Here, the hot trigger (obj-pv2-hw-bussel, `select 1 2 3
4 5`) is a SINGLE shared object -- its outlet for bus b fires to all 8 of
that bus's hwh objects at once. So each per-bus subpatcher needs only 9
inlets (8 for the continuous bg-value cold taps, 1 shared hot-trigger
bang, fanned out internally to all 8), not 16, and 8 outlets (one raw
value per param -- the *127 scale for 'onoff' and the final CTLOUT wiring
both stay outside, unchanged, exactly as they did for the display-shadow
cluster's VISIBLE-control wiring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-37.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-38.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
APPVERSION = p['appversion']

BUSES = [1, 2, 3, 4, 5]
DIAL_PARAMS = ['cc16', 'cc17', 'cc18', 'cc80', 'cc81', 'cc82']
ALL_PARAMS = ['efx'] + DIAL_PARAMS + ['onoff']
CTLOUT = {
    'efx':   'obj-30',
    'cc16':  'obj-459', 'cc17': 'obj-467', 'cc18': 'obj-475',
    'cc80':  'obj-483', 'cc81': 'obj-491', 'cc82': 'obj-499',
    'onoff': 'obj-456',
}

box_by_id = {b['box']['id']: b['box'] for b in boxes}
for b in BUSES:
    for param in ALL_PARAMS:
        assert f'obj-pv2-hwh-{param}-{b}' in box_by_id, f'obj-pv2-hwh-{param}-{b} missing'
assert box_by_id['obj-pv2-hw-bussel']['text'] == 'select 1 2 3 4 5'

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                 'destination': [dst_id, dst_in]}})

removed_boxes = 0
removed_lines = 0

for b in BUSES:
    hwh_ids = {param: f'obj-pv2-hwh-{param}-{b}' for param in ALL_PARAMS}
    hwh_id_set = set(hwh_ids.values())

    before_b = len(boxes)
    boxes[:] = [bx for bx in boxes if bx['box']['id'] not in hwh_id_set]
    removed_boxes += before_b - len(boxes)

    before_l = len(lines)
    lines[:] = [l for l in lines
                if l['patchline']['source'][0] not in hwh_id_set
                and l['patchline']['destination'][0] not in hwh_id_set]
    removed_lines += before_l - len(lines)

    # ---- build the subpatcher content ----
    sub_boxes = []
    sub_lines = []
    def sadd_box(bx):
        sub_boxes.append({'box': bx})
    def sadd_line(src_id, src_out, dst_id, dst_in):
        sub_lines.append({'patchline': {'source': [src_id, src_out],
                                         'destination': [dst_id, dst_in]}})

    # shared hot-trigger inlet (index 1, i.e. the FIRST inlet on the box --
    # placed first so the bg-value inlets occupy 2..9, matching outlet 1..8
    # position-for-position with ALL_PARAMS order)
    in_trigger = 'in-trigger'
    sadd_box({'id': in_trigger, 'maxclass': 'inlet', 'numinlets': 0, 'numoutlets': 1,
              'outlettype': [''], 'index': 1, 'comment': 'hw-bussel bang (shared, hot)',
              'patching_rect': [0.0, 20.0, 30.0, 30.0]})
    fan_id = 'trigger-fan'
    sadd_box({'id': fan_id, 'maxclass': 'newobj', 'text': 't b b b b b b b b',
              'numinlets': 1, 'numoutlets': 8, 'outlettype': ['bang'] * 8,
              'patching_rect': [0.0, 60.0, 300.0, 22.0]})
    sadd_line(in_trigger, 0, fan_id, 0)

    for i, param in enumerate(ALL_PARAMS):
        in_bg = f'in-bg-{param}'
        int_id = f'int-{param}'
        out_id = f'out-{param}'
        sadd_box({'id': in_bg, 'maxclass': 'inlet', 'numinlets': 0, 'numoutlets': 1,
                  'outlettype': [''], 'index': i + 2, 'comment': f'{param} bg value (cold)',
                  'patching_rect': [i * 70.0, 20.0, 30.0, 30.0]})
        sadd_box({'id': int_id, 'maxclass': 'newobj', 'text': 'int 0',
                  'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
                  'patching_rect': [i * 70.0, 100.0, 40.0, 22.0]})
        sadd_box({'id': out_id, 'maxclass': 'outlet', 'numinlets': 1, 'numoutlets': 0,
                  'index': i + 1, 'comment': f'{param} hw-dispatch value',
                  'patching_rect': [i * 70.0, 140.0, 30.0, 30.0]})
        # fan-out outlet order is the same left-to-right ALL_PARAMS order as
        # the outer boxes below, so t's own right-to-left firing order among
        # these 8 independent (non-interacting) writes doesn't matter
        sadd_line(fan_id, 7 - i, int_id, 0)   # hot: re-output on hw-dispatch bang
        sadd_line(in_bg, 0, int_id, 1)        # cold: store only
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

    bp_id = f'obj-pv38-hwshadow-b{b}'
    boxes.append({'box': {
        'id': bp_id, 'maxclass': 'newobj',
        'text': f'p Bus{b}HwShadow',
        'numinlets': 9, 'numoutlets': 8,
        'outlettype': [''] * 8,
        'patching_rect': [40.0, 6600.0 + (b - 1) * 30.0, 500.0, 22.0],
        'patcher': sub_patcher,
    }})

    bi = b - 1
    add_line('obj-pv2-hw-bussel', bi, bp_id, 0)  # shared hot trigger, same outlet as before
    for i, param in enumerate(ALL_PARAMS):
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        add_line(bg_id, 0, bp_id, i + 1)  # cold: same continuous tap as before
        if param == 'onoff':
            scale_id = f'obj-pv2-hwscale-{param}-{b}'
            add_line(bp_id, i, scale_id, 0)
        else:
            add_line(bp_id, i, CTLOUT[param], 0)

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines '
      f'(removed {removed_boxes} boxes / {removed_lines} lines, '
      f'added 5 subpatchers)')
