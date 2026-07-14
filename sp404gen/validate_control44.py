"""
Validates Roland_SP404MK2_Control-44.maxpat: corrects Control-43's
misplaced delay so hardware dispatch and display refresh keep their
original relative order (see build_control44.py's module docstring).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.join(HERE, '..', 'Roland_SP404MK2_Control-44.maxpat')

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

check('obj-pv43-hwdispatch-pipe' not in box_by_id,
      "Control-43's misplaced pipe should have been removed")

check(outgoing('obj-pv2-rcl-post-t', 2) == [('obj-pv39-hw-efx-uzi', 0)],
      'rcl-post-t outlet2 (hw-dispatch) should feed efx-uzi directly again, undelayed relative to rcl-post-t')

pipe = box_by_id.get('obj-pv44-postrecall-pipe')
check(pipe is not None, 'obj-pv44-postrecall-pipe missing')
check(pipe['text'] == 'pipe 500', f'obj-pv44-postrecall-pipe wrong text: {pipe["text"]!r}')
check(outgoing('obj-pv2-rcl-defer', 0) == [('obj-pv44-postrecall-pipe', 0)],
      'rcl-defer should feed the new pipe (delaying the WHOLE post-recall sequence, not just hw-dispatch)')
check(outgoing('obj-pv44-postrecall-pipe', 0) == [('obj-pv2-rcl-post-t', 0)],
      'the pipe should feed rcl-post-t, preserving hw-dispatch-before-display-refresh ordering downstream')

if errors:
    print(f'FAILED: {len(errors)} check(s)')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print(f'OK: all checks passed ({len(boxes)} boxes, {len(lines)} lines)')
