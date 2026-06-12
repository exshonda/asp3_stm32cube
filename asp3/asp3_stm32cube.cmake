#
#  TOPPERS/ASP3 Core ＋ STM32Cube HAL 協調動作ヘルパ
#
#  アプリ（nucleo_*/CMakeLists.txt）から include する．役割：
#   - ASP3_TARGET → ASP3_TARGET_DIR（STM32ターゲット依存部）の解決
#   - ASP3_CORE_DIR（純カーネル submodule）／ASP3_ROOT_DIR の設定
#   - asp3_set_stm32_options()：STM32協調に要る設定（現状なし＝Pico の --wrap 相当は不要）
#
#  カーネル本体・共通arch・cfgエンジンは asp3_core サブモジュール（ASP3_CORE_DIR）側，
#  STM32固有のチップ依存部（arch/arm_m_gcc/stm32h5xx_stm32cube）とターゲット依存部
#  （target/stm32h563_nucleo 等）は本リポジトリ側に置く（ASP3_TARGET_DIR で供給）．
#  経緯：asp3/asp3_core/docs/dev/stm32-integration.md（FSP/ek_ra* と同型）
#

#  このファイルの場所＝本リポジトリの asp3/ ディレクトリ
set(ASP3_STM32_DIR ${CMAKE_CURRENT_LIST_DIR})

#  純カーネル（submodule）
set(ASP3_CORE_DIR ${CMAKE_CURRENT_LIST_DIR}/asp3_core)

#  ASP3カーネルソースのルート＝submodule．asp3_add_syssvc() 等のヘルパは
#  呼び出し側スコープの ASP3_ROOT_DIR を参照するため，親スコープでも設定しておく
#  （add_subdirectory(asp3_core) の子スコープ値は親へ伝播しないため）．
set(ASP3_ROOT_DIR ${ASP3_CORE_DIR})

#  STM32ターゲット依存部（target.cmake）を asp3_core へ供給（本リポジトリ側）．
#  asp3_core.cmake は未定義時のみ既定値で埋めるため，ここで先に設定する．
if(NOT DEFINED ASP3_TARGET)
    set(ASP3_TARGET stm32h563_nucleo)
endif()
set(ASP3_TARGET_DIR ${CMAKE_CURRENT_LIST_DIR}/target/${ASP3_TARGET})

function(asp3_set_stm32_options TARGET)
    #  STM32協調に追加設定が要る場合はここに（現状なし）．
    #  pico-sdk の irq_* --wrap に相当する割込み奪取は，CubeMX の startup が
    #  ベクタを握り main() が sta_ker() を呼ぶ構成では不要．
endfunction()
