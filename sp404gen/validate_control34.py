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

# 11. 128 presets: slotmenu must have 128 items, PC split must cover 0-127,
#     and the rename/rebuild machinery must be present and wired
if box_by_id['obj-pv2-pgsplit']['text'] != 'split 0 127':
    errors.append(f'obj-pv2-pgsplit: expected "split 0 127", got '
                  f'{box_by_id["obj-pv2-pgsplit"]["text"]!r}')
slotmenu_items = box_by_id['obj-pv2-slotmenu'].get('items', [])
n_slot_items = sum(1 for it in slotmenu_items if it != ',') // 2  # each item is "Preset" "N"
if n_slot_items != 128:
    errors.append(f'obj-pv2-slotmenu: expected 128 items, found {n_slot_items}')
namecoll = box_by_id.get('obj-c34-namecoll')
if namecoll is None:
    errors.append('obj-c34-namecoll not found')
else:
    cd = namecoll.get('coll_data', {})
    if cd.get('count') != 128 or len(cd.get('data', [])) != 128:
        errors.append(f'obj-c34-namecoll: expected 128 embedded entries, found {cd.get("count")}')
    keys = {row['key'] for row in cd.get('data', [])}
    if keys != set(range(1, 129)):
        errors.append('obj-c34-namecoll: keys are not exactly 1..128')
required_rename_chain = [
    (('obj-c34-nameedit', 0), ('obj-c34-namet', 0)),
    (('obj-c34-namet', 2), ('obj-c34-namepack', 1)),
    (('obj-c34-namet', 1), ('obj-c34-slotshadow', 0)),
    (('obj-c34-slot1-name', 0), ('obj-c34-namepack', 0)),
    (('obj-c34-namepack', 0), ('obj-c34-namecoll', 0)),
    (('obj-c34-namet', 0), ('obj-c34-rebuild-t', 0)),
    (('obj-c34-rebuild-t', 1), ('obj-c34-clear-msg', 0)),
    (('obj-c34-clear-msg', 0), ('obj-pv2-slotmenu', 0)),
    (('obj-c34-rebuild-t', 0), ('obj-c34-rebuild-uzi', 0)),
    (('obj-c34-rebuild-uzi', 2), ('obj-c34-rebuild-split', 0)),
    (('obj-c34-rebuild-split', 1), ('obj-c34-rebuild-minus1', 0)),
    (('obj-c34-rebuild-minus1', 0), ('obj-c34-rebuild-sprintf', 0)),
    (('obj-c34-rebuild-sprintf', 0), ('obj-c34-rebuild-prependset', 1)),
    (('obj-c34-rebuild-split', 0), ('obj-c34-namecoll', 0)),
    (('obj-c34-namecoll', 0), ('obj-c34-rebuild-prependset', 0)),
    (('obj-c34-rebuild-prependset', 0), ('obj-pv2-slotmenu', 0)),
    (('obj-c34-rebuild-uzi', 1), ('obj-c34-slotshadow-restore', 0)),
    (('obj-c34-slotshadow-restore', 0), ('obj-c34-restore-pset', 0)),
    (('obj-c34-restore-pset', 0), ('obj-pv2-slotmenu', 0)),
]
for src, dst in required_rename_chain:
    if (src, dst) not in conn:
        errors.append(f'missing rename/rebuild wire: {src} -> {dst}')

# rebuild's sprintf must include the literal "append" selector -- without it,
# every rebuilt umenu item is an unrecognized message and gets silently
# dropped, leaving slotmenu with 0 items (the "umenu completely unresponsive"
# bug found in the first Control-34 Max test)
sprintf_box = box_by_id.get('obj-c34-rebuild-sprintf')
if sprintf_box is None or not sprintf_box['text'].startswith('sprintf append '):
    errors.append(f'obj-c34-rebuild-sprintf: expected to start with '
                  f'"sprintf append ", got {sprintf_box and sprintf_box["text"]!r}')

# obj-c34-slotshadow (rename fetch) and obj-c34-slotshadow-restore (post-
# rebuild selection restore) must be two DISTINCT objects, each feeding only
# its own consumer -- sharing one shadow's outlet would make every selection
# restore also silently overwrite a namecoll entry with a stale/uninitialized
# name (the cross-talk bug found and fixed alongside the sprintf bug above)
if (('obj-c34-slotshadow', 0), ('obj-c34-restore-pset', 0)) in conn:
    errors.append('obj-c34-slotshadow must not feed obj-c34-restore-pset directly '
                  '(use obj-c34-slotshadow-restore instead)')
if (('obj-c34-slotshadow-restore', 0), ('obj-c34-slot1-name', 0)) in conn:
    errors.append('obj-c34-slotshadow-restore must not feed obj-c34-slot1-name '
                  '(that would fire a spurious namecoll store on every rebuild)')

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
