/*
 * cfg1_out.cをリンクするために必要なスタブの定義
 */

void Reset_Handler(void) {}

void _close_r() {}
void _lseek_r() {}
void _read_r() {}
void _write_r() {}

int main() { return 0; }

/*
 * チップ依存のスタブの定義
 */
#include <chip_cfg1_out.h>
