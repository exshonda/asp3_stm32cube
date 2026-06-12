/*
 * シリアルインタフェースドライバのターゲット依存部（非TECS版専用）
 *
 * $Id: target_serial.h 289 2021-08-05 14:44:10Z ertl-komori $
 */

#ifndef TOPPERS_TARGET_SERIAL_H
#define TOPPERS_TARGET_SERIAL_H

#include "stm32cubemx.h"
/*
 * SIO割込みハンドラ登録のための定数
 */
#define INHNO_USART		(USART3_IRQn + 16)	/* 割込みハンドラ番号 */
#define INTNO_USART		(USART3_IRQn + 16)	/* 割込み番号 */
#define INTPRI_USART	(TMAX_INTPRI - 1)   /* 割込み優先度 */
#define INTATR_USART	TA_NULL             /* 割込み属性 */

/*
 *  シリアルポート数の定義
 */
#define TNUM_PORT 1

/*
 *  コールバックルーチンの識別番号
 */
#define SIO_RDY_SND    1U        /* 送信可能コールバック */
#define SIO_RDY_RCV    2U        /* 受信通知コールバック */

#ifndef TOPPERS_MACRO_ONLY

/*
 *  シリアルI/Oポート管理ブロックの定義
 */
typedef struct sio_port_control_block    SIOPCB;

/*
 *  SIOドライバの初期化
 */
extern void sio_initialize(EXINF exinf);

/*
 *  SIOドライバの終了処理
 */
extern void sio_terminate(EXINF exinf);

/*
 *  SIOの割込みハンドラ
 */
extern void sio_handler(void);

/*
 *  SIOポートのオープン
 */
extern SIOPCB *sio_opn_por(ID siopid, EXINF exinf);

/*
 *  SIOポートのクローズ
 */
extern void sio_cls_por(SIOPCB *p_siopcb);

/*
 *  SIOポートへの文字送信
 */
extern bool_t sio_snd_chr(SIOPCB *p_siopcb, char c);

/*
 *  SIOポートからの文字受信
 */
extern int_t sio_rcv_chr(SIOPCB *p_siopcb);

/*
 *  SIOポートからのコールバックの許可
 */
extern void sio_ena_cbr(SIOPCB *p_siopcb, uint_t cbrtn);

/*
 *  SIOポートからのコールバックの禁止
 */
extern void sio_dis_cbr(SIOPCB *p_siopcb, uint_t cbrtn);

/*
 *  SIOポートからの送信可能コールバック
 */
extern void sio_irdy_snd(EXINF exinf);

/*
 *  SIOポートからの受信通知コールバック
 */
extern void sio_irdy_rcv(EXINF exinf);

#endif /* TOPPERS_MACRO_ONLY */

/*
 * チップで共通な定義
 */
#include "stm32h5xx_hal.h"

#endif /* TOPPERS_TARGET_SERIAL_H */
