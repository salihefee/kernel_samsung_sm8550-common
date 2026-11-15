#!/usr/bin/env bash
# EZA1-compatible toolchain; set CLANG_DIR and provide bc on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CLANG_DIR:?Set CLANG_DIR to Google clang-r450784e}"
export PATH="$CLANG_DIR/bin:$PATH"
clang --version | head -1 | grep -q 'r450784e' || {
  echo 'Expected Google Clang r450784e (14.0.7)' >&2; exit 1;
}
export KBUILD_BUILD_USER=salihefee
export KBUILD_BUILD_HOST=s23-builder
export KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP="$(git log -1 --format=%cD)"
OUT_DIR=${OUT_DIR:-out-s23}
JOBS=${JOBS:-8}
S23_FAST_BUILD=${S23_FAST_BUILD:-1}
mkdir -p "$OUT_DIR"
if [[ "$S23_FAST_BUILD" == 1 ]]; then
  printf "%s\n" "test: compiler O1, ThinLTO O1, CFI enabled" > "$OUT_DIR/s23-build-mode.txt"
else
  printf "%s\n" "optimized: compiler O2, ThinLTO default optimization, CFI enabled" > "$OUT_DIR/s23-build-mode.txt"
fi
args=(O="$OUT_DIR" ARCH=arm64 LLVM=1 LLVM_IAS=1
      CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_COMPAT=arm-linux-gnueabi-
      LOCALVERSION= PAHOLE="${PAHOLE:-pahole}" S23_FAST_BUILD="$S23_FAST_BUILD" KCFLAGS=-D__ANDROID_COMMON_KERNEL__)
make "${args[@]}" gki_defconfig
make -j"$JOBS" "${args[@]}" Image modules
