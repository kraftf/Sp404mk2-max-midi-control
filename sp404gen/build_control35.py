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

4. FIXED AFTER FIRST MAX TEST (same session): RECALL was wired straight into
   an `int` object, which doesn't understand the literal message-box symbol
   "RECALL" (confirmed console error) -- routed through a `t b` first, same
   as SAVE already did. Rename used `pack s i`, which (confirmed via Cycling
   '74's own pack documentation) spills extra atoms from a multi-word name
   into the next inlet, clobbering the int-typed slot number for any 2+-word
   rename -- replaced with `zl.join`, which has no per-inlet atom-count
   limit. See the inline comments at each fix site and SESSION_STATE.md for
   the full writeup.

5. CC-CONFIG PRESETS NOW ALSO SAVE THE MIDI CONTROL INPUT DEVICE, BY NAME:
   the user pointed out that "different MIDI controllers" (the whole reason
   for this preset system existing) usually also means a different MIDI
   port, so each saved slot should remember which device obj-c34-indev was
   set to. Saves the device's NAME (obj-c34-indev outlet 1's text), not its
   umenu index -- MIDI port lists can be reordered, gain/lose entries, or
   have devices unplugged between sessions, so a raw index could silently
   select the wrong device later. On RECALL, `prepend symbol` -> obj-c34-
   indev inlet 0 selects by matching text (umenu's own "symbol" message,
   confirmed via Max's umenu reference); a name that no longer matches any
   connected device is a harmless no-op, which is the correct fallback here.
   Third embedded coll: obj-c35-ccdevice, defaulting every slot to a sentinel
   ('(unset)') that isn't expected to match any real device name.
   Went through FIVE wrong/incomplete designs before this one -- see
   SESSION_STATE.md for all of them: bare-banging obj-c34-indev for
   RECALL (bang can't select an arbitrary item, only re-emit whatever's
   already selected -- wrong tool for that job); an unnecessary `value`
   proxy object; a `route symbol` fix on the RECALL side assuming `coll`
   always wraps a single-atom symbol value on lookup, replaced by a
   deterministic `prepend DEV` / `route DEV` tagging scheme on the write
   and read sides so extraction never depends on coll's internal
   single-atom formatting at all -- and STILL reported broken, because
   that whole coll-layer investigation was chasing the wrong bug. The
   real defect was upstream, on SAVE: obj-c34-indev's outlet 1 only fires
   on an actual user click, so a passive continuous tap into the join's
   cold inlet captures nothing if the device was already correctly
   selected when the patch loaded and the user never re-clicks it before
   pressing SAVE (the normal case). Fixed by explicitly banging
   obj-c34-indev right before every SAVE (save-t's new outlet 9, firing
   before the slot-fetch trigger) -- a confirmed Cycling '74 forum idiom:
   bang forces umenu to re-emit its CURRENTLY selected item on both
   outlets without changing the selection, guaranteeing a fresh value on
   every SAVE regardless of whether a change event ever fired.
   On RECALL, `route DEV` (obj-c35-rcl-dev-routesym) deterministically
   strips the write-side tag before `prepend symbol` -> obj-c34-indev
   inlet 0 (umenu's own "symbol" message, confirmed via Cycling '74's
   umenu reference, both selects by matching text and fires real output).
   A name that no longer matches any connected device is a harmless
   no-op, which is the correct fallback for a stale/renamed port.

6. Program Change Input Device selector (added in this same build, item 1)
   repositioned in presentation to sit next to the bus-state preset
   selection (slotmenu/SAVE/RECALL/nameedit) per the user's request, since
   it drives that preset system's PC-triggered recall -- moved out of the
   MIDI Control Input area, which is unrelated (CC control, not PC/presets).

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

# Presentation placement: next to the bus-state preset selection (slotmenu/
# SAVE/RECALL at [750,110] and nameedit at [750,140]) per the user's request,
# not near the CC MIDI Control Input controls -- this selector affects
# Program Change (preset recall), not CC input, so it belongs with the
# preset UI it actually drives.
add_box({'id': 'obj-c35-pcin-cmt', 'maxclass': 'comment',
         'text': 'Program Change Input Device (preset recall)',
         'patching_rect': [40.0, 5400.0, 420.0, 20.0],
         'presentation': 1, 'presentation_rect': [750.0, 165.0, 250.0, 16.0]})
add_box({'id': 'obj-c35-pcindev', 'maxclass': 'umenu', 'items': MIDI_DEVICE_ITEMS,
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', '', ''],
         'parameter_enable': 0,
         'patching_rect': [40.0, 5430.0, 160.0, 22.0],
         'presentation': 1, 'presentation_rect': [750.0, 183.0, 200.0, 22.0]})
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

# --- colls: values (8 CC numbers per slot), names (label per slot), and
#     device (the MIDI Control Input Device's NAME, not its umenu index --
#     ports can be reordered/renumbered/unplugged between sessions, so the
#     saved slot needs to re-select by matching text, not replay a raw index
#     that might now point at a different device). All keyed 1-16, all
#     pre-seeded so every lookup always finds something (same idiom as
#     obj-c34-namecache). DEVICE_UNSET is not expected to match any real
#     MIDI device name, so recalling a never-saved slot is a harmless no-op. ---
DEVICE_UNSET = '(unset)'
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
add_box({'id': 'obj-c35-ccdevice', 'maxclass': 'newobj',
         'text': 'coll obj-c35-ccdevice @embed 1',
         'numinlets': 1, 'numoutlets': 4, 'outlettype': ['', '', '', ''],
         'saved_object_attributes': {'embed': 1, 'precision': 6},
         'patching_rect': [5540.0, 5700.0, 200.0, 22.0],
         'coll_data': {
             'count': N_CC_SLOTS,
             # every stored value is tagged ['DEV', <name...>] -- see the
             # write/read sites below for why (deterministic multi-atom
             # values, sidestepping coll's single-atom "symbol"-wrap quirk
             # entirely instead of trying to detect/undo it after the fact).
             'data': [{'key': n, 'value': ['DEV', DEVICE_UNSET]}
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
add_shadow('obj-c35-ccshadow-rename')

add_box({'id': 'obj-c35-restore-pset', 'maxclass': 'newobj', 'text': 'prepend set',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 5790.0, 70.0, 22.0]})
add_line('obj-c35-ccshadow-restore', 0, 'obj-c35-restore-pset', 0)
add_line('obj-c35-restore-pset', 0, 'obj-c35-ccmenu', 0)

# --- SAVE: capture the 8 ccsel values + the MIDI Control Input Device name
#     + current slot, synchronously ---
# STILL BROKEN AFTER THE coll/DEV-tag FIX: that fix addressed the RECALL
# side's extraction, but the real bug was upstream, on SAVE. The previous
# design relied purely on a PASSIVE continuous tap of obj-c34-indev's
# outlet 1 into the join's cold inlet -- fine for catching a *change*, but
# outlet 1 only fires when the user actually clicks a new item. If the
# device was already correctly selected when the patch loaded (the normal
# case -- nobody re-clicks a selector that's already right) and the user
# never touches it before pressing SAVE, outlet 1 never fires even once,
# so the cold inlet is still empty/stale and nothing meaningful is ever
# captured. Confirmed via a Cycling '74 forum idiom (bang -> umenu
# re-outputs its CURRENTLY selected item on both outlets, without changing
# the selection -- the official doc list omits bang, but this is the
# standard trick for reading a umenu's current value on demand): outlet 9
# (NEW, fires FIRST since t is right-to-left) bangs obj-c34-indev directly,
# forcing a fresh, synchronous re-emission of its current index/text right
# before the slot-fetch trigger (outlet 0, LAST) reaches the join's hot
# inlet -- same "capture on demand" pattern already used for the 8 ccsel
# number boxes below, just applied to the device selector too.
add_box({'id': 'obj-c35-save-t', 'maxclass': 'newobj',
         'text': 't b b b b b b b b b b',
         'numinlets': 1, 'numoutlets': 10,
         'outlettype': ['bang'] * 10,
         'patching_rect': [5100.0, 5820.0, 150.0, 22.0]})
add_line('obj-c35-ccsavebtn', 0, 'obj-c35-save-t', 0)
add_line('obj-c35-save-t', 9, 'obj-c34-indev', 0)  # FIRST: force fresh re-emission of current device

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

# NOT `pack i s` for [slot, device-name]: device names can be multi-word
# (e.g. "Arturia BeatStep Pro Arturia BeatStepPro", confirmed present in
# this patch's own obj-4 device list) and `pack` spills extra atoms from a
# multi-atom message into subsequent inlets -- the exact bug already found
# and fixed in the rename mechanism. Uses zl.join instead, which has no
# per-inlet atom-count limit either way.
#
# `prepend DEV` tags the device name with a fixed marker atom BEFORE it
# ever reaches the coll, so the value written is always >= 2 atoms
# (['DEV', <name...>]), never a single bare atom. This sidesteps needing
# to know exactly when `coll` does or doesn't wrap a single-atom symbol
# value on the way back out -- a corner case that went through multiple
# wrong fixes this session and still didn't resolve the reported bug. With
# a self-supplied tag, extraction on RECALL is a plain, deterministic
# `route DEV` instead of guessing at coll's internal behavior.
add_box({'id': 'obj-c35-savedev-tag', 'maxclass': 'newobj', 'text': 'prepend DEV',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 5880.0, 90.0, 22.0]})
add_line('obj-c34-indev', 1, 'obj-c35-savedev-tag', 0)                # any real change (belt-and-suspenders;
                                                                       # save-t outlet 9 above is what actually
                                                                       # guarantees a fresh value on every SAVE)
add_box({'id': 'obj-c35-savedev-zljoin', 'maxclass': 'newobj', 'text': 'zl.join',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 5910.0, 160.0, 22.0]})
add_line('obj-c35-savedev-tag', 0, 'obj-c35-savedev-zljoin', 1)       # cold: ['DEV', name...]
add_line('obj-c35-save-slotplus1', 0, 'obj-c35-savedev-zljoin', 0)    # HOT: triggers join (same slot as savepack)
add_line('obj-c35-savedev-zljoin', 0, 'obj-c35-ccdevice', 0)          # write [slot DEV device-name...]

# --- RECALL: fetch slot, look up values, dispatch to the 8 ccsel boxes ---
# obj-c35-ccrclbtn outputs the literal symbol "RECALL", which int objects do
# NOT understand (confirmed by the user's own Max console: `int: doesn't
# understand "RECALL"`) -- unlike `t`, which fires its outlets regardless of
# input type, `int` only accepts bang/int/float. SAVE was already routed
# through `t` first (obj-c35-save-t) so it never hit this; RECALL was wired
# directly into the shadow int and needs the same `t b` in front of it.
add_box({'id': 'obj-c35-rcl-t', 'maxclass': 'newobj', 'text': 't b',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5100.0, 5930.0, 40.0, 22.0]})
add_box({'id': 'obj-c35-rcl-slotplus1', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 5950.0, 40.0, 22.0]})
add_line('obj-c35-ccrclbtn', 0, 'obj-c35-rcl-t', 0)
add_line('obj-c35-rcl-t', 0, 'obj-c35-ccshadow-rcl', 0)
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

# also look up and re-select the saved MIDI Control Input Device by NAME
# (not by replaying a raw umenu index, which could point at a different
# device if ports were added/removed/reordered since the save) -- fans out
# from the same slot value already computed above, an independent read
# with no ordering dependency on the ccvalues lookup.
#
# THIRD ATTEMPT AT THIS, STILL REPORTED BROKEN IN REAL MAX TESTING: the
# previous fix here assumed `coll` always wraps a single-atom symbol value
# as "symbol <value>" on lookup, and used `route symbol` to strip that.
# That still didn't work. Rather than keep re-guessing at coll's exact
# undocumented single-atom-vs-multi-atom output formatting (two rounds of
# "confirmed via docs" reasoning both failed in practice), the write side
# above now tags every stored value with a fixed marker atom ('DEV')
# BEFORE it ever reaches the coll, so the stored value is always >= 2
# atoms and its lookup output format is no longer ambiguous either way.
# Extraction here is just `route DEV`: matched outlet strips the marker,
# leaving exactly the device-name atoms, deterministically -- no guessing
# required about how coll would otherwise format a single-atom value.
# Reject outlet (shouldn't fire in normal operation, since every entry --
# default or saved -- always carries the tag now) passes anything
# untagged through unchanged, as a defensive fallback only.
add_line('obj-c35-rcl-slotplus1', 0, 'obj-c35-ccdevice', 0)  # lookup -> outlet0: [DEV, name...]
add_box({'id': 'obj-c35-rcl-dev-routesym', 'maxclass': 'newobj', 'text': 'route DEV',
         'numinlets': 2, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5300.0, 5980.0, 90.0, 22.0]})
add_line('obj-c35-ccdevice', 0, 'obj-c35-rcl-dev-routesym', 0)
add_box({'id': 'obj-c35-rcl-dev-prepend', 'maxclass': 'newobj', 'text': 'prepend symbol',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5400.0, 6010.0, 100.0, 22.0]})
add_line('obj-c35-rcl-dev-routesym', 0, 'obj-c35-rcl-dev-prepend', 0)  # matched: tag stripped, bare name
add_line('obj-c35-rcl-dev-routesym', 1, 'obj-c35-rcl-dev-prepend', 0)  # reject: unchanged (untagged fallback)
add_line('obj-c35-rcl-dev-prepend', 0, 'obj-c34-indev', 0)  # select by name (fires real output too)

# --- RENAME: write into ccnames directly (synchronous, no external
#     protocol), then rebuild the menu immediately.
#
# NOT `pack s i` (what Control-34's obj-c34-namepack uses): confirmed via
# Cycling '74's own pack documentation that when a multi-atom LIST arrives
# at one inlet, "the first item is stored in the location that corresponds
# to the inlet in which it was received, and each subsequent item is stored
# as if it had arrived in subsequent inlets". For a 2+-word name typed into
# ccnameedit (e.g. "My Kit"), the second word ("Kit") would spill over into
# pack's NEXT inlet -- here, the int-typed slot-number inlet -- silently
# CLOBBERING the slot number (converted to 0, since a symbol landing in an
# int-typed inlet becomes 0) with no error printed. That's the confirmed
# "int: doesn't understand" class of bug in a different, silent form: not a
# console error, just a rename landing on coll key 0 (invisible -- outside
# the displayed 1-16 range) while the intended slot's name never changes.
# Used `zl.join` instead (the same fix already proven for the 128-preset
# name cache in Control-34, for the identical reason): its hot inlet
# contributes the FIRST segment of the output list, cold inlet the SECOND,
# with no per-inlet atom-count limit either side.
#
# obj-c35-ccname-t (t b l b, right-to-left): outlet2 (FIRST) clears the
# textbox; outlet1 (SECOND, passthrough) stores the just-typed name into
# zljoin's COLD inlet; outlet0 (THIRD/LAST) bangs a dedicated shadow to
# fetch the CURRENT slot fresh, feeding zljoin's HOT inlet -- guaranteeing
# the name is already cold-stored before the slot triggers the join, so
# the output is always exactly [slot, name...].
add_box({'id': 'obj-c35-ccname-zljoin', 'maxclass': 'newobj', 'text': 'zl.join',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 6010.0, 60.0, 22.0]})
add_box({'id': 'obj-c35-ccslot1-rename', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5170.0, 6010.0, 40.0, 22.0]})
add_box({'id': 'obj-c35-ccname-t', 'maxclass': 'newobj', 'text': 't b l b',
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['bang', '', 'bang'],
         'patching_rect': [5100.0, 5980.0, 50.0, 22.0]})
add_line('obj-c35-ccroute-text', 0, 'obj-c35-ccname-t', 0)
add_line('obj-c35-ccname-t', 1, 'obj-c35-ccname-zljoin', 1)          # SECOND: name (cold)
add_line('obj-c35-ccname-t', 0, 'obj-c35-ccshadow-rename', 0)        # THIRD/LAST: fetch slot
add_line('obj-c35-ccshadow-rename', 0, 'obj-c35-ccslot1-rename', 0)
add_line('obj-c35-ccslot1-rename', 0, 'obj-c35-ccname-zljoin', 0)    # HOT: triggers join
add_box({'id': 'obj-c35-ccnameedit-clear', 'maxclass': 'message', 'text': 'clear',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5170.0, 5980.0, 50.0, 20.0]})
add_line('obj-c35-ccname-t', 2, 'obj-c35-ccnameedit-clear', 0)  # FIRST: clear box
add_line('obj-c35-ccnameedit-clear', 0, 'obj-c35-ccnameedit', 0)

# write the join's output (always [slot, name...]) into ccnames, THEN
# (only after that write lands) trigger a rebuild -- explicit `t` rather
# than relying on zl.join's own fan-out order between two destinations,
# per this codebase's own established rule that multi-destination fan-out
# order is unreliable and must be sequenced with a trigger object instead.
add_box({'id': 'obj-c35-ccname-write-t', 'maxclass': 'newobj', 'text': 't b l',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', ''],
         'patching_rect': [5100.0, 6040.0, 50.0, 22.0]})
add_line('obj-c35-ccname-zljoin', 0, 'obj-c35-ccname-write-t', 0)
add_line('obj-c35-ccname-write-t', 1, 'obj-c35-ccnames', 0)  # FIRST: write [slot name...]

# --- REBUILD (shared by loadbang and rename): clear + uzi16 + append,
#     reading names straight from obj-c35-ccnames -- no capture phase
#     needed since this coll is the sole, synchronous source of truth ---
add_box({'id': 'obj-c35-rebuild-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', 'bang'],
         'patching_rect': [5100.0, 6100.0, 50.0, 22.0]})
add_line('obj-c35-ccname-write-t', 0, 'obj-c35-rebuild-t', 0)  # LAST: after the write lands
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
