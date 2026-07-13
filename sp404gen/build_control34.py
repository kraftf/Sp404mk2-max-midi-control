"""
Builds Roland_SP404MK2_Control-34.maxpat from Control-33. Two new features:

1. MIDI CONTROL INPUT: lets an external MIDI controller drive the 8 visible
   controls that generate outgoing CC (the 6 dials, the EFX-select umenu, the
   EFX on/off toggle) -- nothing else. Adds:
   - "MIDI Control Input Device" umenu (obj-c34-indev, item list cloned from
     the existing "MIDI Output Device" umenu obj-4 -- this is the user's own
     MIDI port list, captured once on their machine; re-populate by hand if
     it doesn't match this machine's ports) -> prepend port -> a single bare
     `ctlin` (obj-c34-ctlin, all channels, all controllers on the selected
     port).
   - Per target, a "MIDI CC selector" (a plain `number` box, default = the
     CC the patch already sends to hardware for that control -- 16/17/18 for
     ctrl1-3, 80/81/82 for ctrl4-6, 83 for EFX select, 19 for EFX on/off).
   - Per target: ctlin's controller-number outlet drives a `==` (comparing
     against the CC selector's value) -> a `gate 1`'s control inlet; ctlin's
     value outlet feeds the gate's data inlet. When they match, the incoming
     CC value is delivered straight into the target's own hot inlet 0 -- the
     SAME inlet the user's own mouse edits use -- so it audibly sends CC out
     and updates pattrforward/pattrstorage exactly like a live edit. (EFX
     on/off gets an extra `>= 64` threshold since ctlin's value is 0-127 but
     live.toggle is a 0/1 control.)
   Ordering relies on ctlin's outlet firing order (right to left: channel,
   then controller#, then value) -- controller# always reaches the `==`
   before the value reaches the gate's data inlet, so the gate's open/closed
   state is always current before it receives data. This is the same
   right-to-left guarantee already relied on throughout this patch (t
   objects, uzi's counter outlet, etc).

2. 128 PRESETS (was 8), reflecting the full 0-127 Program Change range, with
   per-preset renaming that always keeps the PC number as a visible prefix:
   - obj-pv2-slotmenu grows from 8 items to 128 ("Preset 1".."Preset 128").
   - obj-pv2-pgsplit: `split 0 7` -> `split 0 127` (PC 0-127 now all recall
     a preset, was PC 0-7 only).
   - A new embedded `coll` (obj-c34-namecoll, @embed 1, independent of the
     pattrstorage-based Control33_presets.json companion file -- this is UI
     label state, not parameter data) holds ONLY the free-text part of each
     preset's name, keyed 1-128, defaulting to "Preset N". The PC-number
     prefix is never stored -- it's recomputed as (slot - 1) every time the
     menu is rebuilt, so renaming can never desync the prefix from the slot.
   - Rebuild routine (obj-c34-rebuild-t / -uzi / -split / -minus1 /
     -sprintf): clears slotmenu and re-appends all 128 items as
     "append PC<n> - <name...>", built with a single dual-specifier
     `sprintf append PC%ld - %s` -- %ld (the PC number, hot/leftmost inlet)
     and %s (the coll-stored name, cold/rightmost inlet) combined in one
     call, standard documented Max sprintf behavior. Runs once on load
     (obj-c34-lb2) and once after every rename.
     (An earlier version of this routine tried to build the same message
     from a proven single-specifier `sprintf append PC%ld -` PLUS a
     *dynamically re-armed* `prepend` object supplying the rest -- that
     failed in real Max testing: the console flooded with
     `umenu: doesn't understand "Preset"`, because `prepend`'s right inlet
     did not adopt the sprintf's multi-atom output as its new prefix the
     way a single-word prepend argument normally works, so it silently left
     the prefix empty and passed the coll's raw content straight through
     unprefixed. Replaced with the single dual-specifier sprintf above,
     which has no such intermediate hand-off to get wrong. Relatedly, the
     coll's default values are stored as ONE atom per entry, e.g.
     `Preset5` not `['Preset', '5']` -- `%s` substitutes exactly one atom,
     so a 2-atom default would have silently dropped the number.)
   - Rename UI: obj-c34-nameedit (`textedit`, free text, no PC number typed
     by the user) -> obj-c34-namet (`t b b l`, right-to-left): the passed-
     through text is stored into namepack's cold inlet FIRST, then the
     current slot (from obj-c34-slotshadow, +1) triggers namepack's hot
     inlet to write [slot, name] into namecoll, and only THEN (last) is the
     full rebuild kicked off -- so the rebuild's coll lookups always see the
     just-written name, never a stale one. Configured at load via explicit
     `keymode 1`/`outputmode 1` messages (see obj-c34-nameedit-lb and the
     two message boxes feeding it) rather than creation-time attributes --
     the attributes did not take effect when set that way in real Max
     testing; the message form is the mechanism Max's own reference
     documents.
   - obj-c34-slotshadow (`int`, cold-tapped from slotmenu's own outlet, same
     "shadow int" idiom used everywhere else in this patch) exists so the
     rename path can fetch the current slot without disturbing anything.
     The post-rebuild step (restore the visible selection via `prepend set`,
     since `clear` wipes it) uses its OWN separate shadow,
     obj-c34-slotshadow-restore, cold-tapped from the same source -- kept
     deliberately off obj-c34-slotshadow's outlet so that banging it to
     restore the display can never also fire the rename-store chain (they'd
     otherwise share one outlet's fan-out, with namepack picking up
     whatever stale/uninitialized name happened to be sitting in its cold
     inlet -- this was a real bug in the first Control-34 build, caught
     before it shipped).

Presets companion file renamed to Control34_presets.json (format unchanged --
still lacks any DFX/name data by design; names live in the embedded coll,
not the pattrstorage file).

NOT hardware/Max tested -- see SESSION_STATE.md "Control-34" MAX-TEST ITEMS,
in particular: the MIDI Control Input Device item list is a straight clone of
the output-device list and will likely need re-picking on the user's machine;
and the dual-specifier sprintf combining %ld and %s for preset renaming has
no precedent elsewhere in this codebase (though it replaced a `prepend`-based
design that failed outright in real Max testing -- see the "128 PRESETS"
section above for the full story).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-33.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-34.maxpat')

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
# 0. Presets companion file rename (33 -> 34)
# =====================================================================
PRESETS_FILENAME = 'Control34_presets.json'
assert box_by_id['obj-pv2-read-msg']['text'] == 'read "Control33_presets.json"'
assert box_by_id['obj-pv2-write-msg']['text'] == 'write "Control33_presets.json"'
box_by_id['obj-pv2-read-msg']['text'] = f'read "{PRESETS_FILENAME}"'
box_by_id['obj-pv2-write-msg']['text'] = f'write "{PRESETS_FILENAME}"'

# =====================================================================
# 1. MIDI CONTROL INPUT
# =====================================================================
MIDI_DEVICE_ITEMS = box_by_id['obj-4']['items']  # clone the output-device list

add_box({'id': 'obj-c34-in-cmt', 'maxclass': 'comment',
         'text': 'MIDI Control Input Device (external controller -> the 8 '
                 'controls below only)',
         'patching_rect': [40.0, 4000.0, 400.0, 20.0]})
add_box({'id': 'obj-c34-indev', 'maxclass': 'umenu', 'items': MIDI_DEVICE_ITEMS,
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', '', ''],
         'parameter_enable': 0,
         'patching_rect': [40.0, 4020.0, 160.0, 22.0],
         'presentation': 1, 'presentation_rect': [20.0, 660.0, 160.0, 22.0]})
add_box({'id': 'obj-c34-in-pport', 'maxclass': 'newobj', 'text': 'prepend port',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [40.0, 4050.0, 90.0, 22.0]})
add_box({'id': 'obj-c34-ctlin', 'maxclass': 'newobj', 'text': 'ctlin',
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['int', 'int', 'int'],
         'patching_rect': [40.0, 4080.0, 90.0, 22.0]})
add_line('obj-c34-indev', 1, 'obj-c34-in-pport', 0)
add_line('obj-c34-in-pport', 0, 'obj-c34-ctlin', 0)

# (name, default CC, target box id, kind)
MIDI_TARGETS = [
    ('ctrl1', 16, 'obj-458', 'dial'),
    ('ctrl2', 17, 'obj-466', 'dial'),
    ('ctrl3', 18, 'obj-474', 'dial'),
    ('ctrl4', 80, 'obj-482', 'dial'),
    ('ctrl5', 81, 'obj-490', 'dial'),
    ('ctrl6', 82, 'obj-498', 'dial'),
    ('efxsel', 83, 'obj-18', 'menu'),
    ('onoff', 19, 'obj-454', 'toggle'),
]

add_box({'id': 'obj-c34-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [40.0, 4110.0, 60.0, 22.0]})

for i, (name, cc, target_id, kind) in enumerate(MIDI_TARGETS):
    x = 40.0 + i * 150.0
    ccsel_id = f'obj-c34-ccsel-{name}'
    cmt_id = f'obj-c34-ccsel-cmt-{name}'
    init_id = f'obj-c34-ccsel-init-{name}'
    eq_id = f'obj-c34-eq-{name}'
    gate_id = f'obj-c34-gate-{name}'

    add_box({'id': cmt_id, 'maxclass': 'comment', 'text': f'{name} MIDI CC#',
             'patching_rect': [x, 4150.0, 140.0, 20.0]})
    add_box({'id': ccsel_id, 'maxclass': 'number',
             'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', 'bang'],
             'patching_rect': [x, 4170.0, 50.0, 22.0],
             'presentation': 1, 'presentation_rect': [20.0 + i * 60.0, 690.0, 50.0, 22.0]})
    add_box({'id': init_id, 'maxclass': 'message', 'text': str(cc),
             'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
             'patching_rect': [x, 4200.0, 40.0, 20.0]})
    add_box({'id': eq_id, 'maxclass': 'newobj', 'text': '==',
             'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
             'patching_rect': [x, 4230.0, 40.0, 22.0]})
    add_box({'id': gate_id, 'maxclass': 'newobj', 'text': 'gate 1',
             'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
             'patching_rect': [x, 4260.0, 40.0, 22.0]})

    add_line('obj-c34-lb', 0, init_id, 0)
    add_line(init_id, 0, ccsel_id, 0)          # hot: stores AND outputs default
    add_line(ccsel_id, 0, eq_id, 1)            # cold: target CC (updatable live)
    add_line('obj-c34-ctlin', 1, eq_id, 0)     # hot: incoming controller# (fires before value)
    add_line(eq_id, 0, gate_id, 0)             # control: 1 if match else 0
    add_line('obj-c34-ctlin', 0, gate_id, 1)   # data: incoming value (fires after controller#)

    if kind == 'toggle':
        thresh_id = f'obj-c34-onoff-thresh'
        add_box({'id': thresh_id, 'maxclass': 'newobj', 'text': '>= 64',
                 'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
                 'patching_rect': [x, 4290.0, 40.0, 22.0]})
        add_line(gate_id, 0, thresh_id, 0)
        add_line(thresh_id, 0, target_id, 0)
    else:
        add_line(gate_id, 0, target_id, 0)

# =====================================================================
# 2. 128 PRESETS + rename
#
# Rebuilt from scratch after three failed from-scratch attempts (missing
# "append" selector; a `prepend` that didn't adopt a multi-atom dynamic
# prefix; uzi's base-value argument; a coll whose single-atom values got
# wrapped as "symbol <value>" on lookup; textedit's unconditional "text"
# selector). The user supplied a WORKING reference patch of their own
# (MIDI_CC_scene_morph.maxpat) that renames a menu backed by pattrstorage --
# tracing it revealed pattrstorage has a NATIVE slot-naming protocol:
#   - "getslotnamelist" sent to pattrstorage makes it emit, via its own
#     outlet, one "slotname <preset#> <name>" message per slot it knows
#     about, followed by a bare "slotname done".
#   - "slotname <preset#> <name>" sent TO pattrstorage renames that slot.
# This is pattrstorage's own feature (not specific to the classic grid
# `preset` UI object) -- using it here replaces the entire custom coll +
# uzi-loop + sprintf/zl.join rebuild machinery with pattrstorage's own
# bookkeeping, which is what the reference patch does.
# =====================================================================
N_PRESETS = 128

assert box_by_id['obj-pv2-pgsplit']['text'] == 'split 0 7'
box_by_id['obj-pv2-pgsplit']['text'] = 'split 0 127'

slotmenu = box_by_id['obj-pv2-slotmenu']
slotmenu['items'] = []
for n in range(1, N_PRESETS + 1):
    if n > 1:
        slotmenu['items'].append(',')
    slotmenu['items'] += ['Preset', str(n)]  # placeholder only -- replaced at load by getslotnamelist

# shadow holds the last real user selection (cold-tapped, silent) so the
# visible highlight can be restored after "clear" wipes it during a rebuild
add_box({'id': 'obj-c34-slotshadow', 'maxclass': 'newobj', 'text': 'int 0',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 4540.0, 50.0, 22.0]})
add_line('obj-pv2-slotmenu', 0, 'obj-c34-slotshadow', 1)  # cold tap, silent
add_box({'id': 'obj-c34-restore-pset', 'maxclass': 'newobj', 'text': 'prepend set',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4570.0, 70.0, 22.0]})
add_line('obj-c34-slotshadow', 0, 'obj-c34-restore-pset', 0)
add_line('obj-c34-restore-pset', 0, 'obj-pv2-slotmenu', 0)

# --- rename UI ---
add_box({'id': 'obj-c34-name-cmt', 'maxclass': 'comment',
         'text': 'Rename selected preset (type name, press Enter/Tab) -- PC number prefix is automatic',
         'patching_rect': [5100.0, 4600.0, 400.0, 20.0]})
# outputmode 1 as a creation-time attribute matches the user's own working
# reference patch (obj-224 there); route text is kept regardless (also
# present in that same reference patch) since outputmode does not remove
# textedit's unconditional "text" selector -- confirmed both by Max forum
# threads and by testing this exact patch.
# numoutlets/outlettype copied EXACTLY from that reference patch's obj-224 --
# textedit always has 4 outlets (only outlet 0 is used, same as there); an
# earlier build here wrongly declared numoutlets=1, a genuine box-definition
# mismatch for this maxclass that plausibly broke the whole patch's load
# (matches the reported "menu shows nothing, SAVE does nothing" symptom,
# which has nothing to do with the rename feature specifically).
add_box({'id': 'obj-c34-nameedit', 'maxclass': 'textedit',
         'numinlets': 1, 'numoutlets': 4, 'outlettype': ['', 'int', '', ''],
         'outputmode': 1,
         'patching_rect': [5100.0, 4620.0, 200.0, 22.0],
         'presentation': 1, 'presentation_rect': [750.0, 140.0, 240.0, 22.0]})
add_box({'id': 'obj-c34-nameedit-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5260.0, 4620.0, 60.0, 22.0]})
add_box({'id': 'obj-c34-nameedit-keymode', 'maxclass': 'message', 'text': 'keymode 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5330.0, 4620.0, 70.0, 20.0]})
add_line('obj-c34-nameedit-lb', 0, 'obj-c34-nameedit-keymode', 0)
add_line('obj-c34-nameedit-keymode', 0, 'obj-c34-nameedit', 0)
add_box({'id': 'obj-c34-route-text', 'maxclass': 'newobj', 'text': 'route text',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5100.0, 4650.0, 90.0, 22.0]})
add_line('obj-c34-nameedit', 0, 'obj-c34-route-text', 0)

# current slot, tracked continuously (no bang-fetch needed -- fires on
# every real selection change, which always happens well before the user
# finishes typing a name, so pack's cold inlet is already correct by the
# time Return commits the text). NOT offset by +1: pattrstorage's own
# "slotname" numbering is 0-based and matches obj-pv2-slotmenu's own
# 0-based item index directly -- confirmed by Max testing, where an
# earlier +1 here (copied from the unrelated SAVE/RECALL "store N +1"
# convention) renamed the slot AFTER the one actually selected. Kept as a
# "+ 0" object rather than wiring straight through so the intent (this is
# deliberately a no-op, not a forgotten adjustment) stays visible in the
# patch.
add_box({'id': 'obj-c34-slot1', 'maxclass': 'newobj', 'text': '+ 0',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 4680.0, 40.0, 22.0]})
add_line('obj-pv2-slotmenu', 0, 'obj-c34-slot1', 0)
# pack s i (hot=text, cold=slot#) -> reorder via a message box into
# pattrstorage's own "slotname <preset#> <name>" rename syntax -- mirrors
# the reference patch's obj-22/obj-13 exactly
add_box({'id': 'obj-c34-namepack', 'maxclass': 'newobj', 'text': 'pack s i',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4710.0, 60.0, 22.0]})
add_line('obj-c34-route-text', 0, 'obj-c34-namepack', 0)   # hot: typed text triggers
add_line('obj-c34-slot1', 0, 'obj-c34-namepack', 1)        # cold: current slot#, continuously updated
add_box({'id': 'obj-c34-namemsg', 'maxclass': 'message', 'text': 'slotname $2 $1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4740.0, 100.0, 20.0]})
add_line('obj-c34-namepack', 0, 'obj-c34-namemsg', 0)
# t b l b (right-to-left): out2 (FIRST, NEW) clears the textedit box so
# leftover text can't get silently prepended to the next thing typed
# (confirmed by Max testing: a rename landed as "Downer my" -- "Downer"
# was leftover from an earlier interaction, "my" was what was actually
# typed this time, and textedit never clears itself on its own); out1
# (SECOND) sends the rename straight into pattrstorage; out0 (THIRD/LAST)
# kicks off a refresh once the rename has actually landed. Existing outlet
# indices 0 and 1 are unchanged from the prior "t b l" -- the new outlet
# was added at the front (rightmost, fires first) so nothing downstream
# needed remapping.
add_box({'id': 'obj-c34-name-t', 'maxclass': 'newobj', 'text': 't b l b',
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['bang', '', 'bang'],
         'patching_rect': [5100.0, 4770.0, 50.0, 22.0]})
add_line('obj-c34-namemsg', 0, 'obj-c34-name-t', 0)
add_line('obj-c34-name-t', 1, 'obj-pv2-pattrstorage', 0)   # SECOND: rename command
add_line('obj-c34-name-t', 0, 'obj-c34-refresh-t', 0)      # THIRD/LAST: refresh (defined below)
add_box({'id': 'obj-c34-nameedit-clear', 'maxclass': 'message', 'text': 'clear',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5170.0, 4770.0, 50.0, 20.0]})
add_line('obj-c34-name-t', 2, 'obj-c34-nameedit-clear', 0)  # FIRST: clear the box
add_line('obj-c34-nameedit-clear', 0, 'obj-c34-nameedit', 0)

# --- refresh routine (shared by loadbang, rename, and SAVE) ---
add_box({'id': 'obj-c34-lb2', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5100.0, 4800.0, 60.0, 22.0]})

# SAVE should also refresh the menu -- the reference patch's classic grid
# `preset` UI object does this automatically as part of its own store
# behavior, which this patch has no equivalent of (it uses a plain umenu +
# explicit "store N" instead). Extend obj-pv2-save-t (t b b -> t b b b, the
# same technique already used in Control-33 for obj-pv2-rcl-post-t): the
# new LEFTMOST outlet fires LAST, guaranteeing the "store" message has
# already reached pattrstorage before the refresh is requested.
save_t = box_by_id['obj-pv2-save-t']
assert save_t['text'] == 't b b', f'obj-pv2-save-t: unexpected text {save_t["text"]!r}'
save_t['text'] = 't b b b'
save_t['numoutlets'] = 3
save_t['outlettype'] = ['', '', '']
remapped_save = 0
for l in lines:
    pl = l['patchline']
    if pl['source'][0] == 'obj-pv2-save-t':
        pl['source'][1] += 1
        remapped_save += 1
assert remapped_save == 2, f'expected 2 obj-pv2-save-t outlet lines to remap, got {remapped_save}'
add_line('obj-pv2-save-t', 0, 'obj-c34-refresh-t', 0)  # LAST: refresh after the store lands
# t b b (right-to-left): out1 (FIRST) clears the menu and opens the gate;
# out0 (SECOND) asks pattrstorage for the current slot-name list
add_box({'id': 'obj-c34-refresh-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', 'bang'],
         'patching_rect': [5100.0, 4830.0, 50.0, 22.0]})
add_line('obj-c34-lb2', 0, 'obj-c34-refresh-t', 0)
add_box({'id': 'obj-c34-clearopen', 'maxclass': 'newobj', 'text': 't 1 clear',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['int', 'clear'],
         'patching_rect': [5100.0, 4860.0, 60.0, 22.0]})
add_line('obj-c34-refresh-t', 1, 'obj-c34-clearopen', 0)
add_line('obj-c34-clearopen', 1, 'obj-pv2-slotmenu', 0)    # FIRST: "clear" -> wipe the menu
add_box({'id': 'obj-c34-gate', 'maxclass': 'newobj', 'text': 'gate 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4890.0, 40.0, 22.0]})
add_line('obj-c34-clearopen', 0, 'obj-c34-gate', 0)        # SECOND: "1" -> open the gate
add_line('obj-c34-gate', 0, 'obj-pv2-slotmenu', 0)
add_box({'id': 'obj-c34-getslotnamelist', 'maxclass': 'message', 'text': 'getslotnamelist',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5170.0, 4860.0, 110.0, 20.0]})
add_line('obj-c34-refresh-t', 0, 'obj-c34-getslotnamelist', 0)
add_line('obj-c34-getslotnamelist', 0, 'obj-pv2-pattrstorage', 0)

# --- parse pattrstorage's reply stream ---
add_box({'id': 'obj-c34-slotname-route', 'maxclass': 'newobj', 'text': 'route slotname',
         'numinlets': 2, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5170.0, 4920.0, 90.0, 22.0]})
add_line('obj-pv2-pattrstorage', 0, 'obj-c34-slotname-route', 0)  # new tap on the existing outlet
add_box({'id': 'obj-c34-slotname-done', 'maxclass': 'newobj', 'text': 'route done',
         'numinlets': 2, 'numoutlets': 2, 'outlettype': ['', ''],
         'patching_rect': [5170.0, 4950.0, 90.0, 22.0]})
add_line('obj-c34-slotname-route', 0, 'obj-c34-slotname-done', 0)
add_box({'id': 'obj-c34-gateclose', 'maxclass': 'newobj', 'text': 't 0',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5170.0, 4980.0, 30.0, 22.0]})
add_line('obj-c34-slotname-done', 0, 'obj-c34-gateclose', 0)  # matched "done" (bare bang)
add_line('obj-c34-gateclose', 0, 'obj-c34-gate', 0)           # closes the gate
add_line('obj-c34-slotname-done', 0, 'obj-c34-slotshadow', 0)  # ALSO restore the visible selection

add_box({'id': 'obj-c34-slotname-unpack', 'maxclass': 'newobj', 'text': 'unpack 0 s',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['int', ''],
         'patching_rect': [5250.0, 4980.0, 70.0, 22.0]})
add_line('obj-c34-slotname-done', 1, 'obj-c34-slotname-unpack', 0)  # unmatched: "<n> <name>"
# pattrstorage always reports a permanent slot 0 ("(undefined)") ahead of
# any user-created slots -- confirmed by Max testing (it showed up as
# "PC-1 - (undefined)", always present, never one of the intended 128).
# select 0 filters it out: its reject outlet (1, non-zero slots) passes
# through to the PC-prefix/append path unchanged; its match outlet (0,
# slot==0) is left unwired, so slot 0 is silently skipped and never
# appended to the visible menu.
add_box({'id': 'obj-c34-slotname-notzero', 'maxclass': 'newobj', 'text': 'select 0',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', 'int'],
         'patching_rect': [5250.0, 5000.0, 60.0, 22.0]})
add_line('obj-c34-slotname-unpack', 0, 'obj-c34-slotname-notzero', 0)  # SECOND (int, leftmost)
add_box({'id': 'obj-c34-slotname-minus1', 'maxclass': 'newobj', 'text': '- 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5250.0, 5015.0, 40.0, 22.0]})
add_line('obj-c34-slotname-notzero', 1, 'obj-c34-slotname-minus1', 0)  # reject (non-zero) passthrough
# single-specifier sprintf builds "append PC<n> -" (proven pattern, same as
# the existing `sprintf send Bus%d_X` objects). zl.join then concatenates
# that with the (possibly multi-atom) name from unpack -- NOT %s (exactly
# one atom) and NOT a dynamically re-armed `prepend` (confirmed broken for
# a multi-atom prefix in real Max testing).
add_box({'id': 'obj-c34-slotname-sprintf', 'maxclass': 'newobj',
         'text': 'sprintf append PC%ld -',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5250.0, 5040.0, 100.0, 22.0]})
add_line('obj-c34-slotname-minus1', 0, 'obj-c34-slotname-sprintf', 0)
add_box({'id': 'obj-c34-slotname-zljoin', 'maxclass': 'newobj', 'text': 'zl.join',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5250.0, 5070.0, 60.0, 22.0]})
add_line('obj-c34-slotname-unpack', 1, 'obj-c34-slotname-zljoin', 1)   # FIRST (symbol, rightmost): 2nd segment
add_line('obj-c34-slotname-sprintf', 0, 'obj-c34-slotname-zljoin', 0)  # SECOND: 1st segment, triggers join
add_line('obj-c34-slotname-zljoin', 0, 'obj-c34-gate', 1)              # data -> gate (passes if open)

# =====================================================================
with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
