/*
 * シリアルインタフェースドライバのターゲット依存部（非TECS版専用）
 *
 * $Id: target_serial.h 289 2021-08-05 14:44:10Z ertl-komori $
 */

#include <stdint.h>
#include "t_stddef.h"
#include "target_serial.h"
#include "target_syssvc.h"
#include "stm32h5xx_nucleo.h"

struct sio_port_control_block
{
    IRQn_Type irq;                  /* 割込み番号 */
    intptr_t exinf;
    UART_HandleTypeDef *handle;     /* UARTハンドル */
    bool_t rdy_snd;                 /* 送信可能コールバック */
    uint8_t snd_buf[256];           /* 送信バッファ */
    uint32_t snd_wpos;              /* 送信バッファ書き込み位置 */
    uint32_t snd_rpos;              /* 送信バッファ読み込み位置 */
    bool_t rdy_rcv;                 /* 受信通知コールバック */
    uint8_t rcv_buf[256];           /* 受信バッファ */
    uint32_t rcv_wpos;              /* 受信バッファ書き込み位置 */
    uint32_t rcv_rpos;              /* 受信バッファ読み込み位置 */
};

/*
 *  SIOポート管理ブロックのエリア
 */
static SIOPCB siopcb_table[TNUM_PORT] = {
    {USART2_IRQn, 0, NULL, false, {0}, 0, 0, false, {0}, 0, 0},
};

/*
 *  SIOポートIDから管理ブロックを取り出すためのマクロ
 */
#define INDEX_SIOP(siopid)	((uint_t)((siopid) - 1))
#define get_siopcb(siopid)	(&(siopcb_table[INDEX_SIOP(siopid)]))

/*
 * SIOドライバの初期化
 */
void sio_initialize(intptr_t exinf)
{
    for (uint_t i = 0; i < TNUM_PORT; i++)
    {
        siopcb_table[i].exinf = exinf;
        siopcb_table[i].handle = NULL;
    }
}

/*
 * SIOドライバの終了処理
 */
void sio_terminate(intptr_t exinf)
{
	uint_t	i;
	SIOPCB	*p_siopcb;

	for (i = 0; i < TNUM_PORT; i++) {
		p_siopcb = &(siopcb_table[i]);
		if (p_siopcb->handle) {
			/*
			 *  オープンされているSIOポートのクローズ
			 */
			sio_cls_por(&(siopcb_table[i]));
		}
	}
}

/*
 * SIOポートのオープン
 */
SIOPCB *sio_opn_por(ID siopid, intptr_t exinf)
{
    SIOPCB *p_siopcb = NULL;
    if (siopid > TNUM_PORT) {
        return p_siopcb;
    }

    p_siopcb = get_siopcb(siopid);
    /* すでにオープンされている場合はNULLを返す */
    if (p_siopcb->handle != NULL) {
        return NULL;
    }

    p_siopcb->exinf = exinf;
    p_siopcb->handle = &hcom_uart[siopid - 1];
    p_siopcb->rcv_wpos = 0;
    p_siopcb->rcv_rpos = 0;

    HAL_NVIC_SetPriority(p_siopcb->irq, 1, 0);
    HAL_NVIC_EnableIRQ(p_siopcb->irq);

    HAL_UART_Receive_IT(p_siopcb->handle, &p_siopcb->rcv_buf[p_siopcb->rcv_wpos], 1); // 受信割込み開始

    return p_siopcb;
}

/*
 * SIOポートのクローズ
 */
void sio_cls_por(SIOPCB *p_siopcb)
{
    HAL_NVIC_DisableIRQ(p_siopcb->irq);

    p_siopcb->handle = NULL;
}

/*
 * SIOポートへの文字送信
 */
bool_t sio_snd_chr(SIOPCB *p_siopcb, char ch)
{
    p_siopcb->snd_buf[p_siopcb->snd_wpos] = ch; // 送信バッファに文字を格納
    if (HAL_UART_Transmit_IT(p_siopcb->handle, &p_siopcb->snd_buf[p_siopcb->snd_wpos], 1) == HAL_OK) {
        p_siopcb->snd_wpos = (p_siopcb->snd_wpos + 1) % sizeof(p_siopcb->snd_buf); // 書き込み位置を更新
        return true; // 送信成功
    }
    return false; // 送信失敗
}

/*
 * SIOポートからの文字受信
 */
int_t sio_rcv_chr(SIOPCB *p_siopcb)
{
    uint8_t ch;
    if (p_siopcb->rcv_wpos != p_siopcb->rcv_rpos) // 受信バッファにデータがある場合
    {
        ch = p_siopcb->rcv_buf[p_siopcb->rcv_rpos];
        p_siopcb->rcv_rpos = (p_siopcb->rcv_rpos + 1) % sizeof(p_siopcb->rcv_buf); // 読み込み位置を更新
        return ch;
    }
    return -1; // 受信失敗
}

/*
 * SIOポートからのコールバックの許可
 */
void sio_ena_cbr(SIOPCB *p_siopcb, uint_t cbrtn)
{
    switch (cbrtn) {
    case SIO_RDY_SND:
        p_siopcb->rdy_snd = true;
        break;
    case SIO_RDY_RCV:
        p_siopcb->rdy_rcv = true;
        break;
    default:
        break;
    }
}

/*
 * SIOポートからのコールバックの禁止
 */
void sio_dis_cbr(SIOPCB *p_siopcb, uint_t cbrtn)
{
    switch (cbrtn) {
    case SIO_RDY_SND:
        p_siopcb->rdy_snd = false;
        break;
    case SIO_RDY_RCV:
        p_siopcb->rdy_rcv = false;
        break;
    default:
        break;
    }
}

/*
 * SIOポートへのポーリング出力
 *
 * syslogの低レベル出力．カーネル起動前・CPUロック中・例外文脈でも
 * 動作するよう，HAL・stdioを介さずUSART2（ST-LINK VCP）レジスタを
 * 直接ポーリングする（porting仕様の「SIOポーリング出力」）．
 */
static void h533_uart_fput(char c)
{
    while ((USART2->ISR & USART_ISR_TXE) == 0U) {
        /* 送信データレジスタが空くまでポーリング */
    }
    USART2->TDR = (uint8_t)c;
}

/*
 * SIOポートへの文字出力
 */
void target_fput_log(char c)
{
    /* UART未初期化（BSP_COM_Init前）の間は捨てる */
    if ((USART2->CR1 & USART_CR1_UE) == 0U) {
        return;
    }
    if (c == '\n') {
        h533_uart_fput('\r');
    }
    h533_uart_fput(c);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    SIOPCB *p_siopcb = NULL;
    for (uint_t i = 0; i < TNUM_PORT; i++) {
        if (siopcb_table[i].handle == huart) {
            p_siopcb = &siopcb_table[i];
            break;
        }
    }

    /*
     *  該当するポートが見つからない場合は何もしない
     */
    if (p_siopcb == NULL) {
        return;
    }

    /*
     *  送信可能コールバックルーチンを呼び出す．
     */
    if (p_siopcb->rdy_snd) {
        sio_irdy_snd(p_siopcb->exinf);
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    SIOPCB *p_siopcb = NULL;
    for (uint_t i = 0; i < TNUM_PORT; i++) {
        if (siopcb_table[i].handle == huart) {
            p_siopcb = &siopcb_table[i];
            break;
        }
    }

    /*
     *  該当するポートが見つからない場合は何もしない
     */
    if (p_siopcb == NULL) {
        return;
    }

    /*
     *  受信データをバッファに格納する．
     */
    p_siopcb->rcv_wpos = (p_siopcb->rcv_wpos + 1) % sizeof(p_siopcb->rcv_buf);

    /*
     *  受信割込み開始
     */
    HAL_UART_Receive_IT(p_siopcb->handle, &p_siopcb->rcv_buf[p_siopcb->rcv_wpos], 1);

    /*
     *  受信通知コールバックルーチンを呼び出す．
     */
    if (p_siopcb->rdy_rcv) {
        sio_irdy_rcv(p_siopcb->exinf);
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    SIOPCB *p_siopcb = NULL;
    for (uint_t i = 0; i < TNUM_PORT; i++) {
        if (siopcb_table[i].handle == huart) {
            p_siopcb = &siopcb_table[i];
            break;
        }
    }

    /*
     *  該当するポートが見つからない場合は何もしない
     */
    if (p_siopcb == NULL) {
        return;
    }

    // エラー処理をここに追加することができます。
}

void sio_handler(void)
{
    HAL_UART_IRQHandler(siopcb_table[0].handle);   // UARTの割込みハンドラを初期化
}