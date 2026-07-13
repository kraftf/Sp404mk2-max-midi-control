"""
Structural validator for Roland_SP404MK2_Control-35.maxpat.
Checks the changes made by build_control35.py:
  1. Dedicated Program Change input port (independent device selector).
  2. CC-mapping preset system (16 slots: umenu + SAVE/RECALL + rename),
     built on two explicit colls rather than a second pattrstorage.
Also does generic structural sanity checks (unique ids, no dangling lines).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-35.maxpat')

errors = []

def check(cond, msg):
    if not cond:
        errors.append(msg)

with open(PATCH) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

# --- generic structural sanity ---
ids = [b['box']['id'] for b in boxes]
check(len(ids) == len(set(ids)), f'duplicate box ids found: {len(ids)} boxes, {len(set(ids))} unique')
for l in lines:
    pl = l['patchline']
    src, dst = pl['source'][0], pl['destination'][0]
    check(src in box_by_id, f'dangling line source: {src}')
    check(dst in box_by_id, f'dangling line destination: {dst}')

def outgoing(src_id, src_out=None):
    res = []
    for l in lines:
        pl = l['patchline']
        if pl['source'][0] == src_id and (src_out is None or pl['source'][1] == src_out):
            res.append(tuple(pl['destination']))
    return res

def incoming(dst_id, dst_in=None):
    res = []
    for l in lines:
        pl = l['patchline']
        if pl['destination'][0] == dst_id and (dst_in is None or pl['destination'][1] == dst_in):
            res.append(tuple(pl['source']))
    return res

# =====================================================================
# 0. Presets filename
# =====================================================================
check(box_by_id['obj-pv2-read-msg']['text'] == 'read "Control35_presets.json"',
      'presets read message not updated to Control35')
check(box_by_id['obj-pv2-write-msg']['text'] == 'write "Control35_presets.json"',
      'presets write message not updated to Control35')

# =====================================================================
# 1. Dedicated Program Change input port
# =====================================================================
check('obj-c35-pcindev' in box_by_id, 'obj-c35-pcindev missing')
check(box_by_id['obj-c35-pcindev']['maxclass'] == 'umenu', 'obj-c35-pcindev not a umenu')
check(box_by_id['obj-c35-pcindev']['items'] == box_by_id['obj-4']['items'],
      'obj-c35-pcindev items do not match obj-4 (MIDI device list)')
check(box_by_id['obj-c35-pcindev'].get('presentation') == 1,
      'obj-c35-pcindev not presentation-visible')

check('obj-c35-pc-pport' in box_by_id and box_by_id['obj-c35-pc-pport']['text'] == 'prepend port',
      'obj-c35-pc-pport missing or wrong text')
check(outgoing('obj-c35-pcindev', 1) == [('obj-c35-pc-pport', 0)],
      'pcindev outlet1 -> pc-pport wiring wrong')
check(outgoing('obj-c35-pc-pport', 0) == [('obj-pv2-pgmin', 0)],
      'pc-pport -> pgmin wiring wrong')
check(incoming('obj-pv2-pgmin', 0) == [('obj-c35-pc-pport', 0)],
      'obj-pv2-pgmin should have exactly one incoming connection, from pc-pport')
check(box_by_id['obj-pv2-pgmin']['text'] == 'pgmin', 'obj-pv2-pgmin text changed unexpectedly')

# obj-c34-indev (CC input device selector) must be untouched/independent
check(incoming('obj-c34-ctlin', 0) == [('obj-c34-in-pport', 0)],
      'obj-c34-ctlin wiring was disturbed -- CC input selector must stay independent')

# =====================================================================
# 2. CC-mapping preset system
# =====================================================================
N_CC_SLOTS = 16
CC_TARGETS = ['ctrl1', 'ctrl2', 'ctrl3', 'ctrl4', 'ctrl5', 'ctrl6', 'efxsel', 'onoff']
CC_DEFAULTS = [16, 17, 18, 80, 81, 82, 83, 19]

check('obj-c35-ccmenu' in box_by_id, 'obj-c35-ccmenu missing')
ccmenu_items = box_by_id['obj-c35-ccmenu']['items']
check(ccmenu_items.count(',') == N_CC_SLOTS - 1,
      f'obj-c35-ccmenu should have {N_CC_SLOTS} placeholder items')

for name in CC_TARGETS:
    check(f'obj-c34-ccsel-{name}' in box_by_id, f'obj-c34-ccsel-{name} missing (from Control-34)')

# --- colls ---
ccvalues = box_by_id['obj-c35-ccvalues']
check(ccvalues['text'] == 'coll obj-c35-ccvalues @embed 1', 'obj-c35-ccvalues text wrong')
cd = ccvalues['coll_data']
check(cd['count'] == N_CC_SLOTS, 'obj-c35-ccvalues count wrong')
keys = sorted(e['key'] for e in cd['data'])
check(keys == list(range(1, N_CC_SLOTS + 1)), 'obj-c35-ccvalues keys not exactly 1..16')
for e in cd['data']:
    check(e['value'] == CC_DEFAULTS, f'obj-c35-ccvalues[{e["key"]}] default value wrong: {e["value"]}')

ccnames = box_by_id['obj-c35-ccnames']
check(ccnames['text'] == 'coll obj-c35-ccnames @embed 1', 'obj-c35-ccnames text wrong')
cd2 = ccnames['coll_data']
check(cd2['count'] == N_CC_SLOTS, 'obj-c35-ccnames count wrong')
keys2 = sorted(e['key'] for e in cd2['data'])
check(keys2 == list(range(1, N_CC_SLOTS + 1)), 'obj-c35-ccnames keys not exactly 1..16')
for e in cd2['data']:
    check(e['value'] == ['Config', str(e['key'])], f'obj-c35-ccnames[{e["key"]}] default value wrong: {e["value"]}')

# --- textedit schema (must match the proven Control-34 recipe exactly) ---
nameedit = box_by_id['obj-c35-ccnameedit']
check(nameedit['maxclass'] == 'textedit', 'obj-c35-ccnameedit not a textedit')
check(nameedit['numoutlets'] == 4, 'obj-c35-ccnameedit numoutlets != 4')
check(nameedit['outlettype'] == ['', 'int', '', ''], 'obj-c35-ccnameedit outlettype wrong')
check(nameedit.get('outputmode') == 1, 'obj-c35-ccnameedit outputmode != 1')
check(outgoing('obj-c35-ccnameedit-lb', 0) == [('obj-c35-ccnameedit-keymode', 0)],
      'ccnameedit keymode loadbang chain wrong')
check(outgoing('obj-c35-ccnameedit-keymode', 0) == [('obj-c35-ccnameedit', 0)],
      'ccnameedit keymode message not wired to nameedit')
check(outgoing('obj-c35-ccnameedit', 0) == [('obj-c35-ccroute-text', 0)],
      'ccnameedit not routed through route text')

# --- SAVE chain: outlets 8..1 (right-to-left) hit ccsel boxes in
#     CC_TARGETS order, feeding savepack cold inlets 8..1; outlet0 (last)
#     fetches slot via shadow+1 into savepack's hot inlet 0 ---
save_t = box_by_id['obj-c35-save-t']
check(save_t['text'] == 't b b b b b b b b b b', 'obj-c35-save-t wrong text/outlet count (should be 10)')
check(outgoing('obj-c35-ccsavebtn', 0) == [('obj-c35-save-t', 0)], 'SAVE button not wired to save-t')
for i, name in enumerate(CC_TARGETS):
    out_index = i + 1
    pack_inlet = i + 1
    ccsel_id = f'obj-c34-ccsel-{name}'
    check((ccsel_id, 0) in outgoing('obj-c35-save-t', out_index),
          f'save-t outlet {out_index} should bang {ccsel_id}')
    check(('obj-c35-savepack', pack_inlet) in outgoing(ccsel_id, 0),
          f'{ccsel_id} outlet0 should feed savepack inlet {pack_inlet}')
check(outgoing('obj-c35-save-t', 0) == [('obj-c35-ccshadow-save', 0)],
      'save-t outlet0 (last) should fetch the save shadow')
check(outgoing('obj-c35-ccshadow-save', 0) == [('obj-c35-save-slotplus1', 0)],
      'ccshadow-save not wired to save-slotplus1')
check(sorted(outgoing('obj-c35-save-slotplus1', 0)) ==
      sorted([('obj-c35-savepack', 0), ('obj-c35-savedev-zljoin', 0)]),
      'save-slotplus1 should feed BOTH savepack HOT inlet 0 AND savedev-zljoin HOT inlet 0')
check(outgoing('obj-c35-savepack', 0) == [('obj-c35-ccvalues', 0)],
      'savepack output should write into obj-c35-ccvalues')

# --- SAVE also captures the MIDI Control Input Device by NAME (not index),
#     since the coll for a lookup-by-name recall needs zl.join (not pack)
#     for the identical multi-atom-spillover reason as the rename fix.
#
#     NOT a bare bang into obj-c34-indev: umenu does not document responding
#     to bang at all (append/clear/delete/dictionary/prefix/set/symbol/etc.
#     are documented; bang is not) -- confirmed the hard way, this silently
#     did nothing in the user's real Max test. Uses `value <name>` instead
#     (already proven working elsewhere in this exact patch, e.g. `value
#     dfx_bus12_1_label_cc`), continuously updated from indev's outlet 1 and
#     fetched via bang on SAVE, since Cycling '74's own reference confirms
#     `value` (unlike umenu) does respond to bang with its stored content. ---
devname_value = box_by_id['obj-c35-indevname-value']
check(devname_value['text'] == 'value c35_indevname_shadow', 'obj-c35-indevname-value wrong text')
check(outgoing('obj-c34-indev', 1) and ('obj-c35-indevname-value', 0) in outgoing('obj-c34-indev', 1),
      'obj-c34-indev outlet1 (device name text) should continuously feed obj-c35-indevname-value')
check(outgoing('obj-c35-save-t', 9) == [('obj-c35-indevname-value', 0)],
      'save-t outlet9 (fires first) should bang obj-c35-indevname-value to fetch the current device name')
check(outgoing('obj-c35-indevname-value', 0) == [('obj-c35-savedev-zljoin', 1)],
      'obj-c35-indevname-value output should feed savedev-zljoin cold inlet')
check(outgoing('obj-c35-savedev-zljoin', 0) == [('obj-c35-ccdevice', 0)],
      'savedev-zljoin output should write into obj-c35-ccdevice')

ccdevice = box_by_id['obj-c35-ccdevice']
check(ccdevice['text'] == 'coll obj-c35-ccdevice @embed 1', 'obj-c35-ccdevice text wrong')
cd3 = ccdevice['coll_data']
check(cd3['count'] == N_CC_SLOTS, 'obj-c35-ccdevice count wrong')
keys3 = sorted(e['key'] for e in cd3['data'])
check(keys3 == list(range(1, N_CC_SLOTS + 1)), 'obj-c35-ccdevice keys not exactly 1..16')
for e in cd3['data']:
    check(e['value'] == ['(unset)'], f'obj-c35-ccdevice[{e["key"]}] default value wrong: {e["value"]}')

# --- RECALL chain: unpack outlet i -> ccsel(CC_TARGETS[i]).
#     This must be the SAME index i as SAVE's pack_inlet = i + 1 above --
#     coll stores exactly [v_ctrl1..v_onoff] in CC_TARGETS order (pack's
#     inlet order), so unpack's outlet order must match it atom-for-atom
#     or values silently swap between controls on recall. ---
check(box_by_id['obj-c35-rcl-t']['text'] == 't b', 'obj-c35-rcl-t wrong text')
check(outgoing('obj-c35-ccrclbtn', 0) == [('obj-c35-rcl-t', 0)],
      'RECALL button not wired through rcl-t (a bare "RECALL" symbol into an '
      'int object is exactly the confirmed console error -- must go through a '
      'trigger first, same as SAVE does via save-t)')
check(outgoing('obj-c35-rcl-t', 0) == [('obj-c35-ccshadow-rcl', 0)],
      'rcl-t not wired to ccshadow-rcl')
check(outgoing('obj-c35-ccshadow-rcl', 0) == [('obj-c35-rcl-slotplus1', 0)],
      'ccshadow-rcl not wired to rcl-slotplus1')
check(sorted(outgoing('obj-c35-rcl-slotplus1', 0)) ==
      sorted([('obj-c35-ccvalues', 0), ('obj-c35-ccdevice', 0)]),
      'rcl-slotplus1 should look up BOTH obj-c35-ccvalues AND obj-c35-ccdevice')
check(outgoing('obj-c35-ccvalues', 0) == [('obj-c35-rcl-unpack', 0)],
      'ccvalues lookup output should feed rcl-unpack')
rcl_unpack = box_by_id['obj-c35-rcl-unpack']
check(rcl_unpack['text'] == 'unpack 0 0 0 0 0 0 0 0', 'obj-c35-rcl-unpack wrong text')
for i, name in enumerate(CC_TARGETS):
    ccsel_id = f'obj-c34-ccsel-{name}'
    check((ccsel_id, 0) in outgoing('obj-c35-rcl-unpack', i),
          f'rcl-unpack outlet {i} should dispatch to {ccsel_id}')

# --- RECALL also re-selects the saved MIDI Control Input Device by name ---
check(outgoing('obj-c35-ccdevice', 0) == [('obj-c35-rcl-dev-prepend', 0)],
      'ccdevice lookup output should feed rcl-dev-prepend')
check(box_by_id['obj-c35-rcl-dev-prepend']['text'] == 'prepend symbol',
      'obj-c35-rcl-dev-prepend wrong text')
check(outgoing('obj-c35-rcl-dev-prepend', 0) == [('obj-c34-indev', 0)],
      'rcl-dev-prepend should select obj-c34-indev by name (umenu "symbol" message)')

# --- rename write + rebuild chain ---
# NOT `pack s i` (see build_control35.py's long comment on this): Cycling
# '74's own pack documentation confirms a multi-atom list arriving at one
# inlet spills its extra atoms into SUBSEQUENT inlets, which would silently
# clobber the int-typed slot-number inlet (converted to 0) for any 2+-word
# rename. Uses zl.join instead -- same fix already proven for the 128-preset
# name cache in Control-34.
name_t = box_by_id['obj-c35-ccname-t']
check(name_t['text'] == 't b l b', 'obj-c35-ccname-t wrong text')
check(outgoing('obj-c35-ccroute-text', 0) == [('obj-c35-ccname-t', 0)],
      'ccroute-text should feed ccname-t')
check(outgoing('obj-c35-ccname-t', 2) == [('obj-c35-ccnameedit-clear', 0)],
      'ccname-t outlet2 (first) should clear the textbox')
check(outgoing('obj-c35-ccname-t', 1) == [('obj-c35-ccname-zljoin', 1)],
      'ccname-t outlet1 (second) should store the name into zljoin COLD inlet')
check(outgoing('obj-c35-ccname-t', 0) == [('obj-c35-ccshadow-rename', 0)],
      'ccname-t outlet0 (last) should fetch the rename shadow')
check(outgoing('obj-c35-ccshadow-rename', 0) == [('obj-c35-ccslot1-rename', 0)],
      'ccshadow-rename not wired to ccslot1-rename')
check(outgoing('obj-c35-ccslot1-rename', 0) == [('obj-c35-ccname-zljoin', 0)],
      'ccslot1-rename should feed zljoin HOT inlet (triggers join last, after name is cold-stored)')
check(outgoing('obj-c35-ccname-zljoin', 0) == [('obj-c35-ccname-write-t', 0)],
      'ccname-zljoin output should feed ccname-write-t')
write_t = box_by_id['obj-c35-ccname-write-t']
check(write_t['text'] == 't b l', 'obj-c35-ccname-write-t wrong text')
check(outgoing('obj-c35-ccname-write-t', 1) == [('obj-c35-ccnames', 0)],
      'ccname-write-t outlet1 (first) should write [slot name...] into obj-c35-ccnames')
check(outgoing('obj-c35-ccname-write-t', 0) == [('obj-c35-rebuild-t', 0)],
      'ccname-write-t outlet0 (last) should trigger rebuild, after the write lands')
check(incoming('obj-c35-ccshadow-rename', 1) == [('obj-c35-ccmenu', 0)],
      'ccshadow-rename not cold-tapped from ccmenu')

rebuild_t = box_by_id['obj-c35-rebuild-t']
check(rebuild_t['text'] == 't b b', 'obj-c35-rebuild-t wrong text')
check(sorted(incoming('obj-c35-rebuild-t', 0)) == sorted([('obj-c35-ccname-write-t', 0), ('obj-c35-cc-lb', 0)]),
      'obj-c35-rebuild-t should be fed by both rename (ccname-write-t) and load (cc-lb)')
check(outgoing('obj-c35-rebuild-t', 1) == [('obj-c35-clear-msg', 0)],
      'rebuild-t outlet1 (first) should clear the menu')
check(outgoing('obj-c35-clear-msg', 0) == [('obj-c35-ccmenu', 0)], 'clear-msg not wired to ccmenu')
check(outgoing('obj-c35-rebuild-t', 0) == [('obj-c35-rebuild-uzi', 0)],
      'rebuild-t outlet0 (second) should start the uzi loop')
uzi = box_by_id['obj-c35-rebuild-uzi']
check(uzi['text'] == f'uzi {N_CC_SLOTS}', 'obj-c35-rebuild-uzi wrong repetitions/base')
check(outgoing('obj-c35-rebuild-uzi', 2) == [('obj-c35-rebuild-split', 0)],
      'rebuild-uzi counter not wired to rebuild-split')
check(outgoing('obj-c35-rebuild-split', 1) == [('obj-c35-ccnames', 0)],
      'rebuild-split outlet1 (first) should look up ccnames')
check(outgoing('obj-c35-rebuild-split', 0) == [('obj-c35-rebuild-sprintf', 0)],
      'rebuild-split outlet0 (second) should feed sprintf')
check(box_by_id['obj-c35-rebuild-sprintf']['text'] == 'sprintf append %ld -',
      'obj-c35-rebuild-sprintf wrong text')
check(outgoing('obj-c35-ccnames', 0) == [('obj-c35-rebuild-routesym', 0)],
      'ccnames lookup output should feed rebuild-routesym')
check(sorted(outgoing('obj-c35-rebuild-routesym', 0) + outgoing('obj-c35-rebuild-routesym', 1)) ==
      sorted([('obj-c35-rebuild-zljoin', 1), ('obj-c35-rebuild-zljoin', 1)]),
      'rebuild-routesym both outlets should feed rebuild-zljoin cold inlet')
check(outgoing('obj-c35-rebuild-sprintf', 0) == [('obj-c35-rebuild-zljoin', 0)],
      'rebuild-sprintf should feed rebuild-zljoin HOT inlet')
check(outgoing('obj-c35-rebuild-zljoin', 0) == [('obj-c35-ccmenu', 0)],
      'rebuild-zljoin output should append into ccmenu')
check(outgoing('obj-c35-rebuild-uzi', 1) == [('obj-c35-ccshadow-restore', 0)],
      'rebuild-uzi completion bang should restore selection via ccshadow-restore')

# --- shadows all cold-tapped from ccmenu outlet0, no cross-wiring ---
for shadow in ['obj-c35-ccshadow-save', 'obj-c35-ccshadow-rcl', 'obj-c35-ccshadow-restore',
               'obj-c35-ccshadow-rename']:
    check(incoming(shadow, 1) == [('obj-c35-ccmenu', 0)], f'{shadow} not cold-tapped from ccmenu')
    check(box_by_id[shadow]['text'] == 'int 0', f'{shadow} wrong text')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    sys.exit(1)
else:
    print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
