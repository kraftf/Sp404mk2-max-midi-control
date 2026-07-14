"""
Builds Roland_SP404MK2_Control-37.maxpat from Control-36. Fixes a
pre-existing bug in the main (128-slot) preset rename mechanism, reported
by the user after testing Control-36: "renaming the presets only works for
the first 4 presets" -- confirmed to mean the MAIN preset system (not the
16-slot CC-config one), and that presets 5+ simply don't take the new name
at all (not garbled, not applied to the wrong slot -- nothing happens).

ROOT CAUSE: this patch's own module docstring (build_control34.py, section
2) already documents the underlying fact that broke this: pattrstorage's
`getslotnamelist` "only ever reports 0 to the largest stored slot" --
confirmed by this session's own earlier real-Max testing (the old
menu-driven-by-getslotnamelist design got "stuck at PC10"). The rename
display pipeline (obj-c34-namecache, a coll used purely as a local lookup
cache) is populated ONLY from that same getslotnamelist reply stream. So
renaming a slot that has never been SAVEd to yet still sends `slotname N
name` to pattrstorage correctly, but our own namecache -- and therefore the
visible menu, which is rebuilt FROM namecache, not from pattrstorage
directly -- never learns about it, because getslotnamelist doesn't report
never-stored slots. Whatever slots the user happened to SAVE to first (in
this case, apparently slots 1-4) are the only ones whose renames become
visible; every other slot's rename is silently swallowed by this gap.

FIX: write the typed name into obj-c34-namecache directly and synchronously
at rename time, in addition to (not instead of) sending pattrstorage its
own "slotname N name" message -- so the display no longer depends on
pattrstorage ever deciding to report that slot back. Mirrors the exact
"synchronous local coll, no round-trip needed" approach the CC-config
preset system (Control-35) already uses successfully for its own renames.

ALSO FIXED (found while re-reading this code for the above, a known bug
class already fixed once elsewhere but never back-ported here -- flagged
as an open question earlier this session and never confirmed until now):
obj-c34-namepack was still `pack s i`. Per Cycling '74's own pack
documentation (confirmed the same way this was confirmed for the CC-config
rename and the 128-preset namecache write), a multi-atom list arriving at
one inlet spills extra atoms into subsequent inlets -- so a 2+-word preset
name would spill its second word into pack's int-typed slot inlet,
converting it to 0 and silently renaming slot 0 (invisible, outside the
1-128 range) instead of the intended slot. Replaced with `zl.join`, same
fix as the CC-config system. The existing "slotname $2 $1" message box
downstream is unaffected: zl.join's hot-first/cold-second output order
([name, slot]) is identical to what `pack s i` already produced, so no
other wiring changes.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-36.maxpat')
DST = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-37.maxpat')

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

# --- fix 1: pack s i -> zl.join (multi-word name no longer clobbers the
#     slot number). Output order is unchanged (hot/first=name, cold/
#     second=slot), so obj-c34-namemsg ("slotname $2 $1") needs no changes. ---
namepack = box_by_id['obj-c34-namepack']
assert namepack['text'] == 'pack s i', f'obj-c34-namepack: unexpected text {namepack["text"]!r}'
namepack['text'] = 'zl.join'

# --- fix 2: write the typed name into namecache directly at rename time,
#     so the visible menu no longer depends on pattrstorage's
#     getslotnamelist ever reporting a never-stored slot back. ---
assert box_by_id['obj-c34-route-text']['numoutlets'] == 2
assert box_by_id['obj-c34-slot1']['text'] == '+ 1'
assert box_by_id['obj-c34-slotshadow']['text'] == 'int 0'
assert box_by_id['obj-c34-namecache']['text'] == 'coll obj-c34-namecache @embed 1'

add_box({'id': 'obj-c37-namecache-write-t', 'maxclass': 'newobj', 'text': 't b l',
         'numinlets': 1, 'numoutlets': 2, 'outlettype': ['bang', ''],
         'patching_rect': [5300.0, 4700.0, 50.0, 22.0]})
add_line('obj-c34-route-text', 0, 'obj-c37-namecache-write-t', 0)  # same commit event namepack uses

add_box({'id': 'obj-c37-namecache-write-zljoin', 'maxclass': 'newobj', 'text': 'zl.join',
         'numinlets': 2, 'numoutlets': 1, 'outlettype': [''],
         'patching_rect': [5300.0, 4770.0, 60.0, 22.0]})
add_line('obj-c37-namecache-write-t', 1, 'obj-c37-namecache-write-zljoin', 1)  # SECOND: name (cold)

# THIRD/LAST (t is right-to-left): bang the existing slot shadow to
# re-output the currently-selected menu index (confirmed already relied on
# elsewhere in this same file -- obj-c34-rebuild-uzi outlet1 bangs this same
# object for the same reason, to re-derive the current slot on demand), then
# +1 it via the existing obj-c34-slot1 object (safe to feed a second time --
# stateless recomputation of the same value slotmenu already drives it with)
# into the join's HOT inlet, producing [slot, name...] for a direct coll
# write ("index value..." is coll's own write syntax).
add_line('obj-c37-namecache-write-t', 0, 'obj-c34-slotshadow', 0)
add_line('obj-c34-slotshadow', 0, 'obj-c34-slot1', 0)
add_line('obj-c34-slot1', 0, 'obj-c37-namecache-write-zljoin', 0)  # HOT: triggers join
add_line('obj-c37-namecache-write-zljoin', 0, 'obj-c34-namecache', 0)  # write [slot, name...]

with open(DST, 'w') as f:
    json.dump(data, f, indent=1)

print(f'Wrote {DST}: {len(boxes)} boxes, {len(lines)} lines')
