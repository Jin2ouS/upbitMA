# upbitMA_market.py - 업비트 원화시장 전체 종목 분석 전용
# created : 2026-02-03 (upbitMA 분리)
# 수정: .env ALL_MA_INTERVAL 사용

import os
import sys
import time
import datetime
import atexit
import signal

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

from utils_upbit import send_telegram_message, get_upbit_markets, get_ticker_info

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

ALL_MA_INTERVAL = int(os.getenv("ALL_MA_INTERVAL", "3600").strip() or "3600")
if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or not os.getenv("TELEGRAM_CHAT_ID", "").strip():
    raise ValueError("TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID가 .env에 필요합니다.")

TODAY_MONTH = datetime.date.today().strftime("%Y%m")
SCRIPT_FILENAME = "upbitMA_market"
LOG_DIR_FILENAME = os.path.join(SCRIPT_DIR, f"{SCRIPT_FILENAME}_{TODAY_MONTH}.md")


def analyze(change_data):
    """등락률 구간별 통계 계산"""
    summary = {
        "total": len(change_data),
        "rise_5": 0,
        "rise_10": 0,
        "rise_15": 0,
        "fall_5": 0,
        "fall_10": 0,
        "fall_15": 0,
        "neutral": 0,
        "rise_over_15": [],
        "fall_below_15": [],
    }

    for d in change_data:
        rate = d["change_rate"]
        if rate >= 15:
            summary["rise_15"] += 1
            summary["rise_over_15"].append(d)
        if rate >= 10:
            summary["rise_10"] += 1
        if rate >= 5:
            summary["rise_5"] += 1
        if -5 < rate < 5:
            summary["neutral"] += 1
        if rate <= -5:
            summary["fall_5"] += 1
        if rate <= -10:
            summary["fall_10"] += 1
        if rate <= -15:
            summary["fall_15"] += 1
        if rate <= -15:
            summary["fall_below_15"].append(d)

    return summary


def save_to_markdown(LOGFILE, summary):
    """결과를 Markdown 파일에 추가"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append(f"\n# 📈 업비트 원화시장 상승/하락 통계 ({now})\n")
    lines.append("| 구분 | 종목 수 |")
    lines.append("|------|----------|")
    lines.append(f"| 전체 종목 | {summary['total']} |")
    lines.append(f"| (+15% 이상) | {summary['rise_15']} |")
    lines.append(f"| (+10% 이상) | {summary['rise_10']} |")
    lines.append(f"| +5% 이상 | {summary['rise_5']} |")
    lines.append(f"| -5% ~ +5% | {summary['neutral']} |")
    lines.append(f"| -5% 이하 | {summary['fall_5']} |")
    lines.append(f"| (-10% 이하) | {summary['fall_10']} |")
    lines.append(f"| (-15% 이하) | {summary['fall_15']} |")

    lines.append("\n## 🚀 +15% 이상 상승 종목")
    if summary["rise_over_15"]:
        lines.append("| 종목명 | 상승률(%) |")
        lines.append("|--------|------------|")
        for d in summary["rise_over_15"]:
            lines.append(f"| {d['market']} | {d['change_rate']:.2f}% |")
    else:
        lines.append("- 없음")

    lines.append("\n## 📉 -15% 이하 하락 종목")
    if summary["fall_below_15"]:
        lines.append("| 종목명 | 하락률(%) |")
        lines.append("|--------|------------|")
        for d in summary["fall_below_15"]:
            lines.append(f"| {d['market']} | {d['change_rate']:.2f}% |")
    else:
        lines.append("- 없음")

    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n\n---\n\n")

    print(f"[{now}] Markdown 파일 저장 완료 → {LOGFILE}")
    return len(summary["fall_below_15"])


def main():
    now_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_telegram_message(f"🟢 [upbitMA_market] 업비트 시장 분석 스크립트 시작\n({now_start})")
    print(f"[시작] 텔레그램 알림 전송 완료 → {now_start}")

    def on_exit():
        t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        send_telegram_message(f"🔴 [upbitMA_market] 스크립트 종료\n({t})")

    atexit.register(on_exit)
    signal.signal(signal.SIGINT, lambda s, f: (on_exit(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (on_exit(), sys.exit(0)))

    last_daily_report_date = None

    while True:
        try:
            now = datetime.datetime.now()
            hour, minute = now.hour, now.minute
            today = now.date()

            markets = get_upbit_markets()
            change_data = get_ticker_info(markets)
            summary = analyze(change_data)
            fall_count = save_to_markdown(LOG_DIR_FILENAME, summary)

            # ① -15% 이하 하락 15개 이상 시 텔레그램 전송
            if fall_count >= 15:
                msg = (
                    f"📉 경고: -15% 이하 하락 종목이 {fall_count}개 이상 발생!\n"
                    f"({now.strftime('%Y-%m-%d %H:%M')})\n"
                    f"전체 종목: {summary['total']}개\n"
                    f"상승: +5%↑ {summary['rise_5']}개 (+10%↑ {summary['rise_10']}개 | +15%↑ {summary['rise_15']}개)\n"
                    f"보합(-5%~+5%): {summary['neutral']}개\n"
                    f"하락: -5%↓ {summary['fall_5']}개 (-10%↓ {summary['fall_10']}개 | -15%↓ {summary['fall_15']}개)\n"
                    f"파일: {os.path.basename(LOG_DIR_FILENAME)}"
                )
                send_telegram_message(msg)

            # ② 매일 8시~9시(9시 이전) 정리 리포트
            is_daily_report_window = (hour == 8)
            if is_daily_report_window and last_daily_report_date != today:
                msg_summary = (
                    f"📊 업비트 원화시장 요약 리포트 ({now.strftime('%Y-%m-%d %H:%M')})\n"
                    f"전체 종목: {summary['total']}개\n"
                    f"상승: +5%↑ {summary['rise_5']}개 (+10%↑ {summary['rise_10']}개 | +15%↑ {summary['rise_15']}개)\n"
                    f"보합(-5%~+5%): {summary['neutral']}개\n"
                    f"하락: -5%↓ {summary['fall_5']}개 (-10%↓ {summary['fall_10']}개 | -15%↓ {summary['fall_15']}개)\n"
                    f"파일: {os.path.basename(LOG_DIR_FILENAME)}"
                )
                send_telegram_message(msg_summary)
                last_daily_report_date = today
                print(f"[로그] 매일 8~9시 정리 리포트 전송 완료 ({now.strftime('%Y-%m-%d %H:%M')})")

        except Exception as e:
            print(f"[오류 발생] {e}")

        now = datetime.datetime.now()
        next_run = now + datetime.timedelta(seconds=ALL_MA_INTERVAL)
        print(f"[{now.strftime('%H:%M:%S')}] ⏳ {ALL_MA_INTERVAL}초 대기 중... 다음 {next_run.strftime('%H:%M:%S')}")
        time.sleep(ALL_MA_INTERVAL)


if __name__ == "__main__":
    main()
