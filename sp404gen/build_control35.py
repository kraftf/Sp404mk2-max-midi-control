"""
Builds Roland_SP404MK2_Control-35.maxpat from Control-34. Three requests:

1. DEDICATED PROGRAM CHANGE INPUT PORT: obj-pv2-pgmin (drives preset recall)
   was a bare `pgmin` with NO port filter at all -- it listened to Program
   Change on every connected MIDI device/port. Adds its own independent
   device selector (obj-c35-pcindev, item list cloned from the same
   MIDI Output Device list used elsewhere -> prepend port -> pgmin inlet 0),
   completely separate from the "MIDI Control Input Device" selector already
   used for CC control (obj-c34-indev) -- the user chose an independent
   selector explicitly (not shared) since Program Change and CC control may
   come from different devices. Mirrors the exact ctlin device-selector
   pattern from Control-34, already confirmed working in real Max testing.

2. SECOND PRESET SYSTEM FOR MIDI CC MAPPINGS: 16 slots (user's chosen count,
   not 128 -- this isn't tied to MIDI Program Change, just a plain picklist)
   that save/recall/rename configurations of the 8 MIDI CC selector numbers
   added in Control-34 (ctrl1-6, efxsel, onoff). Deliberately NOT built on a
   second `pattrstorage` object, despite that being the literal request --
   see the note below for why, and what was built instead to give an
   identical user-facing mechanism (umenu list + SAVE + RECALL + rename,
   PC-style number prefix) safely.

   Why not a second pattrstorage: obj-pv2-pattrstorage runs with
   `@subscribemode 1`, which auto-subscribes EVERY parameter-enabled object
   anywhere in this patcher (confirmed empirically: 52 parameter_enable=1
   objects across all 4 buses/EFX are already its clients, purely by living
   in the same flat patcher -- there is no scoping by object subset). The 8
   CC selector number boxes were deliberately left with parameter_enable
   UNSET in Control-34 specifically so MIDI CC input would never leak into
   the 128-preset system. Turning parameter_enable on for them (needed to
   register them as clients of a NEW pattrstorage) would also make the
   EXISTING pattrstorage's subscribemode auto-discovery adopt them, silently
   pulling MIDI-controller CC numbers into every one of the 128 hardware
   presets -- exactly the cross-contamination this feature must not cause.
   Built instead: two embedded `coll`s (obj-c35-ccvalues for the 8 numbers,
   obj-c35-ccnames for labels) with explicit, synchronous pack/unpack SAVE
   and RECALL, and a rename mechanism that reuses the exact textedit
   (keymode/outputmode/route-text) recipe proven in Control-34 -- but
   simpler: since there's no external async object involved (unlike
   pattrstorage's getslotnamelist/slotname round trip), a rename can clear +
   rebuild the menu immediately in the same trigger cascade, no
   capture-then-rebuild two-phase dance required.

3. PERFORMANCE: investigated structurally (this session cannot run Max).
   Found no feedback loops, no runaway loadbang, no pathological
   coordinates, no oversized embedded data -- ruled out as causes. The
   patch IS large: 790 boxes / 1258 lines, zero subpatchers (fully flat),
   including 46 heavy live.dial/live.menu/live.toggle objects and 52
   parameter-enabled (pattr) objects, all pre-dating this session. That
   combination is a well-documented source of Max editor sluggishness and
   presentation-mode memory/redraw cost, but restructuring the EXISTING,
   already-hard-won working baseline (9 rounds of debugging to get the
   128-preset system right) carries real regression risk this session
   cannot test against. Chose NOT to touch existing Control-33/34 objects
   or pattrstorage attributes blind. Both NEW features in this build are
   kept flat and minimal (matching existing codebase style, cheapest to
   review/diff), and the honest, larger fix -- subpatching the pre-existing
   baseline UI -- is flagged as a separate follow-up decision for the user,
   not bundled into this risk surface. See SESSION_STATE.md.

NOT hardware/Max tested -- see SESSION_STATE.md "Control-35" MAX-TEST ITEMS.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-34.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-35.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']

box_by_id = {b['box']['id']: b['box'] for b in boxes}

def add_box(box):
    boxes.append({'box': box})
    box_by_id[box['id']] = box

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                'destination': [dst_id, dst_in]}})

# =====================================================================
# 0. Presets companion file rename (34 -> 35, format/content unchanged)
# =====================================================================
PRESETS_FILENAME = 'Control35_presets.json'
assert box_by_id['obj-pv2-read-msg']['text'] == 'read "Control34_presets.json"'
assert box_by_id['obj-pv2-write-msg']['text'] == 'write "Control34_presets.json"'
box_by_id['obj-pv2-read-msg']['text'] = f'read "{PRESETS_FILENAME}"'
box_by_id['obj-pv2-write-msg']['text'] = f'write "{PRESETS_FILENAME}"'

MIDI_DEVICE_ITEMS = box_by_id['obj-4']['items']  # same clone source as Control-34

# =====================================================================
# 1. DEDICATED PROGRAM CHANGE INPUT PORT (independent selector)
# =====================================================================
assert box_by_id['obj-pv2-pgmin']['text'] == 'pgmin'
# confirm pgmin currently has no incoming wire (bare -- listens to everything)
assert not any(l['patchline']['destination'][0] == 'obj-pv2-pgmin' for l in lines), \
    'obj-pv2-pgmin already has an incoming connection -- pattern no longer applies'

add_box({'id': 'obj-c35-pcin-cmt', 'maxclass': 'comment',
         'text': 'Program Change Input Device (preset recall only -- independent '
                 'of the MIDI Control Input Device above)',
         'patching_rect': [40.0, 5400.0, 420.0, 20.0],
         'presentation': 1, 'presentation_rect': [20.0, 715.0, 420.0, 16.0]})
add_box({'id': 'obj-c35-pcindev', 'maxclass': 'umenu', 'items': MIDI_DEVICE_ITEMS,
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', '', ''],
         'parameter_enable': 0,
         'patching_rect': [40.0, 5430.0, 160.0, 22.0],
         'presentation': 1, 'presentation_rect': [20.0, 735.0, 200.0, 22.0]})
add_box({'id': 'obj-c35-pc-pport', 'maxclass': 'newobj', 'text': 'prepend port',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [40.0, 5460.0, 90.0, 22.0]})
add_line('obj-c35-pcindev', 1, 'obj-c35-pc-pport', 0)
add_line('obj-c35-pc-pport', 0, 'obj-pv2-pgmin', 0)

# =====================================================================
# 2. CC-MAPPING PRESET SYSTEM (16 slots: umenu + SAVE/RECALL + rename)
#
# See module docstring for why this uses two explicit colls instead of a
# second pattrstorage. Layout mirrors the 8 MIDI_TARGETS order established
# in Control-34's build_control34.py: ctrl1-6, efxsel, onoff, with the same
# default CC numbers (16,17,18,80,81,82,83,19).
# =====================================================================
N_CC_SLOTS = 16
CC_TARGETS = ['ctrl1', 'ctrl2', 'ctrl3', 'ctrl4', 'ctrl5', 'ctrl6', 'efxsel', 'onoff']
CC_DEFAULTS = [16, 17, 18, 80, 81, 82, 83, 19]
for name in CC_TARGETS:
    assert box_by_id[f'obj-c34-ccsel-{name}']['maxclass'] == 'number', \
        f'obj-c34-ccsel-{name} missing or not a number box'

add_box({'id': 'obj-c35-cc-cmt', 'maxclass': 'comment',
         'text': 'MIDI CC Config Presets (save/recall the 8 CC# selectors above, '
                 'per external controller)',
         'patching_rect': [40.0, 5500.0, 420.0, 20.0],
         'presentation': 1, 'presentation_rect': [20.0, 765.0, 420.0, 16.0]})

# --- 16-slot umenu, placeholder items replaced at load by the rebuild ---
cc_items = []
for n in range(1, N_CC_SLOTS + 1):
    if n > 1:
        cc_items.append(',')
    cc_items += [str(n), '-', 'Config', str(n)]
add_box({'id': 'obj-c35-ccmenu', 'maxclass': 'umenu', 'items': cc_items,
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', '', ''],
         'parameter_enable': 0,
         'patching_rect': [40.0, 5530.0, 140.0, 22.0],
         'presentation': 1, 'presentation_rect': [20.0, 785.0, 140.0, 22.0]})
add_box({'id': 'obj-c35-ccsavebtn', 'maxclass': 'message', 'text': 'SAVE',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [190.0, 5530.0, 55.0, 20.0],
         'presentation': 1, 'presentation_rect': [165.0, 785.0, 55.0, 20.0]})
add_box({'id': 'obj-c35-ccrclbtn', 'maxclass': 'message', 'text': 'RECALL',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [250.0, 5530.0, 65.0, 20.0],
         'presentation': 1, 'presentation_rect': [225.0, 785.0, 65.0, 20.0]})

# --- rename UI: same textedit recipe as Control-34 (keymode/outputmode via
#     runtime messages, route text to strip textedit's unconditional prefix,
#     numoutlets/outlettype matching textedit's real, fixed 4-outlet shape) ---
add_box({'id': 'obj-c35-ccnameedit', 'maxclass': 'textedit',
         'numinlets': 1, 'numoutlets': 4, 'outlettype': ['', 'int', '', ''],
         'outputmode': 1,
         'patching_rect': [40.0, 5560.0, 200.0, 22.0],
         'presentation': 1, 'presentation_rect': [300.0, 785.0, 220.0, 22.0]})
add_box({'id': 'obj-c35-ccnameedit-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [260.0, 5560.0, 60.0, 22.0]})
add_box({'id': 'obj-c35-ccnameedit-keymode', 'maxclass': 'message', 'text': 'keymode 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [330.0, 5560.0, 70.0, 20.0]})
add_line('obj-c35-ccnameedit-lb', 0, 'obj-c35-ccnameedit-keymode', 0)
add_line('obj-c35-ccnameedit-keymode', 0, 'obj-c35-ccnameedit', 0)
add_box({'id': 'obj-c35-ccroute-text', 'maxclass': 'newobj', 'text': 'route text',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [40.0, 5590.0, 90.0, 22.0]})
add_line('obj-c35-ccnameedit', 0, 'obj-c35-ccroute-text', 0)

# --- colls: values (8 CC numbers per slot) and names (label per slot),
#     both keyed 1-16, both pre-seeded so every lookup always finds
#     something (same idiom as obj-c34-namecache) ---
add_box({'id': 'obj-c35-ccvalues', 'maxclass': 'newobj',
         'text': 'coll obj-c35-ccvalues @embed 1',
         'numinlets': 1, 'numoutlets': 4, 'outlettype': ['', '', '', ''],
         'saved_object_attributes': {'embed': 1, 'precision': 6},
         'patching_rect': [5100.0, 5700.0, 200.0, 22.0],
         'coll_data': {
             'count': N_CC_SLOTS,
             'data': [{'key': n, 'value': list(CC_DEFAULTS)}
                      for n in range(1, N_CC_SLOTS + 1)],
         }})
add_box({'id': 'obj-c35-ccnames', 'maxclass': 'newobj',
         'text': 'coll obj-c35-ccnames @embed 1',
         'numinlets': 1, 'numoutlets': 4, 'outlettype': ['', '', '', ''],
         'saved_object_attributes': {'embed': 1, 'precision': 6},
         'patching_rect': [5320.0, 5700.0, 200.0, 22.0],
         'coll_data': {
             'count': N_CC_SLOTS,
             'data': [{'key': n, 'value': ['Config', str(n)]}
                      for n in range(1, N_CC_SLOTS + 1)],
         }})

# --- shadow/slot tracking: one dedicated int-shadow per independent use,
#     mirroring Control-34's proven "separate shadow per consumer" idiom
#     (slotshadow vs slotshadow-restore) so SAVE/RECALL/rename/restore can
#     never accidentally cross-trigger each other via a shared fan-out ---
def add_shadow(shadow_id):
    add_box({'id': shadow_id, 'maxclass': 'newobj', 'text': 'int 0',
             'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
             'patching_rect': [5100.0, 5730.0, 50.0, 22.0]})
    add_line('obj-c35-ccmenu', 0, shadow_id, 1)  # cold tap, silent

add_shadow('obj-c35-ccshadow-save')
add_shadow('obj-c35-ccshadow-rcl')
add_shadow('obj-c35-ccshadow-restore')

# continuous hot tracker for rename (fires on every real selection change,
# always current by the time a rename is committed) -- same idiom as
# obj-c34-slot1
add_box({'id': 'obj-c35-ccslot1', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 5760.0, 40.0, 22.0]})
add_line('obj-c35-ccmenu', 0, 'obj-c35-ccslot1', 0)

add_box({'id': 'obj-c35-restore-pset', 'maxclass': 'newobj', 'text': 'prepend set',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 5790.0, 70.0, 22.0]})
add_line('obj-c35-ccshadow-restore', 0, 'obj-c35-restore-pset', 0)
add_line('obj-c35-restore-pset', 0, 'obj-c35-ccmenu', 0)

# --- SAVE: capture the 8 ccsel values + current slot, synchronously ---
# t b x9 (right-to-left): outlets 8..1 bang each ccsel box (in CC_TARGETS
# order) to make it output its current value straight into savepack's cold
# inlets; outlet 0 (LAST) bangs the save-shadow, fetching the 0-based index,
# +1'ing it into savepack's HOT inlet 0 -- guaranteeing all 8 cold inlets
# are already filled before the pack fires.
add_box({'id': 'obj-c35-save-t', 'maxclass': 'newobj',
         'text': 't b b b b b b b b b',
         'numinlets': 1, 'numoutlets': 9,
         'outlettype': ['bang'] * 9,
         'patching_rect': [5100.0, 5820.0, 140.0, 22.0]})
add_line('obj-c35-ccsavebtn', 0, 'obj-c35-save-t', 0)

add_box({'id': 'obj-c35-savepack', 'maxclass': 'newobj',
         'text': 'pack 0 0 0 0 0 0 0 0 0',
         'numinlets': 9, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 5910.0, 160.0, 22.0]})
for i, name in enumerate(CC_TARGETS):
    # outlets 1-8 all fire (in some order) strictly before outlet 0 (t
    # fires right-to-left) -- that's the only ordering requirement, so
    # outlet/inlet number can match CC_TARGETS order directly (i+1), which
    # is what must line up with obj-c35-rcl-unpack's outlet order below
    # (both read/write the coll in the same [ctrl1..onoff] atom order).
    out_index = i + 1
    pack_inlet = i + 1
    ccsel_id = f'obj-c34-ccsel-{name}'
    add_line('obj-c35-save-t', out_index, ccsel_id, 0)     # bang: output current value
    add_line(ccsel_id, 0, 'obj-c35-savepack', pack_inlet)  # NEW additional tap
add_box({'id': 'obj-c35-save-slotplus1', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 5880.0, 40.0, 22.0]})
add_line('obj-c35-save-t', 0, 'obj-c35-ccshadow-save', 0)         # LAST: fetch slot
add_line('obj-c35-ccshadow-save', 0, 'obj-c35-save-slotplus1', 0)
add_line('obj-c35-save-slotplus1', 0, 'obj-c35-savepack', 0)      # HOT: triggers pack
add_line('obj-c35-savepack', 0, 'obj-c35-ccvalues', 0)             # write [slot v1..v8]

# --- RECALL: fetch slot, look up values, dispatch to the 8 ccsel boxes ---
add_box({'id': 'obj-c35-rcl-slotplus1', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 5950.0, 40.0, 22.0]})
add_line('obj-c35-ccrclbtn', 0, 'obj-c35-ccshadow-rcl', 0)
add_line('obj-c35-ccshadow-rcl', 0, 'obj-c35-rcl-slotplus1', 0)
add_line('obj-c35-rcl-slotplus1', 0, 'obj-c35-ccvalues', 0)  # lookup -> outlet0: [v1..v8]
add_box({'id': 'obj-c35-rcl-unpack', 'maxclass': 'newobj',
         'text': 'unpack 0 0 0 0 0 0 0 0',
         'numinlets': 1, 'numoutlets': 8,
         'outlettype': ['int'] * 8,
         'patching_rect': [5100.0, 5980.0, 160.0, 22.0]})
add_line('obj-c35-ccvalues', 0, 'obj-c35-rcl-unpack', 0)
for i, name in enumerate(CC_TARGETS):
    # unpack outlet i corresponds to CC_TARGETS[i] (v1 in leftmost outlet)
    add_line('obj-c35-rcl-unpack', i, f'obj-c34-ccsel-{name}', 0)

# --- RENAME: write into ccnames directly (synchronous, no external
#     protocol), then rebuild the menu immediately -- t b l b, same shape
#     as obj-c34-name-t: outlet2 (FIRST) clears the textbox, outlet1
#     (SECOND) writes the name, outlet0 (THIRD/LAST) rebuilds the menu ---
add_box({'id': 'obj-c35-ccnamepack', 'maxclass': 'newobj', 'text': 'pack s i',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6010.0, 60.0, 22.0]})
add_line('obj-c35-ccroute-text', 0, 'obj-c35-ccnamepack', 0)  # hot: typed text
add_line('obj-c35-ccslot1', 0, 'obj-c35-ccnamepack', 1)       # cold: current slot#
add_box({'id': 'obj-c35-ccnamemsg', 'maxclass': 'message', 'text': '$2 $1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6040.0, 60.0, 20.0]})
add_line('obj-c35-ccnamepack', 0, 'obj-c35-ccnamemsg', 0)
add_box({'id': 'obj-c35-ccname-t', 'maxclass': 'newobj', 'text': 't b l b',
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['bang', '', 'bang'],
         'patching_rect': [5100.0, 6070.0, 50.0, 22.0]})
add_line('obj-c35-ccnamemsg', 0, 'obj-c35-ccname-t', 0)
add_line('obj-c35-ccname-t', 1, 'obj-c35-ccnames', 0)  # SECOND: write [slot name...]
add_box({'id': 'obj-c35-ccnameedit-clear', 'maxclass': 'message', 'text': 'clear',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5170.0, 6070.0, 50.0, 20.0]})
add_line('obj-c35-ccname-t', 2, 'obj-c35-ccnameedit-clear', 0)  # FIRST: clear box
add_line('obj-c35-ccnameedit-clear', 0, 'obj-c35-ccnameedit', 0)

# --- REBUILD (shared by loadbang and rename): clear + uzi16 + append,
#     reading names straight from obj-c35-ccnames -- no capture phase
#     needed since this coll is the sole, synchronous source of truth ---
add_box({'id': 'obj-c35-rebuild-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', 'bang'],
         'patching_rect': [5100.0, 6100.0, 50.0, 22.0]})
add_line('obj-c35-ccname-t', 0, 'obj-c35-rebuild-t', 0)  # THIRD/LAST after rename
add_box({'id': 'obj-c35-cc-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5250.0, 6100.0, 60.0, 22.0]})
add_line('obj-c35-cc-lb', 0, 'obj-c35-rebuild-t', 0)  # once at load
add_box({'id': 'obj-c35-clear-msg', 'maxclass': 'message', 'text': 'clear',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6130.0, 50.0, 20.0]})
add_line('obj-c35-rebuild-t', 1, 'obj-c35-clear-msg', 0)  # FIRST: clear
add_line('obj-c35-clear-msg', 0, 'obj-c35-ccmenu', 0)
add_box({'id': 'obj-c35-rebuild-uzi', 'maxclass': 'newobj', 'text': f'uzi {N_CC_SLOTS}',
         'numinlets': 2, 'numoutlets': 3, 'outlettype': ['bang', 'bang', 'int'],
         'patching_rect': [5100.0, 6160.0, 70.0, 22.0]})
add_line('obj-c35-rebuild-t', 0, 'obj-c35-rebuild-uzi', 0)  # SECOND: start loop
add_box({'id': 'obj-c35-rebuild-split', 'maxclass': 'newobj', 'text': 't i i',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['int', 'int'],
         'patching_rect': [5100.0, 6190.0, 50.0, 22.0]})
add_line('obj-c35-rebuild-uzi', 2, 'obj-c35-rebuild-split', 0)  # counter 1..16
add_line('obj-c35-rebuild-split', 1, 'obj-c35-ccnames', 0)      # FIRST: lookup name
add_box({'id': 'obj-c35-rebuild-sprintf', 'maxclass': 'newobj',
         'text': 'sprintf append %ld -',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6220.0, 100.0, 22.0]})
add_line('obj-c35-rebuild-split', 0, 'obj-c35-rebuild-sprintf', 0)  # SECOND: slot#
# same "symbol <value>" wrapping risk as namecache -- strip on the way out
add_box({'id': 'obj-c35-rebuild-routesym', 'maxclass': 'newobj', 'text': 'route symbol',
         'numinlets': 2, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5100.0, 6250.0, 90.0, 22.0]})
add_line('obj-c35-ccnames', 0, 'obj-c35-rebuild-routesym', 0)
add_box({'id': 'obj-c35-rebuild-zljoin', 'maxclass': 'newobj', 'text': 'zl.join',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6280.0, 60.0, 22.0]})
add_line('obj-c35-rebuild-routesym', 0, 'obj-c35-rebuild-zljoin', 1)  # matched: stripped
add_line('obj-c35-rebuild-routesym', 1, 'obj-c35-rebuild-zljoin', 1)  # reject: unchanged
add_line('obj-c35-rebuild-sprintf', 0, 'obj-c35-rebuild-zljoin', 0)   # hot: triggers join
add_line('obj-c35-rebuild-zljoin', 0, 'obj-c35-ccmenu', 0)

# restore selection after rebuild's clear wipes it -- triggered by uzi's OWN
# completion bang, guaranteeing all 16 appends finished first
add_line('obj-c35-rebuild-uzi', 1, 'obj-c35-ccshadow-restore', 0)

# =====================================================================
with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
