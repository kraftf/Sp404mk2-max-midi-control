"""
Builds Roland_SP404MK2_Control-32.maxpat from Control-31 by replacing the
hand-rolled coll-based preset system (obj-psys-*, 49 objects) with a
pattrstorage/pattrforward-based one, following the mechanism validated in
SP404_preset_TEST_v16.maxpat, scaled from the prototype's 7 params/bus
(35 bg objects) to the real patch's 8 params/bus (40 bg objects: 6 CC
dials + 1 effect-select menu + 1 on/off toggle).

Key departures from the v16 prototype (justified by tracing the real patch --
see SESSION_STATE.md "Control-32" entry for the full reasoning):
  1. 8 params/bus, not 7 (v16 never covered the bus on/off toggle, CC19).
  2. Display refresh for the 6 CC dials + toggle feeds a REAL (audible) value
     into their hot inlet 0, not a silent 'set' -- this matches what the
     existing psys system already does (SESSION_STATE lesson: bare int to
     live.dial hot inlet stores AND outputs), and is what makes the downstream
     enum/SYNC display pipeline (expr $i2*1000+$i1 -> gate -> coll) recompute.
  3. The effect-select menu (obj-18, a plain umenu, not live.menu) gets a
     SILENT 'set $1' (avoids a spurious CC83 resend) PLUS an explicit
     broadcast into the 5 per-bus EFX gates' inlet 1 (mirroring the deleted
     obj-psys-mfan) -- required because 'set' alone does not fire umenu's
     outlet, and the enum-mode derivation pipeline only re-derives when
     obj-18's outlet fires.
  4. Recall ordering (effect-select must apply before CC values) is achieved
     via explicit trigger sequencing (t objects, right-to-left firing),
     the same technique the original system used -- NOT via a pattrstorage
     "priority" attribute, since that attribute's existence/behavior on
     live.* parameter objects could not be verified without Max.
  5. Hardware dispatch on recall (send all 5 buses' stored state to the
     real unit over MIDI, bypassing the UI) has no v16 analogue at all
     (the prototype has no MIDI). It reuses the per-bus-per-param shadow
     ints already needed for display refresh: after `recall N`, bang all
     40 shadows (grouped by bus, driving obj-15's channel per bus) into
     the existing ctlout objects -- same bypass-the-UI approach as the
     deleted obj-psys-unhw/ithw/x127.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-31.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-32.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']

PSYS_PREFIX = 'obj-psys-'
def is_psys(bid):
    return bid.startswith(PSYS_PREFIX)

# ---- strip the old preset system ----
new_boxes = [b for b in boxes if not is_psys(b['box']['id'])]
new_lines = [l for l in lines
             if not is_psys(l['patchline']['source'][0])
             and not is_psys(l['patchline']['destination'][0])]

def add_box(box):
    new_boxes.append({'box': box})

def add_line(src_id, src_out, dst_id, dst_in):
    new_lines.append({'patchline': {'source': [src_id, src_out],
                                     'destination': [dst_id, dst_in]}})

BUSES = [1, 2, 3, 4, 5]
DIAL_PARAMS = ['cc16', 'cc17', 'cc18', 'cc80', 'cc81', 'cc82']
ALL_PARAMS = ['efx'] + DIAL_PARAMS + ['onoff']

VISIBLE = {
    'efx':   'obj-18',
    'cc16':  'obj-458', 'cc17': 'obj-466', 'cc18': 'obj-474',
    'cc80':  'obj-482', 'cc81': 'obj-490', 'cc82': 'obj-498',
    'onoff': 'obj-454',
}
CTLOUT = {
    'efx':   'obj-30',
    'cc16':  'obj-459', 'cc17': 'obj-467', 'cc18': 'obj-475',
    'cc80':  'obj-483', 'cc81': 'obj-491', 'cc82': 'obj-499',
    'onoff': 'obj-456',
}
# bus -> gate object whose inlet 1 needs the re-derived effect index
BUS_GATE = {1: 'obj-509', 2: 'obj-547', 3: 'obj-585', 4: 'obj-623', 5: 'obj-c3135'}
# mfan outlet order replicated from the deleted obj-psys-mfan (out4->bus1 .. out0->bus5)
MFAN_OUTLET_FOR_BUS = {1: 4, 2: 3, 3: 2, 4: 1, 5: 0}

# =====================================================================
# 1. Orientation comments
# =====================================================================
add_box({'id': 'obj-pv2-cmt-main', 'maxclass': 'comment',
         'text': 'PRESET SYSTEM v2 (pattrstorage/pattrforward, replaces psys-*). '
                 'See SESSION_STATE.md "Control-32" for design notes.',
         'patching_rect': [40.0, 3120.0, 700.0, 20.0]})
add_box({'id': 'obj-pv2-cmt-bg', 'maxclass': 'comment',
         'text': '40 hidden pattr client objects (8 params x 5 buses) -- never shown, only their index/value matters',
         'patching_rect': [40.0, 3160.0, 700.0, 20.0]})

# =====================================================================
# 2. 40 bg client objects (hidden, parked below all visible content)
# =====================================================================
GENERIC_EFX_ITEMS = [f'E{i}' for i in range(50)]  # placeholder text; only index is ever read

for bi, b in enumerate(BUSES):
    for pi, param in enumerate(ALL_PARAMS):
        bid = f'obj-pv2-bg-b{b}-{param}'
        varname = f'Bus{b}_{param}'
        x = 40.0 + pi * 150.0
        y = 3200.0 + bi * 60.0
        if param == 'efx':
            add_box({
                'id': bid, 'maxclass': 'live.menu', 'varname': varname,
                'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', 'float'],
                'parameter_enable': 1, 'items': GENERIC_EFX_ITEMS,
                'patching_rect': [x, y, 120.0, 22.0],
                'saved_attribute_attributes': {'valueof': {
                    'parameter_longname': varname, 'parameter_shortname': varname,
                    'parameter_type': 2, 'parameter_enum': GENERIC_EFX_ITEMS,
                    'parameter_initial': [0.0]}},
            })
        elif param == 'onoff':
            add_box({
                'id': bid, 'maxclass': 'live.toggle', 'varname': varname,
                'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
                'parameter_enable': 1,
                'patching_rect': [x, y, 24.0, 24.0],
                'saved_attribute_attributes': {'valueof': {
                    'parameter_longname': varname, 'parameter_shortname': varname,
                    'parameter_type': 2, 'parameter_enum': ['off', 'on'],
                    'parameter_mmax': 1, 'parameter_initial': [0.0]}},
            })
        else:
            add_box({
                'id': bid, 'maxclass': 'live.dial', 'varname': varname,
                'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', 'float'],
                'parameter_enable': 1,
                'patching_rect': [x, y, 44.0, 48.0],
                'saved_attribute_attributes': {'valueof': {
                    'parameter_longname': varname, 'parameter_shortname': varname,
                    'parameter_type': 0, 'parameter_mmin': 0.0, 'parameter_mmax': 127.0,
                    'parameter_unitstyle': 0, 'parameter_initial': [0.0]}},
            })

# =====================================================================
# 3. pattrstorage + autopattr + subscribe + explicit file persistence
#
#    pattrstorage does NOT embed its data in the .maxpat the way
#    `coll @embed 1` does (confirmed against Max's own docs) -- it always
#    persists to a companion JSON/XML file. @savemode 1 (the first attempt)
#    only prompts to save that file on patcher close, and @autorestore 0
#    (copied from the v16 prototype, which only cared about not sending
#    MIDI on load) also disabled the mechanism that reloads it -- so
#    nothing came back after a real close/reopen.
#
#    Fix: pin an explicit, fixed filename via `read`/`write` messages
#    (Max's own docs: the patcher's own folder is searched by default for
#    a bare filename, so no absolute path needed) instead of relying on
#    savemode's prompt-on-close or autorestore's default name-guessing.
#    @savemode 0 (no prompt) since persistence is now handled explicitly;
#    @autorestore 1 left at its default, harmless alongside the explicit
#    read below. write fires right after every SAVE-button store (section
#    7), so preset data hits disk immediately, not on patcher close.
# =====================================================================
PRESETS_FILENAME = 'Control32_presets.json'

add_box({'id': 'obj-pv2-pattrstorage', 'maxclass': 'newobj',
         'text': 'pattrstorage presets @savemode 0 @autorestore 1 @subscribemode 1',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [800.0, 3160.0, 350.0, 22.0]})
add_box({'id': 'obj-pv2-autopattr', 'maxclass': 'newobj', 'text': 'autopattr',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [800.0, 3200.0, 80.0, 22.0]})
add_box({'id': 'obj-pv2-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [800.0, 3240.0, 60.0, 22.0]})
add_box({'id': 'obj-pv2-lb-defer', 'maxclass': 'newobj', 'text': 'deferlow',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [800.0, 3270.0, 60.0, 22.0]})
subscribe_names = [f'Bus{b}_{param}' for b in BUSES for param in ALL_PARAMS]
add_box({'id': 'obj-pv2-sub-msg', 'maxclass': 'message',
         'text': 'subscribe ' + ' '.join(subscribe_names),
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [800.0, 3300.0, 700.0, 20.0]})
add_box({'id': 'obj-pv2-storagewin-msg', 'maxclass': 'message', 'text': 'storagewindow',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [1550.0, 3300.0, 90.0, 20.0]})
add_box({'id': 'obj-pv2-load-defer2', 'maxclass': 'newobj', 'text': 'deferlow',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [800.0, 3330.0, 60.0, 22.0]})
add_box({'id': 'obj-pv2-read-msg', 'maxclass': 'message', 'text': f'read "{PRESETS_FILENAME}"',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [800.0, 3360.0, 200.0, 20.0]})

add_line('obj-pv2-lb', 0, 'obj-pv2-lb-defer', 0)
add_line('obj-pv2-lb-defer', 0, 'obj-pv2-sub-msg', 0)
add_line('obj-pv2-sub-msg', 0, 'obj-pv2-pattrstorage', 0)
add_line('obj-pv2-storagewin-msg', 0, 'obj-pv2-pattrstorage', 0)
# read fires AFTER subscribe (deferred a tick) so pattrstorage's client
# list is fully registered before loading data for those clients
add_line('obj-pv2-sub-msg', 0, 'obj-pv2-load-defer2', 0)
add_line('obj-pv2-load-defer2', 0, 'obj-pv2-read-msg', 0)
add_line('obj-pv2-read-msg', 0, 'obj-pv2-pattrstorage', 0)

# =====================================================================
# 4. Bus-switch retargeting (hangs off the real obj-12 bus-select umenu,
#    alongside its existing obj-19/obj-506-series item-rebuild wiring,
#    which is untouched)
# =====================================================================
add_box({'id': 'obj-pv2-busadd', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [40.0, 3400.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-busN', 'maxclass': 'newobj', 'text': 'int 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [40.0, 3430.0, 40.0, 22.0]})
add_line('obj-12', 0, 'obj-pv2-busadd', 0)
add_line('obj-pv2-busadd', 0, 'obj-pv2-busN', 0)

for pi, param in enumerate(ALL_PARAMS):
    sp_id = f'obj-pv2-sp-{param}'
    pf_id = f'obj-pv2-pf-{param}'
    x = 100.0 + pi * 160.0
    add_box({'id': sp_id, 'maxclass': 'newobj', 'text': f'sprintf send Bus%d_{param}',
             'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
             'patching_rect': [x, 3400.0, 140.0, 22.0]})
    add_box({'id': pf_id, 'maxclass': 'newobj', 'text': f'pattrforward Bus1_{param}',
             'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
             'patching_rect': [x, 3430.0, 140.0, 22.0]})
    add_line('obj-pv2-busadd', 0, sp_id, 0)
    add_line(sp_id, 0, pf_id, 0)
    add_line(VISIBLE[param], 0, pf_id, 0)

# =====================================================================
# 5. Per-bus-per-param DISPLAY shadow ints + select fan (drives display
#    refresh only -- a separate set of "hw-holder" ints for hardware
#    dispatch is built in section 7, to avoid a non-viewed bus's recalled
#    value leaking into the visible controls when hw-dispatch reads it)
# =====================================================================
for pi, param in enumerate(ALL_PARAMS):
    sel_id = f'obj-pv2-sel-{param}'
    x = 100.0 + pi * 160.0
    add_box({'id': sel_id, 'maxclass': 'newobj', 'text': 'select 1 2 3 4 5',
             'numinlets': 1, 'numoutlets': 6, 'outlettype': ['', '', '', '', '', ''],
             'patching_rect': [x, 3460.0, 140.0, 22.0]})
    add_line('obj-pv2-busN', 0, sel_id, 0)
    for bi, b in enumerate(BUSES):
        sh_id = f'obj-pv2-sh-{param}-{b}'
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        add_box({'id': sh_id, 'maxclass': 'newobj', 'text': 'int 0',
                 'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
                 'patching_rect': [x, 3500.0 + bi * 30.0, 40.0, 22.0]})
        add_line(bg_id, 0, sh_id, 1)           # continuous tap -> COLD inlet: store only,
                                                # no output (hot inlet would echo straight
                                                # back into the visible control on every
                                                # live edit / every bus during recall)
        add_line(sel_id, bi, sh_id, 0)         # bang -> HOT inlet: re-output stored value,
                                                # only on the deliberate refresh trigger

# =====================================================================
# 6. Visible-control refresh wiring
#    - 6 CC dials + toggle: real (audible) value straight into hot inlet 0,
#      matching what the deleted psys-unres did.
#    - efx: silent 'set $1' to obj-18 PLUS broadcast into the 5 EFX gates'
#      inlet 1 (replicates the deleted obj-psys-mfan), since 'set' alone
#      does not fire umenu's outlet and the enum-mode pipeline needs that
#      outlet to re-derive display text.
# =====================================================================
for param in DIAL_PARAMS + ['onoff']:
    for b in BUSES:
        add_line(f'obj-pv2-sh-{param}-{b}', 0, VISIBLE[param], 0)

add_box({'id': 'obj-pv2-rps-efx', 'maxclass': 'newobj', 'text': 'prepend set',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [100.0, 3700.0, 80.0, 22.0]})
add_box({'id': 'obj-pv2-efx-mfan', 'maxclass': 'newobj', 'text': 't i i i i i i',
         'numinlets': 1, 'numoutlets': 6, 'outlettype': ['', '', '', '', '', ''],
         'patching_rect': [100.0, 3740.0, 200.0, 22.0]})
add_line('obj-pv2-rps-efx', 0, 'obj-18', 0)
for b in BUSES:
    add_line(f'obj-pv2-sh-efx-{b}', 0, 'obj-pv2-rps-efx', 0)
    add_line(f'obj-pv2-sh-efx-{b}', 0, 'obj-pv2-efx-mfan', 0)
for b in BUSES:
    add_line('obj-pv2-efx-mfan', MFAN_OUTLET_FOR_BUS[b], BUS_GATE[b], 1)

# =====================================================================
# 7. SAVE / RECALL UI (replaces obj-psys-menu/save-msg/rcl-msg and all
#    the pak/unpack/key-arithmetic machinery -- pattrstorage's own
#    store/recall take a plain slot number, no key math needed)
# =====================================================================
PRESET_ITEMS = []
for i in range(1, 9):
    if i > 1:
        PRESET_ITEMS.append(',')
    PRESET_ITEMS.extend(['Preset', str(i)])

add_box({'id': 'obj-pv2-cmt-presets', 'maxclass': 'comment',
         'text': 'Presets: all 5 bus states. Incoming PC 0-7 = recall 1-8',
         'patching_rect': [5100.0, 2670.0, 350.0, 19.0], 'presentation': 1,
         'presentation_rect': [750.0, 90.0, 340.0, 19.0]})
add_box({'id': 'obj-pv2-slotmenu', 'maxclass': 'umenu', 'items': PRESET_ITEMS,
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', '', ''],
         'patching_rect': [5100.0, 2700.0, 100.0, 22.0], 'presentation': 1,
         'presentation_rect': [750.0, 110.0, 100.0, 22.0]})
add_box({'id': 'obj-pv2-savebtn', 'maxclass': 'message', 'text': 'SAVE',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 2740.0, 50.0, 20.0], 'presentation': 1,
         'presentation_rect': [860.0, 110.0, 55.0, 20.0]})
add_box({'id': 'obj-pv2-rclbtn', 'maxclass': 'message', 'text': 'RECALL',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5160.0, 2740.0, 60.0, 20.0], 'presentation': 1,
         'presentation_rect': [922.0, 110.0, 65.0, 20.0]})

add_box({'id': 'obj-pv2-save-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5100.0, 2780.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-slot1-store', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 2800.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-pre-store', 'maxclass': 'newobj', 'text': 'prepend store',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 2820.0, 90.0, 22.0]})
add_box({'id': 'obj-pv2-store-msg', 'maxclass': 'message', 'text': 'store',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5220.0, 2820.0, 50.0, 20.0]})
add_line('obj-pv2-savebtn', 0, 'obj-pv2-save-t', 0)
add_line('obj-pv2-save-t', 1, 'obj-pv2-slotmenu', 0)
add_line('obj-pv2-save-t', 0, 'obj-pv2-store-msg', 0)
# slotmenu is a umenu: 0-indexed ("Preset 1" outputs 0). +1 here converts to the
# 1-based slot number pattrstorage's store/recall expect -- the original psys
# system did the same conversion (curpre -> +1) before its own key math.
add_line('obj-pv2-slotmenu', 0, 'obj-pv2-slot1-store', 0)
add_line('obj-pv2-slot1-store', 0, 'obj-pv2-pre-store', 0)
add_line('obj-pv2-pre-store', 0, 'obj-pv2-store-msg', 1)
add_line('obj-pv2-store-msg', 0, 'obj-pv2-pattrstorage', 0)

# write to disk immediately after every store (deferred a tick so the
# store itself finishes first) -- persistence no longer depends on the
# user remembering to save/close, or on a prompt they might dismiss
add_box({'id': 'obj-pv2-save-defer', 'maxclass': 'newobj', 'text': 'deferlow',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5220.0, 2860.0, 60.0, 22.0]})
add_box({'id': 'obj-pv2-write-msg', 'maxclass': 'message', 'text': f'write "{PRESETS_FILENAME}"',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5220.0, 2900.0, 200.0, 20.0]})
add_line('obj-pv2-store-msg', 0, 'obj-pv2-save-defer', 0)
add_line('obj-pv2-save-defer', 0, 'obj-pv2-write-msg', 0)
add_line('obj-pv2-write-msg', 0, 'obj-pv2-pattrstorage', 0)

add_box({'id': 'obj-pv2-rcl-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5300.0, 2780.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-slot1-rcl', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 2800.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-pre-rcl', 'maxclass': 'newobj', 'text': 'prepend recall',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 2820.0, 90.0, 22.0]})
add_box({'id': 'obj-pv2-rcl-msg', 'maxclass': 'message', 'text': 'recall',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5420.0, 2820.0, 55.0, 20.0]})
add_line('obj-pv2-rclbtn', 0, 'obj-pv2-rcl-t', 0)
add_line('obj-pv2-rcl-t', 1, 'obj-pv2-slotmenu', 0)
add_line('obj-pv2-rcl-t', 0, 'obj-pv2-rcl-msg', 0)
add_line('obj-pv2-slotmenu', 0, 'obj-pv2-slot1-rcl', 0)
add_line('obj-pv2-slot1-rcl', 0, 'obj-pv2-pre-rcl', 0)
add_line('obj-pv2-pre-rcl', 0, 'obj-pv2-rcl-msg', 1)
add_line('obj-pv2-rcl-msg', 0, 'obj-pv2-pattrstorage', 0)

# ---- post-recall sequencing: hw-dispatch MUST complete before the final
#      display refresh, so the display refresh is the authoritative last
#      word for whichever bus is currently on screen (mirrors the deleted
#      psys-rcl-t's own order: hw-dispatch at out2, UI-restore at out0,
#      i.e. hw dispatch strictly before UI refresh) ----
add_box({'id': 'obj-pv2-rcl-defer', 'maxclass': 'newobj', 'text': 'deferlow',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5300.0, 2860.0, 60.0, 22.0]})
add_box({'id': 'obj-pv2-rcl-post-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5300.0, 2900.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-rcl-trig', 'maxclass': 'newobj', 'text': 't b',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 2940.0, 30.0, 22.0]})
add_line('obj-pv2-pattrstorage', 0, 'obj-pv2-rcl-defer', 0)
add_line('obj-pv2-rcl-defer', 0, 'obj-pv2-rcl-post-t', 0)
add_line('obj-pv2-rcl-post-t', 0, 'obj-pv2-rcl-trig', 0)   # outlet0 fires LAST: display refresh
add_line('obj-pv2-rcl-trig', 0, 'obj-pv2-busN', 0)  # bang re-outputs current bus, no bus change

# ---- hardware dispatch: send all 5 buses' recalled state to the real
#      unit, bypassing the UI (same approach as the deleted psys-unhw).
#      Uses a SEPARATE set of 40 "hw-holder" ints (not the display shadow
#      ints from section 5) so dispatching a non-viewed bus can never
#      leak into the currently-displayed dial/menu/toggle.
#      uzi 5's outlet 2 is the 1-indexed loop count (1..5) -- confirmed
#      against the deleted psys-uzhw's own wiring (fed obj-15 with no +1),
#      so bus channel numbers line up directly, no extra arithmetic. ----
for param in ALL_PARAMS:
    for b in BUSES:
        hwh_id = f'obj-pv2-hwh-{param}-{b}'
        bg_id = f'obj-pv2-bg-b{b}-{param}'
        add_box({'id': hwh_id, 'maxclass': 'newobj', 'text': 'int 0',
                 'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
                 'patching_rect': [5450.0, 3060.0, 40.0, 22.0]})
        add_line(bg_id, 0, hwh_id, 1)   # COLD inlet: store only. hwh_id's outlet 0 feeds
                                        # straight into a ctlout -- a hot-inlet tap here
                                        # would fire a spurious MIDI send on every live
                                        # edit, on whatever channel obj-15 last held.

add_box({'id': 'obj-pv2-hw-uzi', 'maxclass': 'newobj', 'text': 'uzi 5',
         'numinlets': 2, 'numoutlets': 3, 'outlettype': ['bang', 'bang', 'int'],
         'patching_rect': [5450.0, 2900.0, 50.0, 22.0]})
add_box({'id': 'obj-pv2-hw-t', 'maxclass': 'newobj', 'text': 't i i',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5450.0, 2940.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-hw-bussel', 'maxclass': 'newobj', 'text': 'select 1 2 3 4 5',
         'numinlets': 1, 'numoutlets': 6, 'outlettype': ['', '', '', '', '', ''],
         'patching_rect': [5450.0, 2980.0, 140.0, 22.0]})
add_line('obj-pv2-rcl-post-t', 1, 'obj-pv2-hw-uzi', 0)   # outlet1 fires FIRST: hw dispatch
add_line('obj-pv2-hw-uzi', 2, 'obj-pv2-hw-t', 0)
add_line('obj-pv2-hw-t', 1, 'obj-15', 0)          # set MIDI channel first (fires first)
add_line('obj-pv2-hw-t', 0, 'obj-pv2-hw-bussel', 0)  # then bang this bus's holders (fires second)

for b in BUSES:
    for param in ALL_PARAMS:
        hwh_id = f'obj-pv2-hwh-{param}-{b}'
        if param == 'onoff':
            scale_id = f'obj-pv2-hwscale-{param}-{b}'
            add_box({'id': scale_id, 'maxclass': 'newobj', 'text': '* 127',
                     'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
                     'patching_rect': [5620.0, 3060.0, 50.0, 22.0]})
            add_line('obj-pv2-hw-bussel', b - 1, hwh_id, 0)
            add_line(hwh_id, 0, scale_id, 0)
            add_line(scale_id, 0, CTLOUT[param], 0)
        else:
            add_line('obj-pv2-hw-bussel', b - 1, hwh_id, 0)
            add_line(hwh_id, 0, CTLOUT[param], 0)

# =====================================================================
# 8. Program Change 0-7 -> recall preset 1-8
# =====================================================================
add_box({'id': 'obj-pv2-pgmin', 'maxclass': 'newobj', 'text': 'pgmin',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5600.0, 2670.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-pgsplit', 'maxclass': 'newobj', 'text': 'split 0 7',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5600.0, 2700.0, 60.0, 22.0]})
add_box({'id': 'obj-pv2-pgt', 'maxclass': 'newobj', 'text': 't i i',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5600.0, 2730.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-pgset', 'maxclass': 'message', 'text': 'set $1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5600.0, 2770.0, 55.0, 20.0]})
add_box({'id': 'obj-pv2-pgadd', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5670.0, 2770.0, 40.0, 22.0]})
add_box({'id': 'obj-pv2-pgrcl', 'maxclass': 'newobj', 'text': 'prepend recall',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5670.0, 2800.0, 90.0, 22.0]})
add_line('obj-pv2-pgmin', 0, 'obj-pv2-pgsplit', 0)
add_line('obj-pv2-pgsplit', 0, 'obj-pv2-pgt', 0)
# pgt fans out the RAW 0-7 PC value: outlet1 sets slotmenu's display directly
# (umenu is 0-indexed, so PC=0 correctly shows/selects "Preset 1" at index 0);
# outlet0 gets +1 before reaching pattrstorage, since store/recall need the
# 1-based slot number, not the 0-based menu index (same distinction as the
# SAVE/RECALL button path above -- this was the earlier bug: applying +1
# before the split meant BOTH branches got the wrong value for their purpose).
add_line('obj-pv2-pgt', 1, 'obj-pv2-pgset', 0)
add_line('obj-pv2-pgset', 0, 'obj-pv2-slotmenu', 0)
add_line('obj-pv2-pgt', 0, 'obj-pv2-pgadd', 0)
add_line('obj-pv2-pgadd', 0, 'obj-pv2-pgrcl', 0)
add_line('obj-pv2-pgrcl', 0, 'obj-pv2-pattrstorage', 0)

# =====================================================================
p['boxes'] = new_boxes
p['lines'] = new_lines

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(new_boxes)} boxes, {len(new_lines)} lines')
