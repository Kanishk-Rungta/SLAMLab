"""Resolve native keyframe timestamps for evaluation, using recorded metadata only.

No ground truth is read, and nothing is returned to any algorithm runtime.
Keyframe IDs and timestamps were recorded independently by their own robots.
"""
import json
from pathlib import Path


def finalize(run):
    run = Path(run)
    files = sorted((run / 'benchmark/robots').glob('bstem*/bench.jsonl'))
    times = {}
    datasets = {}
    ambiguous = set()
    for path in files:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        datasets[path] = rows
        for row in rows:
            if row.get('type') == 'event' and row.get('name') == 'native_keyframe':
                key = (path.parent.name, str(row['key']))
                if key in times and abs(times[key] - row['t']) > 1e-7:
                    ambiguous.add(key)
                times[key] = row['t']
    resolved, missing = 0, 0
    for path, rows in datasets.items():
        changed = False
        for row in rows:
            if row.get('type') != 'loop' or row.get('current_keyframe') is None:
                continue
            current = (path.parent.name, str(row['current_keyframe']))
            matched = (row.get('matched_robot'), str(row.get('matched_keyframe')))
            if current in ambiguous or matched in ambiguous or current not in times or matched not in times:
                missing += 1
                continue
            row.setdefault('detection_time', row['t'])
            row['t'] = times[current]
            row['matched_time'] = times[matched]
            row['timestamp_source'] = 'recorded native robot keyframe metadata'
            resolved += 1
            changed = True
        if changed:
            temporary = path.with_suffix('.tmp.jsonl')
            temporary.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
            temporary.replace(path)
    result = {'resolved_loops': resolved, 'unresolved_loops': missing,
              'ambiguous_keyframes': len(ambiguous), 'ground_truth_used': False}
    (run / 'native_timestamp_resolution.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
