#!/bin/sh
# SPDX-License-Identifier: GPL-2.0

extra_paholeopt=

if ! [ -x "$(command -v ${PAHOLE})" ]; then
	exit 0
fi

pahole_ver=$($(dirname $0)/pahole-version.sh ${PAHOLE})

if [ "${pahole_ver}" -ge "118" ] && [ "${pahole_ver}" -le "121" ]; then
	# pahole 1.18 through 1.21 can't handle zero-sized per-CPU vars
	extra_paholeopt="${extra_paholeopt} --skip_encoding_btf_vars"
fi
if [ "${pahole_ver}" -ge "121" ]; then
	extra_paholeopt="${extra_paholeopt} --btf_gen_floats"
fi

# With Clang full LTO, pahole 1.23 emits overlapping per-CPU VARs from
# duplicated DWARF locations (observed on S23: efi_sve_state_used, lru_pvecs,
# call_single_queue). The kernel rejects this vmlinux BTF and consequently
# *all* BPF_PROG_LOAD calls fail, including Android's networking programs.
# Keep type/function BTF and all compiler optimizations; omit optional VAR
# records with this encoder, as already done above for older broken versions.
if [ "${pahole_ver}" -eq "123" ] && [ "${CONFIG_LTO_CLANG_FULL}" = "y" ]; then
	extra_paholeopt="${extra_paholeopt} --skip_encoding_btf_vars"
fi

if [ "${pahole_ver}" -ge "124" ]; then
	extra_paholeopt="${extra_paholeopt} --skip_encoding_btf_enum64"
fi
if [ "${pahole_ver}" -ge "125" ]; then
	extra_paholeopt="${extra_paholeopt} --skip_encoding_btf_inconsistent_proto --btf_gen_optimized"
fi

echo ${extra_paholeopt}
