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
target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'Roland_SP404MK2_Control-33.maxpat')

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

# 7. presets companion-file messages must reference the Control-33 filename
for bid, expected in (('obj-pv2-read-msg', 'read "Control33_presets.json"'),
                      ('obj-pv2-write-msg', 'write "Control33_presets.json"')):
    box = box_by_id.get(bid)
    if box is None:
        errors.append(f'{bid} not found')
    elif box['text'] != expected:
        errors.append(f'{bid}: text {box["text"]!r} != {expected!r}')

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
