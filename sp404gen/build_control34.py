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
# =====================================================================
N_PRESETS = 128

assert box_by_id['obj-pv2-pgsplit']['text'] == 'split 0 7'
box_by_id['obj-pv2-pgsplit']['text'] = 'split 0 127'

slotmenu = box_by_id['obj-pv2-slotmenu']
slotmenu['items'] = []
for n in range(1, N_PRESETS + 1):
    if n > 1:
        slotmenu['items'].append(',')
    slotmenu['items'] += ['Preset', str(n)]

add_box({'id': 'obj-c34-namecoll', 'maxclass': 'newobj',
         'text': 'coll obj-c34-namecoll @embed 1',
         'numinlets': 1, 'numoutlets': 4,
         'outlettype': ['', '', '', ''],
         'saved_object_attributes': {'embed': 1, 'precision': 6},
         'patching_rect': [5100.0, 4500.0, 180.0, 22.0],
         'coll_data': {
             'count': N_PRESETS,
             # single atom per entry, always -- sprintf's %s substitution
             # takes exactly one value, so a 2-atom default like
             # ['Preset', '5'] would only contribute 'Preset' and silently
             # drop the number (textedit-typed renames are already always
             # a single atom, spaces included, so this only affects defaults)
             'data': [{'key': n, 'value': [f'Preset{n}']}
                      for n in range(1, N_PRESETS + 1)],
         }})

add_box({'id': 'obj-c34-slotshadow', 'maxclass': 'newobj', 'text': 'int 0',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 4540.0, 50.0, 22.0]})
add_line('obj-pv2-slotmenu', 0, 'obj-c34-slotshadow', 1)  # cold tap, silent
# separate shadow for the post-rebuild selection restore -- keeping this off
# obj-c34-slotshadow's own outlet means banging it to restore the display
# can never also fire the rename-store chain below (they'd otherwise share
# one outlet's fan-out, with namepack picking up whatever stale/uninitialized
# name happened to be in its cold inlet)
add_box({'id': 'obj-c34-slotshadow-restore', 'maxclass': 'newobj', 'text': 'int 0',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 4570.0, 50.0, 22.0]})
add_line('obj-pv2-slotmenu', 0, 'obj-c34-slotshadow-restore', 1)  # cold tap, silent

# --- rename UI ---
add_box({'id': 'obj-c34-name-cmt', 'maxclass': 'comment',
         'text': 'Rename selected preset (type name, press Enter/Tab) -- PC number prefix is automatic',
         'patching_rect': [5100.0, 4580.0, 400.0, 20.0]})
add_box({'id': 'obj-c34-nameedit', 'maxclass': 'textedit',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4600.0, 200.0, 22.0],
         'presentation': 1, 'presentation_rect': [750.0, 140.0, 240.0, 22.0]})
# keymode/outputmode set as creation-time JSON attributes did NOT take effect
# in real Max testing (Return still just inserted a line break, and the
# output still arrived as a "text <words...>" message rather than a bare
# symbol). Max's own textedit reference documents BOTH as also settable by
# sending the attribute as a message to the inlet ("the message keymode 1
# causes..."), which is the mechanism used here instead, fired once at load:
#   keymode 1    -- Return outputs the buffer instead of inserting a line break
#   outputmode 1 -- output is a single symbol, not a "text <words...>" message
#                   (that "text" selector was otherwise silently swallowing
#                   everything the user typed -- pack's symbol inlet only
#                   keeps an incoming list's first atom, so the stored/
#                   displayed name became the literal word "text")
add_box({'id': 'obj-c34-nameedit-lb', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5260.0, 4600.0, 60.0, 22.0]})
add_box({'id': 'obj-c34-nameedit-keymode', 'maxclass': 'message', 'text': 'keymode 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5330.0, 4600.0, 70.0, 20.0]})
add_box({'id': 'obj-c34-nameedit-outmode', 'maxclass': 'message', 'text': 'outputmode 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5410.0, 4600.0, 90.0, 20.0]})
add_line('obj-c34-nameedit-lb', 0, 'obj-c34-nameedit-keymode', 0)
add_line('obj-c34-nameedit-lb', 0, 'obj-c34-nameedit-outmode', 0)
add_line('obj-c34-nameedit-keymode', 0, 'obj-c34-nameedit', 0)
add_line('obj-c34-nameedit-outmode', 0, 'obj-c34-nameedit', 0)
add_box({'id': 'obj-c34-namet', 'maxclass': 'newobj', 'text': 't b b l',
         'numinlets': 1, 'numoutlets': 3, 'outlettype': ['bang', 'bang', ''],
         'patching_rect': [5100.0, 4630.0, 60.0, 22.0]})
add_box({'id': 'obj-c34-slot1-name', 'maxclass': 'newobj', 'text': '+ 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5100.0, 4660.0, 40.0, 22.0]})
add_box({'id': 'obj-c34-namepack', 'maxclass': 'newobj', 'text': 'pack 0 s',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5160.0, 4660.0, 90.0, 22.0]})

add_line('obj-c34-nameedit', 0, 'obj-c34-namet', 0)
add_line('obj-c34-namet', 2, 'obj-c34-namepack', 1)        # FIRST: name -> cold store
add_line('obj-c34-namet', 1, 'obj-c34-slotshadow', 0)      # SECOND: bang -> current slot (0-based)
add_line('obj-c34-slotshadow', 0, 'obj-c34-slot1-name', 0)
add_line('obj-c34-slot1-name', 0, 'obj-c34-namepack', 0)   # hot: triggers [slot, name]
add_line('obj-c34-namepack', 0, 'obj-c34-namecoll', 0)     # store into coll

# --- rebuild routine (shared by loadbang and rename) ---
add_box({'id': 'obj-c34-lb2', 'maxclass': 'newobj', 'text': 'loadbang',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': ['bang'],
         'patching_rect': [5100.0, 4700.0, 60.0, 22.0]})
add_box({'id': 'obj-c34-rebuild-t', 'maxclass': 'newobj', 'text': 't b b',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', 'bang'],
         'patching_rect': [5100.0, 4730.0, 50.0, 22.0]})
add_box({'id': 'obj-c34-clear-msg', 'maxclass': 'message', 'text': 'clear',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5100.0, 4760.0, 50.0, 20.0]})
# uzi's args are <repetitions> <base>, NOT <repetitions> <outlet-index> --
# there is no "which outlet" argument, the right outlet always carries the
# counter regardless. "uzi 128 3" was misread as "counter on outlet 3" but
# actually means "counter starting at 3", i.e. it counts 3..130, not 1..128
# (confirmed against Max's own uzi reference). Omitting the second argument
# defaults the base to 1, which is what's actually needed here.
add_box({'id': 'obj-c34-rebuild-uzi', 'maxclass': 'newobj', 'text': 'uzi 128',
         'numinlets': 2, 'numoutlets': 3, 'outlettype': ['bang', 'bang', 'int'],
         'patching_rect': [5160.0, 4760.0, 70.0, 22.0]})
add_box({'id': 'obj-c34-rebuild-split', 'maxclass': 'newobj', 'text': 't i i',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['int', 'int'],
         'patching_rect': [5160.0, 4790.0, 50.0, 22.0]})
add_box({'id': 'obj-c34-rebuild-minus1', 'maxclass': 'newobj', 'text': '- 1',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': ['int'],
         'patching_rect': [5160.0, 4820.0, 40.0, 22.0]})
# single sprintf combining BOTH the PC number and the coll-stored name in one
# call -- standard documented Max sprintf behavior (mixing %ld and %s is
# routine). Replaces an earlier design that tried to build this message with
# a *dynamically re-armed* `prepend` instead: that failed in real Max testing
# (console flooded with `umenu: doesn't understand "Preset"`) because
# prepend's right inlet does not adopt a multi-atom message as its new
# prefix the way a single-specifier sprintf's output was assumed to be
# usable there -- it silently left the prefix unset and just passed the
# coll's raw content through unprefixed. A single dual-specifier sprintf
# has no such intermediate hand-off to get wrong.
add_box({'id': 'obj-c34-rebuild-sprintf', 'maxclass': 'newobj',
         'text': 'sprintf append PC%ld - %s',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5160.0, 4850.0, 140.0, 22.0]})

add_line('obj-c34-lb2', 0, 'obj-c34-rebuild-t', 0)
add_line('obj-c34-namet', 0, 'obj-c34-rebuild-t', 0)       # LAST (rename path): kick off rebuild
add_line('obj-c34-rebuild-t', 1, 'obj-c34-clear-msg', 0)   # FIRST: clear
add_line('obj-c34-clear-msg', 0, 'obj-pv2-slotmenu', 0)
add_line('obj-c34-rebuild-t', 0, 'obj-c34-rebuild-uzi', 0) # SECOND: start loop

add_line('obj-c34-rebuild-uzi', 2, 'obj-c34-rebuild-split', 0)  # counter 1..128
add_line('obj-c34-rebuild-split', 1, 'obj-c34-namecoll', 0)     # FIRST: lookup stored name
add_line('obj-c34-namecoll', 0, 'obj-c34-rebuild-sprintf', 1)   # cold: %s = name
add_line('obj-c34-rebuild-split', 0, 'obj-c34-rebuild-minus1', 0)  # SECOND: pc# path
add_line('obj-c34-rebuild-minus1', 0, 'obj-c34-rebuild-sprintf', 0)  # hot: %ld, triggers output
add_line('obj-c34-rebuild-sprintf', 0, 'obj-pv2-slotmenu', 0)

# restore the visible selection after the rebuild (clear wipes it)
add_box({'id': 'obj-c34-restore-pset', 'maxclass': 'newobj', 'text': 'prepend set',
         'numinlets': 1, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5260.0, 4760.0, 70.0, 22.0]})
add_line('obj-c34-rebuild-uzi', 1, 'obj-c34-slotshadow-restore', 0)  # done-bang -> re-output current slot
add_line('obj-c34-slotshadow-restore', 0, 'obj-c34-restore-pset', 0)
add_line('obj-c34-restore-pset', 0, 'obj-pv2-slotmenu', 0)

# =====================================================================
with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
