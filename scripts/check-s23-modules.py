#!/usr/bin/env python3
"""Compare unmodified Samsung module requirements with kernel Module.symvers.

Requires pyelftools. Usage: check-s23-modules.py FIRMWARE_ROOT BUILD_DIR REPORT
"""
import json
from pathlib import Path
import struct
import sys
from elftools.elf.elffile import ELFFile

firmware, build, report = map(Path, sys.argv[1:4])
ramdisk = Path(sys.argv[4]) if len(sys.argv) > 4 else None
exports = {}
for line in (build / 'Module.symvers').read_text().splitlines():
    crc, name, provider, *_ = line.split()
    exports[name] = (int(crc, 16), provider)

modules = []
stock_exports = {}
roots = [(partition, firmware / partition) for partition in ('system_dlkm', 'vendor_dlkm')]
if ramdisk:
    roots.append(('vendor_boot', ramdisk))
for partition, root in roots:
    for path in sorted(root.rglob('*.ko')):
        name = str(Path(partition) / path.relative_to(root))
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            section = elf.get_section_by_name('__versions')
            data = section.data() if section else b''
            versions = {
                data[i+8:i+64].split(b'\0')[0].decode():
                struct.unpack_from('<Q', data, i)[0]
                for i in range(0, len(data), 64)
            }
            info = elf.get_section_by_name('.modinfo').data().split(b'\0')
            vermagic = next(x.decode().split('=', 1)[1] for x in info
                            if x.startswith(b'vermagic='))
            symtab = elf.get_section_by_name('.symtab')
            for symbol in symtab.iter_symbols():
                if symbol.name.startswith('__ksymtab_'):
                    stock_exports.setdefault(symbol.name[10:], []).append(name)
        modules.append(dict(module=name, vermagic=vermagic, versions=versions))

mismatches, missing, checks = [], [], 0
for module in modules:
    for symbol, expected in module['versions'].items():
        if symbol in exports:
            actual, provider = exports[symbol]
            checks += 1
            if expected != actual:
                mismatches.append(dict(module=module['module'], symbol=symbol,
                                       stock=hex(expected), built=hex(actual),
                                       provider=provider))
        elif symbol not in stock_exports:
            missing.append(dict(module=module['module'], symbol=symbol))

result = dict(module_count=len(modules), kernel_import_checks=checks,
              unique_kernel_imports=len({s for m in modules for s in m['versions']
                                         if s in exports}),
              crc_mismatches=mismatches, missing_symbols=missing,
              modules=modules)
report.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: len(v) if isinstance(v, list) else v
                  for k, v in result.items() if k != 'modules'}))
sys.exit(bool(mismatches or missing))
