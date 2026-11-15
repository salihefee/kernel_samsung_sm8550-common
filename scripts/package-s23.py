#!/usr/bin/env python3
"""Package a checked Image using the fsrb/voltage AnyKernel3 installer.

Usage: package-s23.py BUILD_DIR ANYKERNEL_DIR ABI_REPORT OUTPUT.zip
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

build, installer, report, output = map(Path, sys.argv[1:])
audit = json.loads(report.read_text())
if audit['crc_mismatches'] or audit['missing_symbols']:
    raise SystemExit('Refusing to package: vendor module ABI audit failed')
image = build / 'arch/arm64/boot/Image'
data = image.read_bytes()
assert data[56:60] == b'ARM\x64', 'Expected uncompressed arm64 Image'
assert len(data) < 100663296 - 4096, 'Image exceeds S911B boot partition'
config = (build / '.config').read_text()
assert '\nCONFIG_KSU=y\n' in config
release = (build / 'include/config/kernel.release').read_text().strip()

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

manifest = dict(
    device='SM-S911B / dm1q', vendor='S911BXXS8EZA1',
    kernel_release=release,
    kernel_source=(build / 's23-source-commit.txt').read_text().strip(),
    repository_source=git('rev-parse', 'HEAD'),
    kernelsu_source=git('-C', 'KernelSU-Next', 'rev-parse', 'HEAD'),
    kernelsu_version='v3.4.2 / 33355',
    compiler='Google Clang r450784e / 14.0.7',
    optimization=(build / 's23-build-mode.txt').read_text().strip(),
    installer_source=git('-C', str(installer.resolve()), 'rev-parse', 'HEAD'),
    image_sha256=hashlib.sha256(data).hexdigest(),
    module_count=audit['module_count'],
    kernel_import_checks=audit['kernel_import_checks'],
    hardware_boot_tested=False,
)
script = '''### AnyKernel3 -- S23 EZA1 KernelSU Next
properties() { '
kernel.string=S23 Linux 5.15.225 KernelSU Next v3.4.2
kernel.compiler=Google Clang r450784e
kernel.made=salihefee
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=dm1q
device.name2=dm1qxxx
supported.versions=16
supported.patchlevels=
supported.vendorpatchlevels=
'; }
boot_attributes() {
  set_perm_recursive 0 0 755 644 $ramdisk/*;
  set_perm_recursive 0 0 750 750 $ramdisk/init* $ramdisk/sbin;
}
block=/dev/block/bootdevice/by-name/boot;
is_slot_device=0;
ramdisk_compression=auto;
patch_vbmeta_flag=0;
. tools/ak3-core.sh;
model=$(getprop ro.boot.em.model);
[ "$model" = "SM-S911B" ] || abort "Unsupported hardware: $model (requires SM-S911B)";
ui_print "S23 EZA1 / KernelSU Next v3.4.2";
split_boot;
flash_boot;
'''
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for root in ('META-INF', 'tools'):
        for path in sorted((installer / root).rglob('*')):
            if path.is_file():
                archive.write(path, str(path.relative_to(installer)))
    archive.writestr('anykernel.sh', script)
    archive.write(installer / 'LICENSE', 'LICENSE.AnyKernel3')
    archive.write(image, 'Image')
    archive.writestr('build-manifest.json', json.dumps(manifest, indent=2) + '\n')
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    assert hashlib.sha256(archive.read('Image')).hexdigest() == manifest['image_sha256']
output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(output)
