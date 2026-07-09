"""
Builds Roland_SP404MK2_Control-33.maxpat from Control-32. Two changes:

1. FIX the four broken SYNC-mode-detection expr objects (obj-sync-sl-ex,
   obj-sync-sf-ex, obj-sync-tc-ex, obj-sync-zz-ex). They used expr's C-style
   ternary `($i1 >= 1) ? N : -1`, which Max's expr has never implemented
   (long-standing unfulfilled feature request -- confirmed via Max's own
   forums), so they have silently failed to compile since Control-30:
   Max console error `expr: syntax error ? N : -1` on every load, and the
   SYNC-dependent enum-mode switch (Slicer SPEED / SuperFilter RATE /
   TimeCtrlDly TIME / Zan-Zou TIME named-division display) never worked.
   Rewritten without the ternary as `(($i1 >= 1) * (N+1)) - 1`:
   $i1 >= 1 evaluates to 1 -> (N+1)-1 = N; else 0-1 = -1. Same output
   domain as the ternary intended.
   (SESSION_STATE's "REMAINING OPEN ITEMS" only named sl/sf; tc/zz have the
   identical construct and are fixed here too.)

2. ADD the 5 DirectFX slot-assignment menus (obj-43/84/125/166/207,
   DFX1-DFX5) to the pattrstorage preset system -- the known Control-31/32
   gap ("recall does NOT restore DFX slot assignments").

   Traced wiring (why this port needs NO hardware dispatch): each DFX umenu's
   int outlet feeds ONLY `select 1..42` -> per-effect message boxes -> a
   global `value dfx_bus12_N_label_cc` store, read (via bang) by the per-bus
   label/menu-rebuild machinery. There is no ctlout anywhere in the chain --
   DFX slot assignment is pure UI/label state in this patch, so presets
   restore it in the UI only. No MIDI is ever emitted by this path.

   Mechanism (mirrors the proven pv2 architecture, obj-pv33-* namespace):
   - 5 hidden bg live.menu pattr clients, varname Dfx1..Dfx5, appended to
     the pattrstorage subscribe list (45 names total).
   - Write path: visible DFX umenu outlet 0 -> bg client inlet 0 (bare int:
     live.menu stores AND outputs; its only output destination is a shadow
     int's COLD inlet, so nothing echoes back -- same cold-inlet discipline
     as the pv2 fix for the double-CC bug).
   - Recall path: pattrstorage restores the 5 bg clients (their outputs
     refresh the shadows' cold storage, silent); then the deliberate
     refresh bangs each shadow's HOT inlet -> stored position fires as a
     bare int into the visible umenu's hot inlet 0. That reproduces the
     patch's own loadbang-default path (loadbang -> msg '38' -> obj-43)
     exactly: menu selects the item AND fires its outlet, so the
     select -> message -> value chain re-derives dfx_bus12_N_label_cc.
   - Recall ordering: obj-pv2-rcl-post-t is rebuilt from `t b b` to
     `t b b b`. Right-to-left firing preserved: outlet 2 (FIRST) -> hw
     dispatch uzi (unchanged behavior, was outlet 1); outlet 1 (SECOND) ->
     bang the 5 DFX shadows, so the dfx_* value stores are correct BEFORE
     outlet 0 (LAST) -> current-bus display refresh, whose effect-menu
     label rebuild reads those value stores.

Also renames the presets companion file to Control33_presets.json (read and
write messages) to match the patch version. An existing Control32_presets.json
can be migrated by renaming the file -- the pattrstorage format is unchanged,
old files simply lack the Dfx1-5 fields (recall then leaves DFX menus as-is).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-32.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-33.maxpat')

with open(SRC) as f:
    data = json.load(f)
p = data['patcher']
boxes = p['boxes']
lines = p['lines']

box_by_id = {b['box']['id']: b['box'] for b in boxes}

def add_box(box):
    boxes.append({'box': box})

def add_line(src_id, src_out, dst_id, dst_in):
    lines.append({'patchline': {'source': [src_id, src_out],
                                'destination': [dst_id, dst_in]}})

# =====================================================================
# 1. Fix the four ternary exprs (ternary was never valid expr syntax)
# =====================================================================
SYNC_EXPR_FIX = {
    # box id            (broken text,                     synced etid)
    'obj-sync-sl-ex': ('expr ($i1 >= 1) ? 32 : -1', 32),  # Slicer SPEED
    'obj-sync-sf-ex': ('expr ($i1 >= 1) ? 32 : -1', 32),  # SuperFilter RATE
    'obj-sync-tc-ex': ('expr ($i1 >= 1) ? 33 : -1', 33),  # TimeCtrlDly TIME
    'obj-sync-zz-ex': ('expr ($i1 >= 1) ? 34 : -1', 34),  # Zan-Zou TIME
}
for bid, (old_text, etid) in SYNC_EXPR_FIX.items():
    box = box_by_id[bid]
    assert box['text'] == old_text, f'{bid}: unexpected text {box["text"]!r}'
    box['text'] = f'expr (($i1 >= 1) * {etid + 1}) - 1'

# =====================================================================
# 2. Presets companion file rename (32 -> 33)
# =====================================================================
PRESETS_FILENAME = 'Control33_presets.json'
assert box_by_id['obj-pv2-read-msg']['text'] == 'read "Control32_presets.json"'
assert box_by_id['obj-pv2-write-msg']['text'] == 'write "Control32_presets.json"'
box_by_id['obj-pv2-read-msg']['text'] = f'read "{PRESETS_FILENAME}"'
box_by_id['obj-pv2-write-msg']['text'] = f'write "{PRESETS_FILENAME}"'

# =====================================================================
# 3. DFX slot assignments into the preset system (obj-pv33-*)
# =====================================================================
DFX_SLOTS = [1, 2, 3, 4, 5]
DFX_VISIBLE = {1: 'obj-43', 2: 'obj-84', 3: 'obj-125', 4: 'obj-166', 5: 'obj-207'}
DFX_ITEM_COUNT = 43  # OFF + 42 effects, verified against the visible umenus
GENERIC_DFX_ITEMS = [f'E{i}' for i in range(DFX_ITEM_COUNT)]  # placeholder text; only index is ever read

add_box({'id': 'obj-pv33-cmt-main', 'maxclass': 'comment',
         'text': 'DFX PRESET EXTENSION (Control-33): 5 hidden pattr clients Dfx1-5 mirror the '
                 'DFX slot menus. UI-only restore -- the DFX chain has no MIDI out at all. '
                 'See SESSION_STATE.md "Control-33".',
         'patching_rect': [40.0, 3800.0, 700.0, 20.0]})

for n in DFX_SLOTS:
    bg_id = f'obj-pv33-bg-dfx{n}'
    sh_id = f'obj-pv33-sh-dfx{n}'
    varname = f'Dfx{n}'
    x = 40.0 + (n - 1) * 160.0
    add_box({
        'id': bg_id, 'maxclass': 'live.menu', 'varname': varname,
        'numinlets': 1, 'numoutlets': 2, 'outlettype': ['', 'float'],
        'parameter_enable': 1, 'items': GENERIC_DFX_ITEMS,
        'patching_rect': [x, 3840.0, 120.0, 22.0],
        'saved_attribute_attributes': {'valueof': {
            'parameter_longname': varname, 'parameter_shortname': varname,
            'parameter_type': 2, 'parameter_enum': GENERIC_DFX_ITEMS,
            'parameter_initial': [0.0]}},
    })
    add_box({'id': sh_id, 'maxclass': 'newobj', 'text': 'int 0',
             'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
             'patching_rect': [x, 3880.0, 40.0, 22.0]})
    # write path: visible menu -> bg client (stores AND outputs; output only
    # reaches the shadow's cold inlet, so no echo back into the UI)
    add_line(DFX_VISIBLE[n], 0, bg_id, 0)
    add_line(bg_id, 0, sh_id, 1)          # continuous tap -> COLD inlet: store silently
    # deliberate refresh: shadow HOT inlet is banged post-recall (section 4);
    # bare int into the visible umenu's hot inlet = the loadbang-default path
    # (selects item AND fires outlet -> select -> msg -> value store rebuilt)
    add_line(sh_id, 0, DFX_VISIBLE[n], 0)

# subscribe list: append Dfx1..Dfx5
sub_msg = box_by_id['obj-pv2-sub-msg']
assert sub_msg['text'].startswith('subscribe Bus1_efx')
sub_msg['text'] = sub_msg['text'] + ' ' + ' '.join(f'Dfx{n}' for n in DFX_SLOTS)

# =====================================================================
# 4. Post-recall sequencing: t b b -> t b b b
#    out2 (FIRST): hw dispatch (unchanged, was out1)
#    out1 (SECOND): DFX UI restore (bang the 5 shadows; order among the 5
#                   is irrelevant -- independent slots, no MIDI)
#    out0 (LAST):  current-bus display refresh (unchanged) -- must stay
#                  last so its effect-menu label rebuild reads the freshly
#                  restored dfx_bus12_N_label_cc value stores
# =====================================================================
post_t = box_by_id['obj-pv2-rcl-post-t']
assert post_t['text'] == 't b b'
post_t['text'] = 't b b b'
post_t['numoutlets'] = 3
post_t['outlettype'] = ['', '', '']

remapped_hw = 0
for l in lines:
    pl = l['patchline']
    if pl['source'] == ['obj-pv2-rcl-post-t', 1] and pl['destination'] == ['obj-pv2-hw-uzi', 0]:
        pl['source'] = ['obj-pv2-rcl-post-t', 2]
        remapped_hw += 1
assert remapped_hw == 1, f'expected exactly 1 hw-uzi line to remap, got {remapped_hw}'

for n in DFX_SLOTS:
    add_line('obj-pv2-rcl-post-t', 1, f'obj-pv33-sh-dfx{n}', 0)

# =====================================================================
with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
