#!/usr/bin/env python3
"""Gate stock vendor-facing USB layouts against the linked kernel's BTF."""
import json
from pathlib import Path
import sys

def load(p):
    types=json.loads(Path(p).read_text())['types']
    return {t['id']:t for t in types}, {t['name']:t for t in types if t['kind']=='STRUCT' and t.get('name')}

def layout(types, t, offset=0):
    out={}
    for member in t.get('members', []):
        name=member['name']; pos=offset+member['bits_offset']
        child=types[member['type_id']]
        if name=='(anon)' and child['kind'] in ('STRUCT','UNION'):
            out.update(layout(types,child,pos))
        elif not name.startswith('android_kabi_reserved'):
            out[name]=(pos,member.get('bitfield_size'))
    return out

old,oldnames=load(sys.argv[1]);new,newnames=load(sys.argv[2]);results=[]
for name in ('dwc3','dwc3_vendor','dwc3_request','usb_gadget','usb_request','usb_ep','usb_gadget_driver','usb_phy','snd_usb_endpoint'):
    a=oldnames[name];b=newnames[name];al=layout(old,a);bl=layout(new,b)
    changes={n:[v,bl.get(n)] for n,v in al.items() if bl.get(n)!=v}
    results.append(dict(name=name,stock_size=a['size'],built_size=b['size'],changed_legacy_offsets=changes,passed=a['size']==b['size'] and not changes))
Path(sys.argv[3]).write_text(json.dumps(results,indent=2)+'\n')
for r in results:print(r['name'],r['stock_size'],r['built_size'],'PASS' if r['passed'] else 'FAIL')
sys.exit(not all(r['passed'] for r in results))
