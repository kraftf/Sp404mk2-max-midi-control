"""
Validates Roland_SP404MK2_Control-37.maxpat: the main-preset rename fix
(see build_control37.py's module docstring for the bug and the fix).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-37.maxpat')

with open(PATCH) as f:
    data = json.load(f)
boxes = data['patcher']['boxes']
lines = data['patcher']['lines']
box_by_id = {b['box']['id']: b['box'] for b in boxes}

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)

def outgoing(src_id, src_out):
    return [tuple(l['patchline']['destination']) for l in lines
            if l['patchline']['source'] == [src_id, src_out]]

# --- fix 1: namepack is now zl.join, existing wiring untouched ---
namepack = box_by_id['obj-c34-namepack']
check(namepack['text'] == 'zl.join', f'obj-c34-namepack should be zl.join, got {namepack["text"]!r}')
check(namepack['numinlets'] == 2 and namepack['numoutlets'] == 1,
      'obj-c34-namepack inlet/outlet count changed unexpectedly')
check(('obj-c34-namepack', 0) in outgoing('obj-c34-route-text', 0),
      'route-text should still feed namepack hot inlet 0 unchanged')
check(('obj-c34-namepack', 1) in outgoing('obj-c34-slot1', 0),
      'slot1 should still feed namepack cold inlet 1 unchanged')
check(outgoing('obj-c34-namepack', 0) == [('obj-c34-namemsg', 0)],
      'namepack output should still feed namemsg unchanged')

# --- fix 2: direct namecache write at rename-commit time ---
check(box_by_id['obj-c37-namecache-write-t']['text'] == 't b l',
      'obj-c37-namecache-write-t wrong text')
check(('obj-c37-namecache-write-t', 0) in outgoing('obj-c34-route-text', 0),
      'route-text should also feed the new namecache-write-t (same commit event as namepack)')
check(outgoing('obj-c37-namecache-write-t', 1) == [('obj-c37-namecache-write-zljoin', 1)],
      'namecache-write-t outlet1 (SECOND, list) should feed the new zljoin cold inlet')
check(outgoing('obj-c37-namecache-write-t', 0) == [('obj-c34-slotshadow', 0)],
      'namecache-write-t outlet0 (LAST, bang) should bang slotshadow to refetch current slot')
check(('obj-c34-slot1', 0) in outgoing('obj-c34-slotshadow', 0),
      'slotshadow bang-refetch output should feed slot1 (recompute +1)')
check(('obj-c37-namecache-write-zljoin', 0) in outgoing('obj-c34-slot1', 0),
      'slot1 should also feed the new zljoin HOT inlet 0')
check(outgoing('obj-c37-namecache-write-zljoin', 0) == [('obj-c34-namecache', 0)],
      'namecache-write-zljoin output should write directly into obj-c34-namecache')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
