# Galaxy S23 / EZA1 kernel build

Target: international **SM-S911B (dm1q)** running the EZA1 vendor stack and
UN1CA One UI 8 / Android 16. The installer replaces the kernel in `boot`;
the existing boot header and ramdisk are repacked by AnyKernel3.

## Sources

- Fork starting point: `29d38a6a77fd7a938289204e4f106cd372dbc7ea` (5.15.209).
- Android 13 LTS: `f181319b13edc6e68c367bc247e36bc255097483` (5.15.223).
- Linux stable updates: incremental `v5.15.223..v5.15.225`.
- KernelSU Next: submodule pinned to v3.4.2,
  `4c706b5938665866ebe16944a481a7b91e3396af`, version 33355.
- Compiler: Google Clang r450784e / 14.0.7, matching EZA1's compiler generation.
- BTF metadata: Android build-tools pahole 1.23, commit
  `083e34d8c2c4239be4967172427268c267585951`, matching EZA1's pahole version.
- Installer: voltage-dmxq/AnyKernel3, commit
  `db39ee20d5118a5453dcabb71f7939cb1affb297`, the template used by fsrb.

This is an Android kernel with Samsung and ABI adaptations. It is not an
unmodified kernel.org tarball. Stable changes that depend on newer NFS ACL or
perf-signal refactors retain their Android API paths. The commit history records
the adaptations and build fixes.

## Important adaptations

- Futex sequencing uses an Android reserved slot in `mm_struct`.
- Subreaper flags retain their bit offsets. `tasklist_lock` serializes prctl
  updates, and autoreap uses spare bits.
- The cgroup kill sequence uses existing arm64 padding before `cgroup.kn`.
- The XFRM work flag uses tail padding, preserving threshold offsets.
- Timed tty breaks share the existing write waitqueue.
- KEYCTL_READ sorts the complete serial list before truncation, hiding
  address-dependent traversal ordering without enlarging public key structures.
- Unicode maps keep their public size; RCU teardown state is allocated privately.
- USB audio uses existing endpoint padding for new URB bounds state.
- CPU capability exports retain the original 66-entry ABI prefix, with new
  capabilities appended without renumbering old entries.
- The old skb hash export and Samsung input-booster event notifier are retained.
- The embedded configuration reports the actual build rather than the fork's
  unrelated stock-config substitute.
- Vendor module CRC checking rejects mismatches; the fork's unconditional
  acceptance of mismatched versions has been removed.
- Samsung hardware/debug drivers are permitted to load. Only stock zram and
  zsmalloc modules are blocked when their replacements are built into the kernel.

## Build

Initialize the submodule, install normal kernel build dependencies, and use the
pinned compiler. `bc`, flex, bison, OpenSSL development files and pahole are needed.

```sh
git submodule update --init
CLANG_DIR=/absolute/path/to/clang-r450784e \
PAHOLE=/absolute/path/to/android13-build-tools/bin/pahole \
JOBS=8 scripts/build-s23.sh
```

The output is `out-s23/arch/arm64/boot/Image`. ThinLTO and CFI are enabled. Test builds default to compiler O1 and LTO O1.
After hardware validation, `S23_FAST_BUILD=0` enables the configured O2 build.
KernelSU is built in (`CONFIG_KSU=y`) with its manager and policy support enabled.

## Validate and package

The module checker requires Python's `pyelftools`. Supply the extracted EZA1
firmware root and the separately unpacked EZA1 vendor ramdisk. Both DLKM
partitions and the early-boot vendor modules must be checked.

```sh
python3 scripts/check-s23-modules.py /path/to/EZA1 out-s23 abi.json /path/to/vendor-ramdisk
python3 scripts/package-s23.py out-s23 /path/to/AnyKernel3 abi.json output.zip
```

Packaging refuses a failed module ABI report. A passing static audit is not a
hardware boot test. Keep the known-working EZA1/UN1CA boot image available for
recovery. Install the matching official KernelSU Next v3.4.2 manager APK.
