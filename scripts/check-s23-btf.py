#!/usr/bin/env python3
"""Reject BTF DATASEC layouts that Linux 5.15 refuses during boot.

bpftool can dump structurally readable BTF that the in-kernel metadata
validator rejects. Mirror btf_datasec_check_meta's variable-range checks.
This gate supplements, rather than replaces, the kernel's full verifier.
Usage: check-s23-btf.py BTF_JSON REPORT_JSON
"""
import hashlib
import json
from pathlib import Path
import sys

source, destination = map(Path, sys.argv[1:])
raw = source.read_bytes()
types = json.loads(raw)['types']
by_id = {t['id']: t for t in types}
errors = []
count = 0
supported = {'INT', 'PTR', 'ARRAY', 'STRUCT', 'UNION', 'ENUM', 'FWD',
             'TYPEDEF', 'VOLATILE', 'CONST', 'RESTRICT', 'FUNC', 'FUNC_PROTO',
             'VAR', 'DATASEC', 'FLOAT'}
for t in types:
    if t['kind'] not in supported:
        errors.append(f"type {t['id']}: unsupported kind {t['kind']}")
    if t['kind'] != 'DATASEC':
        continue
    end = total = 0
    if not t['name'] or t['size'] <= 0:
        errors.append(f"DATASEC {t['id']}: invalid name/size")
    for var in t['vars']:
        count += 1
        offset, size = var['offset'], var['size']
        target = by_id.get(var['type_id'], {})
        if (target.get('kind') != 'VAR' or offset < end or
                offset >= t['size'] or size <= 0 or
                offset + size > t['size']):
            errors.append(f"{t['name']}: invalid/overlapping variable {var}")
        end = offset + size
        total += size
    if total > t['size']:
        errors.append(f"{t['name']}: sum of variable sizes exceeds section")
result = dict(passed=not errors, type_count=len(types),
              datasec_variables_checked=count, errors=errors,
              btf_json_sha256=hashlib.sha256(raw).hexdigest())
destination.write_text(json.dumps(result, indent=2) + '\n')
print(f"BTF metadata: {len(types)} types, {count} variables, "
      f"{len(errors)} errors")
if errors:
    print(errors[0], file=sys.stderr)
sys.exit(bool(errors))
