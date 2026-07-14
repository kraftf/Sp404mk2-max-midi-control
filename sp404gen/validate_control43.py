"""
Validates Roland_SP404MK2_Control-43.maxpat: the pattrstorage-async-restore
timing fix for hardware dispatch (see build_control43.py's module
docstring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-43.maxpat')

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

check('obj-pv42-dbg-print-hwefx' not in box_by_id,
      'Control-42 debug print should have been removed')

pipe = box_by_id.get('obj-pv43-hwdispatch-pipe')
check(pipe is not None, 'obj-pv43-hwdispatch-pipe missing')
check(pipe['text'] == 'pipe 500', f'obj-pv43-hwdispatch-pipe wrong text: {pipe["text"]!r}')

check(outgoing('obj-pv2-rcl-post-t', 2) == [('obj-pv43-hwdispatch-pipe', 0)],
      'rcl-post-t outlet2 (hw-dispatch trigger) should feed the new pipe, not efx-uzi directly')
check(outgoing('obj-pv43-hwdispatch-pipe', 0) == [('obj-pv39-hw-efx-uzi', 0)],
      'the pipe should feed efx-uzi (unchanged downstream chain)')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
