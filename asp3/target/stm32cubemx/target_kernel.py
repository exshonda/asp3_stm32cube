# -*- coding: utf-8 -*-
#
#   TOPPERS/ASP Kernel
#       Toyohashi Open Platform for Embedded Real-Time Systems/
#       Advanced Standard Profile Kernel
#
#   $Id: target_kernel.py (converted from target_kernel.trb) $
#

#
#     パス2のターゲット依存テンプレート（NUCLEO-H563ZI / STM32Cube HAL 用）
#
#  arm_m 共通テンプレート（core_kernel.py）は使わず，kernel/kernel.py を直接
#  インクルードしてベクタテーブルをここで生成する（FSP と同方針）．理由：
#  リセットエントリと初期スタックポインタを CubeMX 生成の startup_stm32h5xx.s
#  （Reset_Handler / _estack）に向けるため．core_kernel.py は _kernel_start /
#  _kernel_istack を用いる arm_m 標準の起動を前提とする．
#

#
#  有効な割込み番号，割込みハンドラ番号
#
INTNO_VALID = list(range(15, TMAX_INTNO + 1))
INHNO_VALID = INTNO_VALID

#
#  有効なCPU例外番号
#
EXCNO_VALID = [2, 3, 4, 5, 6, 7, 12]

#
#  CRE_ISRで使用できる割込み番号とそれに対応する割込みハンドラ番号
#
INTNO_CREISR_VALID = INTNO_VALID
INHNO_CREISR_VALID = INHNO_VALID

#
#  DEF_INT／DEF_EXCで使用できる割込みハンドラ番号／CPU例外ハンドラ番号
#
INHNO_DEFINH_VALID = INHNO_VALID
EXCNO_DEFEXC_VALID = EXCNO_VALID

#
#  CFG_INTで使用できる割込み番号と割込み優先度
#  最大優先度はBASEPRIレジスタでマスクできない優先度（内部優先度'0'）
#  そのため，カーネル管理外の割込みでのみ指定可能．
#
INTNO_CFGINT_VALID = INTNO_VALID
INTPRI_CFGINT_VALID = list(range(-(1 << TBITW_IPRI), 0))

#
#  kernel/kernel.tf のターゲット依存部
#

#
#  TSKINICTXBの初期化情報を生成
#
def GenerateTskinictxb(key, params):
    return ("{"
            f"\t(void *)({params['tinib_stk']}), "
            f"\t((void *)((char *)({params['tinib_stk']}) + "
            f"({params['tinib_stksz']}))), "
            "},")

#
#  ベクタテーブルの予約領域はデフォルトで0にする
#
if "GenResVectVal" not in globals():
    GenResVectVal = lambda num: 0

#
#  標準テンプレートファイルのインクルード
#
IncludeTrb("kernel/kernel.py")

kernelCfgC.append("""/*
 *  Target-dependent Definitions (ARM-M / STM32Cube)
 */

/*
 *  ベクターテーブル
 *
 *  リセットエントリ・初期スタックポインタは CubeMX 生成の startup から引く．
 *  Reset_Handler は target_kernel.h，_estack は target_kernel_impl.h で
 *  既に宣言済み（cfg1_out 用のダミー Reset_Handler は target_cfg1_out.h）．
 */
__attribute__ ((section(".vector")))
const FP _kernel_vector_table[] = {
    (FP)(&_estack),                    /* 0 The initial stack pointer */
    (FP)Reset_Handler,                 /* 1 The reset handler */
""")
for excno in range(2, 15):
    if excno == 8:
        kernelCfgC.add(f"    (FP)({GenResVectVal(8)}),")
    elif excno == 9:
        kernelCfgC.add(f"    (FP)({GenResVectVal(9)}),")
    elif excno == 10:
        kernelCfgC.add(f"    (FP)({GenResVectVal(10)}),")
    elif excno == 11:
        kernelCfgC.add("    (FP)(_kernel_svc_handler),      /* 11 SVCall handler */")
    elif excno == 13:
        kernelCfgC.add(f"    (FP)({GenResVectVal(13)}),")
    elif excno == 14:
        kernelCfgC.add("    (FP)(_kernel_pendsv_handler),      /* 14 PendSV handler */")
    else:
        exc = cfgData.get("DEF_EXC", {}).get(excno)
        if exc and (exc["excatr"] & TA_DIRECT) != 0:
            kernelCfgC.add(f"    (FP)({exc['exchdr']}), /* {excno} */")
        else:
            kernelCfgC.add(f"    (FP)(_kernel_core_exc_entry), /* {excno} */")

for inhno in INTNO_VALID:
    inh = cfgData.get("DEF_INH", {}).get(inhno)
    if inh and (inh["inhatr"] & TA_NONKERNEL) != 0:
        kernelCfgC.add(f"    (FP)({inh['inthdr']}), /* {inhno} */")
    else:
        kernelCfgC.add(f"    (FP)(_kernel_core_int_entry), /* {inhno} */")
kernelCfgC.add2("};")

kernelCfgC.add("const FP _kernel_exc_tbl[] = {")
for excno in range(0, 15):
    exc = cfgData.get("DEF_EXC", {}).get(excno)
    if exc:
        kernelCfgC.add(f"   (FP)({exc['exchdr']}), /* {excno} */")
    else:
        kernelCfgC.add(f"   (FP)(_kernel_default_exc_handler), /* {excno} */")

for inhno in INTNO_VALID:
    inh = cfgData.get("DEF_INH", {}).get(inhno)
    if inh:
        kernelCfgC.add(f"   (FP)({inh['inthdr']}), /* {inhno} */")
    else:
        kernelCfgC.add(f"   (FP)(_kernel_default_int_handler), /* {inhno} */")
kernelCfgC.add2("};")

#
#  _kernel_bitpat_cfgintの生成
#

bitpat_cfgint_num = 0
if (TMAX_INTNO & 0x0f) == 0x00:
    bitpat_cfgint_num = (TMAX_INTNO >> 4)
else:
    bitpat_cfgint_num = (TMAX_INTNO >> 4) + 1

kernelCfgC.add()
kernelCfgC.add(f"const uint32_t _kernel_bitpat_cfgint[{bitpat_cfgint_num}] = {{")
for num in range(bitpat_cfgint_num):
    bitpat_cfgint = 0
    for inhno in range((num * 32), (num * 32) + 32):
        inh_list = [v for k, v in cfgData.get("DEF_INH", {}).items()
                    if v["inhno"] == inhno]
        if inh_list:
            bitpat_cfgint = bitpat_cfgint | (1 << (inhno & 0x01f))
    kernelCfgC.add("   UINT32_C(0x%08x)," % bitpat_cfgint)
kernelCfgC.add2("};")
