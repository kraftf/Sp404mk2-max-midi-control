"""
Structural validation for a .maxpat: catches the class of errors that would
otherwise only surface as a Max console error or a silent dangling wire --
NOT a check that the patch behaves correctly (that requires opening it in
Max, which this script cannot do).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'Roland_SP404MK2_Control-34.maxpat')

with open(target) as f:
    data = json.load(f)

p = data['patcher']
boxes = p['boxes']
lines = p['lines']

errors = []
warnings = []

box_by_id = {}
for b in boxes:
    box = b['box']
    bid = box.get('id')
    if bid is None:
        errors.append(f'box missing id: {box}')
        continue
    if bid in box_by_id:
        errors.append(f'duplicate box id: {bid}')
    box_by_id[bid] = box

# 1. every patchline source/destination id must exist, inlet/outlet indices in range
for l in lines:
    pl = l['patchline']
    (src, sout), (dst, din) = pl['source'], pl['destination']
    for bid, role in ((src, 'source'), (dst, 'destination')):
        if bid not in box_by_id:
            errors.append(f'patchline {role} references missing box: {bid}')
    if src in box_by_id:
        nout = box_by_id[src].get('numoutlets', 1)
        if not (0 <= sout < nout):
            errors.append(f'{src}: outlet {sout} out of range (numoutlets={nout})')
    if dst in box_by_id:
        dst_box = box_by_id[dst]
        # expr/expr~ objects: Max derives real inlet count from the expression
        # text ($i2 etc) at load time, not from the saved numinlets field --
        # this mismatch pre-exists in Control-31 itself, so skip the check.
        if dst_box.get('text', '').split(' ')[0] in ('expr', 'expr~'):
            pass
        else:
            nin = dst_box.get('numinlets', 1)
            if not (0 <= din < nin):
                errors.append(f'{dst}: inlet {din} out of range (numinlets={nin})')

# 2. no dangling references to the removed psys-* namespace
for l in lines:
    pl = l['patchline']
    for bid in (pl['source'][0], pl['destination'][0]):
        if bid.startswith('obj-psys-'):
            errors.append(f'dangling psys-* reference in patchline: {bid}')
for bid in box_by_id:
    if bid.startswith('obj-psys-'):
        errors.append(f'psys-* box still present: {bid}')

# 3. varnames unique, and the 45 Bus{1-5}_{param} + Dfx{1-5} names match the subscribe list exactly
varnames = {}
for bid, box in box_by_id.items():
    vn = box.get('varname')
    if vn:
        if vn in varnames:
            errors.append(f'duplicate varname "{vn}": {bid} and {varnames[vn]}')
        varnames[vn] = bid

sub_msg = box_by_id.get('obj-pv2-sub-msg')
if sub_msg is None:
    errors.append('subscribe message box obj-pv2-sub-msg not found')
else:
    sub_names = sub_msg['text'].split()[1:]  # drop leading "subscribe"
    bg_varnames = {vn for vn in varnames if vn.startswith('Bus') or vn.startswith('Dfx')}
    if set(sub_names) != bg_varnames:
        missing_from_sub = bg_varnames - set(sub_names)
        missing_from_bg = set(sub_names) - bg_varnames
        if missing_from_sub:
            errors.append(f'bg varnames not in subscribe list: {sorted(missing_from_sub)}')
        if missing_from_bg:
            errors.append(f'subscribe list names with no matching bg object: {sorted(missing_from_bg)}')
    if len(sub_names) != len(set(sub_names)):
        errors.append('subscribe list has duplicate names')
    expected_count = 45
    if len(sub_names) != expected_count:
        errors.append(f'expected {expected_count} subscribed names, got {len(sub_names)}')

# 4. every bg object's declared parameter_longname must match its varname
for bid, box in box_by_id.items():
    if bid.startswith('obj-pv2-bg-') or bid.startswith('obj-pv33-bg-'):
        vn = box.get('varname')
        pln = box.get('saved_attribute_attributes', {}).get('valueof', {}).get('parameter_longname')
        if vn != pln:
            errors.append(f'{bid}: varname "{vn}" != parameter_longname "{pln}"')

# 5. sanity counts
n_bg = sum(1 for bid in box_by_id
           if bid.startswith('obj-pv2-bg-') or bid.startswith('obj-pv33-bg-'))
n_hwh = sum(1 for bid in box_by_id if bid.startswith('obj-pv2-hwh-'))
n_sh = sum(1 for bid in box_by_id
           if bid.startswith('obj-pv2-sh-') or bid.startswith('obj-pv33-sh-'))
if n_bg != 45:
    errors.append(f'expected 45 bg client objects (40 bus + 5 DFX), found {n_bg}')
if n_hwh != 40:
    errors.append(f'expected 40 hw-holder objects, found {n_hwh}')
if n_sh != 45:
    errors.append(f'expected 45 display shadow objects (40 bus + 5 DFX), found {n_sh}')

# 6. no expr may use the never-implemented C-style ternary (silently fails
#    to compile in Max -- the Control-30 SYNC bug fixed in Control-33)
for bid, box in box_by_id.items():
    t = box.get('text', '')
    if t.split(' ')[0] in ('expr', 'expr~') and '?' in t:
        errors.append(f'{bid}: expr uses unsupported ternary operator: {t!r}')

# 7. bus-switch refresh must be decoupled from obj-12's same-outlet firing
#    order: obj-12 must reach obj-pv2-busadd ONLY via the deferlow
#    obj-pv33-busdefer (cross-group label-scramble fix)
conn = {(tuple(l['patchline']['source']), tuple(l['patchline']['destination'])) for l in lines}
if (('obj-12', 0), ('obj-pv2-busadd', 0)) in conn:
    errors.append('obj-12 wired directly to obj-pv2-busadd (bus-switch refresh not deferred)')
if (('obj-12', 0), ('obj-pv33-busdefer', 0)) not in conn or \
   (('obj-pv33-busdefer', 0), ('obj-pv2-busadd', 0)) not in conn:
    errors.append('missing obj-12 -> obj-pv33-busdefer -> obj-pv2-busadd chain')

# 8. post-recall sequence must be triggered by the recall COMMANDS, never by
#    pattrstorage's notification outlet (fires on store/write/read too), and
#    the display refresh must restore the MIDI channel (obj-15) via busN-t
#    before the select fans fire (post-SAVE/RECALL channel-5 residue fix)
if (('obj-pv2-pattrstorage', 0), ('obj-pv2-rcl-defer', 0)) in conn:
    errors.append('pattrstorage notification outlet still triggers rcl-defer '
                  '(SAVE/read would run the hw dispatch)')
for src in ('obj-pv2-rcl-msg', 'obj-pv2-pgrcl'):
    if ((src, 0), ('obj-pv2-rcl-defer', 0)) not in conn:
        errors.append(f'missing {src} -> obj-pv2-rcl-defer recall trigger')
if (('obj-pv2-busN', 0), ('obj-pv33-busN-t', 0)) not in conn or \
   (('obj-pv33-busN-t', 1), ('obj-15', 0)) not in conn:
    errors.append('missing busN -> busN-t -> obj-15 channel-restore chain')
for s, dst in conn:
    if s[0] == 'obj-pv2-busN' and dst[0].startswith('obj-pv2-sel-'):
        errors.append(f'busN still wired directly to {dst[0]} (bypasses channel restore)')

# 9. presets companion-file messages must reference the Control-34 filename
for bid, expected in (('obj-pv2-read-msg', 'read "Control34_presets.json"'),
                      ('obj-pv2-write-msg', 'write "Control34_presets.json"')):
    box = box_by_id.get(bid)
    if box is None:
        errors.append(f'{bid} not found')
    elif box['text'] != expected:
        errors.append(f'{bid}: text {box["text"]!r} != {expected!r}')

# 10. MIDI control input: 8 targets, each with ctlin -> == -> gate -> target
#     hot inlet 0 (or -> threshold -> target for the on/off toggle), and CC
#     selector defaults must match what the patch actually sends to hardware
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
if box_by_id.get('obj-c34-ctlin', {}).get('text') != 'ctlin':
    errors.append('obj-c34-ctlin missing or not a bare ctlin (must not filter CC# at the object level)')
for name, cc, target_id, kind in MIDI_TARGETS:
    ccsel_id, init_id, eq_id, gate_id = (f'obj-c34-ccsel-{name}', f'obj-c34-ccsel-init-{name}',
                                         f'obj-c34-eq-{name}', f'obj-c34-gate-{name}')
    init_box = box_by_id.get(init_id)
    if init_box is None:
        errors.append(f'{init_id} not found')
    elif init_box['text'] != str(cc):
        errors.append(f'{init_id}: default {init_box["text"]!r} != expected {cc!r} (hardware CC mismatch)')
    if (('obj-c34-ctlin', 1), (eq_id, 0)) not in conn:
        errors.append(f'missing ctlin controller# -> {eq_id} (hot inlet 0)')
    if ((ccsel_id, 0), (eq_id, 1)) not in conn:
        errors.append(f'missing {ccsel_id} -> {eq_id} cold inlet 1')
    if ((eq_id, 0), (gate_id, 0)) not in conn:
        errors.append(f'missing {eq_id} -> {gate_id} control inlet 0')
    if (('obj-c34-ctlin', 0), (gate_id, 1)) not in conn:
        errors.append(f'missing ctlin value -> {gate_id} data inlet 1')
    if kind == 'toggle':
        if ((gate_id, 0), ('obj-c34-onoff-thresh', 0)) not in conn or \
           (('obj-c34-onoff-thresh', 0), (target_id, 0)) not in conn:
            errors.append(f'missing {gate_id} -> onoff-thresh -> {target_id} chain')
    else:
        if ((gate_id, 0), (target_id, 0)) not in conn:
            errors.append(f'missing {gate_id} -> {target_id} hot inlet 0')

# 11. 128 presets: slotmenu must have 128 placeholder items, PC split must
#     cover 0-127, and renaming/display uses a two-phase CAPTURE (write
#     pattrstorage's native "slotname <n> <name>" replies into a coll)
#     then REBUILD (unconditionally build all 128 items from that coll,
#     falling back to a seeded default for any never-reported slot) --
#     the previous "clear + append only what pattrstorage reports" design
#     got permanently stuck at however many slots had been saved so far,
#     since getslotnamelist only reports "0 to the largest stored slot"
#     (confirmed via Max's own pattrstorage docs) and there was no way to
#     select a not-yet-existing slot through the same umenu used to
#     display known ones.
if box_by_id['obj-pv2-pgsplit']['text'] != 'split 0 127':
    errors.append(f'obj-pv2-pgsplit: expected "split 0 127", got '
                  f'{box_by_id["obj-pv2-pgsplit"]["text"]!r}')
slotmenu_items = box_by_id['obj-pv2-slotmenu'].get('items', [])
n_slot_items = sum(1 for it in slotmenu_items if it != ',') // 2  # each item is "Preset" "N"
if n_slot_items != 128:
    errors.append(f'obj-pv2-slotmenu: expected 128 placeholder items, found {n_slot_items}')
for dead in ('obj-c34-namecoll', 'obj-c34-slotshadow-restore', 'obj-c34-namet',
            'obj-c34-slot1-name', 'obj-c34-nameedit-outmode', 'obj-c34-rebuild-prependset',
            'obj-c34-refresh-t', 'obj-c34-clearopen', 'obj-c34-gate', 'obj-c34-gateclose',
            'obj-c34-slotname-notzero', 'obj-c34-slotname-minus1', 'obj-c34-slotname-sprintf',
            'obj-c34-slotname-zljoin'):
    if dead in box_by_id:
        errors.append(f'{dead} should no longer exist (replaced by the capture/rebuild design)')

# namecache: 128 embedded default entries (1-128), always found on lookup
# even for slots pattrstorage has never reported
namecache = box_by_id.get('obj-c34-namecache')
if namecache is None:
    errors.append('obj-c34-namecache not found')
else:
    cd = namecache.get('coll_data', {})
    if cd.get('count') != 128 or len(cd.get('data', [])) != 128:
        errors.append(f'obj-c34-namecache: expected 128 embedded entries, found {cd.get("count")}')
    keys = {row['key'] for row in cd.get('data', [])}
    if keys != set(range(1, 129)):
        errors.append('obj-c34-namecache: keys are not exactly 1..128')

# textedit: keymode via message (creation-time attribute didn't take effect;
# confirmed fixed -- Return now commits) + outputmode 1 as a creation
# attribute (matches the user's own working reference patch) -- but route
# text is STILL required regardless of outputmode, since textedit prepends
# its "text" selector unconditionally (confirmed both by Max forum threads
# and by the reference patch, which also uses route text despite outputmode 1)
if box_by_id.get('obj-c34-nameedit', {}).get('outputmode') != 1:
    errors.append('obj-c34-nameedit: expected outputmode=1')
# textedit ALWAYS has 4 outlets (confirmed against the reference patch's own
# obj-224) -- an earlier build here wrongly declared numoutlets=1, a genuine
# box-definition mismatch for this maxclass, found after the user reported
# the whole preset system (including previously-working SAVE) went dead
nameedit_box = box_by_id.get('obj-c34-nameedit', {})
if nameedit_box.get('numoutlets') != 4 or nameedit_box.get('outlettype') != ['', 'int', '', '']:
    errors.append(f'obj-c34-nameedit: expected numoutlets=4, outlettype=["","int","",""], '
                  f'got numoutlets={nameedit_box.get("numoutlets")}, '
                  f'outlettype={nameedit_box.get("outlettype")}')
msg_box = box_by_id.get('obj-c34-nameedit-keymode')
if msg_box is None or msg_box['text'] != 'keymode 1':
    errors.append(f'obj-c34-nameedit-keymode: expected "keymode 1", got '
                  f'{msg_box and msg_box["text"]!r}')
if (('obj-c34-nameedit-lb', 0), ('obj-c34-nameedit-keymode', 0)) not in conn or \
   (('obj-c34-nameedit-keymode', 0), ('obj-c34-nameedit', 0)) not in conn:
    errors.append('missing obj-c34-nameedit-lb -> keymode msg -> nameedit chain')
if box_by_id.get('obj-c34-route-text', {}).get('text') != 'route text':
    errors.append('obj-c34-route-text missing or not "route text"')
if (('obj-c34-nameedit', 0), ('obj-c34-route-text', 0)) not in conn:
    errors.append('missing obj-c34-nameedit -> obj-c34-route-text')

# rename-send: pack s i (hot=text, cold=continuously-tracked slot#) reordered
# via a message box into pattrstorage's own "slotname <n> <name>" syntax,
# sent directly into obj-pv2-pattrstorage (mirrors the reference patch's
# obj-22/obj-13/obj-30 exactly)
if box_by_id.get('obj-c34-namepack', {}).get('text') != 'pack s i':
    errors.append('obj-c34-namepack should be "pack s i"')
if box_by_id.get('obj-c34-namemsg', {}).get('text') != 'slotname $2 $1':
    errors.append('obj-c34-namemsg should be the message "slotname $2 $1"')
# +1: obj-c34-slotname-notzero filters pattrstorage's slot 0 out of the
# rebuilt menu, so the umenu's own item positions no longer line up 1:1
# with real pattrstorage slot numbers -- every visible item is shifted
# down by the one slot that was omitted. Confirmed by Max testing: without
# this offset, renaming targeted the slot immediately BEFORE the one
# actually selected.
if box_by_id.get('obj-c34-slot1', {}).get('text') != '+ 1':
    errors.append('obj-c34-slot1 should be "+ 1" (compensates for the slot-0 filter -- see comment in build script)')
required_rename_chain = [
    (('obj-pv2-slotmenu', 0), ('obj-c34-slot1', 0)),
    (('obj-c34-route-text', 0), ('obj-c34-namepack', 0)),
    (('obj-c34-slot1', 0), ('obj-c34-namepack', 1)),
    (('obj-c34-namepack', 0), ('obj-c34-namemsg', 0)),
    (('obj-c34-namemsg', 0), ('obj-c34-name-t', 0)),
    (('obj-c34-name-t', 1), ('obj-pv2-pattrstorage', 0)),
    (('obj-c34-name-t', 0), ('obj-c34-getslotnamelist', 0)),
    (('obj-c34-name-t', 2), ('obj-c34-nameedit-clear', 0)),
    (('obj-c34-nameedit-clear', 0), ('obj-c34-nameedit', 0)),
]
if box_by_id.get('obj-c34-name-t', {}).get('text') != 't b l b':
    errors.append('obj-c34-name-t should be "t b l b" (clears the textbox after rename)')
if box_by_id.get('obj-c34-nameedit-clear', {}).get('text') != 'clear':
    errors.append('obj-c34-nameedit-clear should be the message "clear"')
for src, dst in required_rename_chain:
    if (src, dst) not in conn:
        errors.append(f'missing rename wire: {src} -> {dst}')

# refresh now just means "ask pattrstorage for its slot-name list" -- no
# clearing/gating happens at trigger time anymore (that's driven later, off
# the reply stream itself). Shared by loadbang, the post-rename trigger
# above, and SAVE (obj-pv2-save-t extended t b b -> t b b b, same technique
# already used in Control-33 for obj-pv2-rcl-post-t -- the reference
# patch's classic grid `preset` object refreshes its menu automatically on
# store; this patch has no equivalent, so SAVE must trigger it explicitly)
if box_by_id['obj-pv2-save-t']['text'] != 't b b b':
    errors.append(f'obj-pv2-save-t: expected "t b b b", got '
                  f'{box_by_id["obj-pv2-save-t"]["text"]!r}')
required_refresh_chain = [
    (('obj-c34-lb2', 0), ('obj-c34-getslotnamelist', 0)),
    (('obj-pv2-save-t', 0), ('obj-c34-getslotnamelist', 0)),
    (('obj-pv2-save-t', 1), ('obj-pv2-store-msg', 0)),
    (('obj-pv2-save-t', 2), ('obj-pv2-slotmenu', 0)),
    (('obj-c34-getslotnamelist', 0), ('obj-pv2-pattrstorage', 0)),
]
for src, dst in required_refresh_chain:
    if (src, dst) not in conn:
        errors.append(f'missing refresh wire: {src} -> {dst}')
if box_by_id.get('obj-c34-getslotnamelist', {}).get('text') != 'getslotnamelist':
    errors.append('obj-c34-getslotnamelist should be the message "getslotnamelist"')

# CAPTURE: route slotname -> route done -> unmatched "<n> <name>" -> unpack
# -> zl.join builds [n, name...] -> write into namecache (no menu contact
# at all in this phase)
if (('obj-pv2-pattrstorage', 0), ('obj-c34-slotname-route', 0)) not in conn:
    errors.append('missing obj-pv2-pattrstorage -> obj-c34-slotname-route tap')
required_capture_chain = [
    (('obj-c34-slotname-route', 0), ('obj-c34-slotname-done', 0)),
    (('obj-c34-slotname-done', 1), ('obj-c34-slotname-unpack', 0)),
    (('obj-c34-slotname-unpack', 1), ('obj-c34-cache-zljoin', 1)),
    (('obj-c34-slotname-unpack', 0), ('obj-c34-cache-zljoin', 0)),
    (('obj-c34-cache-zljoin', 0), ('obj-c34-namecache', 0)),
]
for src, dst in required_capture_chain:
    if (src, dst) not in conn:
        errors.append(f'missing capture wire: {src} -> {dst}')

# REBUILD: pattrstorage's "slotname done" (capture finished) -> clear ->
# uzi 128 -> per-slot lookup in namecache + PC-prefix sprintf + zl.join ->
# slotmenu; uzi's OWN completion bang (not "slotname done" directly)
# restores the visible selection, guaranteeing all 128 appends land first
required_rebuild_chain = [
    (('obj-c34-slotname-done', 0), ('obj-c34-rebuild-t', 0)),
    (('obj-c34-rebuild-t', 1), ('obj-c34-clear-msg', 0)),
    (('obj-c34-clear-msg', 0), ('obj-pv2-slotmenu', 0)),
    (('obj-c34-rebuild-t', 0), ('obj-c34-rebuild-uzi', 0)),
    (('obj-c34-rebuild-uzi', 2), ('obj-c34-rebuild-split', 0)),
    (('obj-c34-rebuild-split', 1), ('obj-c34-namecache', 0)),
    (('obj-c34-rebuild-split', 0), ('obj-c34-rebuild-minus1', 0)),
    (('obj-c34-rebuild-minus1', 0), ('obj-c34-rebuild-sprintf', 0)),
    (('obj-c34-namecache', 0), ('obj-c34-rebuild-zljoin', 1)),
    (('obj-c34-rebuild-sprintf', 0), ('obj-c34-rebuild-zljoin', 0)),
    (('obj-c34-rebuild-zljoin', 0), ('obj-pv2-slotmenu', 0)),
    (('obj-c34-rebuild-uzi', 1), ('obj-c34-slotshadow', 0)),
]
for src, dst in required_rebuild_chain:
    if (src, dst) not in conn:
        errors.append(f'missing rebuild wire: {src} -> {dst}')
if box_by_id.get('obj-c34-rebuild-uzi', {}).get('text') != 'uzi 128':
    errors.append('obj-c34-rebuild-uzi should be "uzi 128" (base defaults to 1)')
if box_by_id.get('obj-c34-rebuild-sprintf', {}).get('text') != 'sprintf append PC%ld -':
    errors.append('obj-c34-rebuild-sprintf should be "sprintf append PC%ld -"')

print(f'{target}')
print(f'  boxes: {len(boxes)}, lines: {len(lines)}')
print(f'  bg client objects: {n_bg}, hw-holders: {n_hwh}, display shadows: {n_sh}')
print()
if errors:
    print(f'ERRORS ({len(errors)}):')
    for e in errors:
        print(f'  - {e}')
else:
    print('No structural errors found.')
if warnings:
    print(f'WARNINGS ({len(warnings)}):')
    for w in warnings:
        print(f'  - {w}')

sys.exit(1 if errors else 0)
