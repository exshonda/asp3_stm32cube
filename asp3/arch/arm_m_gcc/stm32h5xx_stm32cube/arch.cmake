#
#  アーキ依存部のCMake定義（STM32H5xx / Cortex-M33 + STM32Cube HAL）
#
#  外部（SDK）ターゲットのパス解決規約（asp3_core PORTING_GUIDE「外部ターゲット」）：
#   - 共通arch（arch/arm_m_gcc/common）は asp3_core サブモジュール側＝ARCHDIR
#   - チップ依存部（stm32h5xx_stm32cube）は本リポジトリ側＝CHIPDIR
#  ARCHDIR/CHIPDIR/TARGETDIR は target.cmake で設定済み．
#
#  start.S（_kernel_start）は含めない：リセットは CubeMX 生成の Reset_Handler が
#  握り，main() が sta_ker() を呼ぶ（FSP/RASC と同方針）．ベクタテーブルの
#  リセットエントリも Reset_Handler を指す（target_kernel.py 参照）．SIO は
#  チップ内蔵シリアル（chip_serial.c）ではなく target_serial.c（HAL UART）が供給．
#

list(APPEND ASP3_SYMVAL_TABLES
    ${ARCHDIR}/common/core_sym.def
)

list(APPEND ASP3_OFFSET_TRB_FILES
    ${ARCHDIR}/common/core_offset.py
)

list(APPEND ASP3_INCLUDE_DIRS
    ${CHIPDIR}
    ${ARCHDIR}/common
    ${ASP3_ROOT_DIR}/arch/gcc
)

#  TOPPERS_ENABLE_TRUSTZONE は定義しないこと：STM32H5 は TZEN オプションバイト
#  無効（出荷時 0xC3=disabled）の場合，ハードウェアが生成する EXC_RETURN は
#  0xFFFFFFBC（ES/S=0）．定義すると Secure 用 0xFFFFFFFD になり仕様上不正
#  （RES0 ビットに 1）．実測（NUCLEO-H533RE）では動作したが保証はないため，
#  TZEN 無効構成では定義しない．TZEN 有効（Secure 実行）にする場合のみ定義する．
list(APPEND ASP3_COMPILE_DEFS
    TOPPERS_CORTEX_M33
    __TARGET_ARCH_THUMB=5
    __TARGET_FPU_FPV4_SP
)

list(APPEND ASP3_ARCH_C_FILES
    ${ARCHDIR}/common/core_kernel_impl.c
    ${ARCHDIR}/common/core_support.S
)
