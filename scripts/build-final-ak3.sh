#!/usr/bin/env bash
# Final S911B EZA1 build: O3 + full LTO O3, retaining CFI and the tested ABI.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
UN1CA_DIR=${UN1CA_DIR:-/home/salihefee/Projects/un1ca}
ASSETS=${ASSETS:-"$UN1CA_DIR/out/kernel-upstream"}
CLANG_DIR=${CLANG_DIR:-"$ASSETS/toolchains/clang-r450784e"}
PAHOLE=${PAHOLE:-"$ASSETS/toolchains/android13-build-tools/bin/pahole"}
PYTHON=${PYTHON:-"$UN1CA_DIR/out/tools/venv/bin/python"}
FIRMWARE=${FIRMWARE:-"$UN1CA_DIR/out/fw/SM-S911B_TUR"}
VENDOR_RAMDISK=${VENDOR_RAMDISK:-"$ASSETS/vendor-ramdisk-stock"}
STOCK_BTF=${STOCK_BTF:-"$ASSETS/stock-btf.json"}
ANYKERNEL_DIR=${ANYKERNEL_DIR:-"$ASSETS/AnyKernel3"}
OUT_DIR=${OUT_DIR:-"$ROOT/out-final-o3-full-lto"}
DIST_DIR=${DIST_DIR:-"$ASSETS/dist"}
JOBS=${JOBS:-12}
export PATH="$CLANG_DIR/bin:$UN1CA_DIR/out/host-tools/root/usr/bin:$PATH"
for file in "$CLANG_DIR/bin/clang" "$PAHOLE" "$PYTHON" "$STOCK_BTF" "$ANYKERNEL_DIR/anykernel.sh"; do
  [[ -f "$file" ]] || { echo "Missing dependency: $file" >&2; exit 1; }
done
for cmd in make bc flex bison bpftool sha256sum flock; do command -v "$cmd" >/dev/null; done
clang --version | head -1 | grep -q r450784e
"$PAHOLE" --version | grep -q 'v1.23'
"$PYTHON" -c 'import elftools'
[[ -d "$FIRMWARE/vendor_dlkm" && -d "$VENDOR_RAMDISK/lib/modules" ]]
[[ $(git -C KernelSU-Next rev-parse HEAD) == 4c706b5938665866ebe16944a481a7b91e3396af ]]

exec 9>"$ASSETS/.s23-final-build.lock"
flock -n 9 || { echo 'Another final-build script is running.' >&2; exit 1; }
# The earlier O2 build may still be running; do not run competing kernel builds.
waiting=0
while :; do
  busy=0
  for pid in $(pgrep -x make || true); do
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    if [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT/"* ]]; then busy=1; break; fi
  done
  (( busy )) || break
  if (( ! waiting )); then echo 'Waiting for the existing kernel build to finish…'; waiting=1; fi
  sleep 5
done

mkdir -p "$OUT_DIR" "$DIST_DIR"
exec > >(tee "$OUT_DIR/final-build.log") 2>&1
export KBUILD_BUILD_USER=salihefee KBUILD_BUILD_HOST=s23-builder KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP="$(git log -1 --format=%cD)"
git rev-parse HEAD > "$OUT_DIR/s23-source-commit.txt"
printf '%s\n' 'optimized: compiler O3, full LTO O3, CFI enabled' > "$OUT_DIR/s23-build-mode.txt"
args=(O="$OUT_DIR" ARCH=arm64 LLVM=1 LLVM_IAS=1
      CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_COMPAT=arm-linux-gnueabi-
      LOCALVERSION= PAHOLE="$PAHOLE" S23_FAST_BUILD=0 S23_LTO_OPT=3
      KCFLAGS=-D__ANDROID_COMMON_KERNEL__)
make "${args[@]}" gki_defconfig
scripts/config --file "$OUT_DIR/.config" \
  --disable CC_OPTIMIZE_FOR_PERFORMANCE --disable CC_OPTIMIZE_FOR_SIZE \
  --enable CC_OPTIMIZE_FOR_PERFORMANCE_O3 \
  --disable LTO_NONE --disable LTO_CLANG_THIN --enable LTO_CLANG_FULL \
  --enable CFI_CLANG --disable CFI_PERMISSIVE --enable KSU
make "${args[@]}" olddefconfig
for flag in CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE_O3 CONFIG_LTO_CLANG_FULL CONFIG_CFI_CLANG CONFIG_KSU; do
  grep -qx "$flag=y" "$OUT_DIR/.config" || { echo "Required option lost: $flag"; exit 1; }
done
make -j"$JOBS" "${args[@]}" Image modules

"$PYTHON" scripts/check-s23-modules.py "$FIRMWARE" "$OUT_DIR" "$OUT_DIR/abi.json" "$VENDOR_RAMDISK"
bpftool -j btf dump file "$OUT_DIR/vmlinux" format raw > "$OUT_DIR/btf.json"
"$PYTHON" scripts/check-s23-usb-layout.py "$STOCK_BTF" "$OUT_DIR/btf.json" "$OUT_DIR/usb-layout.json"
ZIP="$DIST_DIR/S23-EZA1-5.15.225-KSUNext-3.4.2-O3-FULL-LTO.zip"
"$PYTHON" scripts/package-s23.py "$OUT_DIR" "$ANYKERNEL_DIR" "$OUT_DIR/abi.json" "$ZIP" "$OUT_DIR/usb-layout.json"
(cd "$DIST_DIR" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")
cp "$OUT_DIR/abi.json" "$DIST_DIR/optimized-abi.json"
cp "$OUT_DIR/usb-layout.json" "$DIST_DIR/optimized-usb-layout.json"
echo "DONE: $ZIP"
echo 'Build and static checks passed. Flash manually in TWRP; keep TEST2 for rollback.'
