# created : 2025-10-23  컨테이너 실행
# modified : 2025-10-27 +-20% 알람 해제
# modified : 2025-10-27 로그파일 월단위 설정

import requests
import time
import datetime
import os
import sys
import json


# 설정값 불러오기 (config.json)
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "upbitMA.config.json")
with open(config_path, encoding="utf-8") as f:
    config = json.load(f)
TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = config.get("TELEGRAM_CHAT_ID")
MA_INTERVAL = config.get("MA_INTERVAL")  # 초 단위

# ✅ 실행 시마다 날짜 확인 → 파일명 동적으로 갱신
TODAY = datetime.date.today().strftime("%Y%m%d")
TODAY_MONTH = datetime.date.today().strftime("%Y%m")
SCRIPT_FILENAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
# LOG_DIR_FILENAME = os.path.join(SCRIPT_DIR, f"{SCRIPT_FILENAME}_{TODAY}.md")
LOG_DIR_FILENAME = os.path.join(SCRIPT_DIR, f"{SCRIPT_FILENAME}_{TODAY_MONTH}.md")



def send_telegram_message(message):
    """텔레그램 알림 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[텔레그램 전송 실패] {e}")

def get_upbit_markets():
    """업비트 원화시장 종목 목록 가져오기"""
    url = "https://api.upbit.com/v1/market/all"
    res = requests.get(url).json()
    return [m['market'] for m in res if m['market'].startswith('KRW-')]

def get_ticker_info(markets):
    """현재가, 전일가 기준으로 등락률 계산"""
    url = "https://api.upbit.com/v1/ticker"
    res = requests.get(url, params={"markets": ",".join(markets)}).json()

    result = []
    for r in res:
        change_rate = (r['trade_price'] - r['prev_closing_price']) / r['prev_closing_price'] * 100
        result.append({
            'market': r['market'],
            'change_rate': change_rate
        })
    return result

def analyze(change_data):
    """등락률 구간별 통계 계산"""
    summary = {
        'total': len(change_data),
        'rise_5': 0,
        'rise_10': 0,
        'rise_15': 0,
        'fall_5': 0,
        'fall_10': 0,
        'fall_15': 0,
        'neutral': 0,
        'rise_over_15': [],
        'fall_below_15': []
    }

    for d in change_data:
        rate = d['change_rate']
        if rate >= 15:
            summary['rise_15'] += 1
            summary['rise_over_15'].append(d)
        if rate >= 10:
            summary['rise_10'] += 1
        if rate >= 5:
            summary['rise_5'] += 1
        if -5 < rate < 5:
            summary['neutral'] += 1
        if rate <= -5:
            summary['fall_5'] += 1
        if rate <= -10:
            summary['fall_10'] += 1
        if rate <= -15:
            summary['fall_15'] += 1
        if rate <= -15:
            summary['fall_below_15'].append(d)

    return summary

def save_to_markdown(LOGFILE, summary):
    """결과를 Markdown 파일에 추가"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append(f"\n# 📈 업비트 원화시장 상승/하락 통계 ({now})\n")
    lines.append("| 구분 | 종목 수 |")
    lines.append("|------|----------|")
    lines.append(f"| 전체 종목 | {summary['total']} |")
    lines.append(f"| +15% 이상 | {summary['rise_15']} |")
    lines.append(f"| +10% 이상 | {summary['rise_10']} |")
    lines.append(f"| +5% 이상 | {summary['rise_5']} |")
    lines.append(f"| -5% ~ +5% | {summary['neutral']} |")
    lines.append(f"| -5% 이하 | {summary['fall_5']} |")
    lines.append(f"| -10% 이하 | {summary['fall_10']} |")
    lines.append(f"| -15% 이하 | {summary['fall_15']} |")

    lines.append("\n## 🚀 +15% 이상 상승 종목")
    if summary['rise_over_15']:
        lines.append("| 종목명 | 상승률(%) |")
        lines.append("|--------|------------|")
        for d in summary['rise_over_15']:
            lines.append(f"| {d['market']} | {d['change_rate']:.2f}% |")
    else:
        lines.append("- 없음")

    lines.append("\n## 📉 -15% 이하 하락 종목")
    if summary['fall_below_15']:
        lines.append("| 종목명 | 하락률(%) |")
        lines.append("|--------|------------|")
        for d in summary['fall_below_15']:
            lines.append(f"| {d['market']} | {d['change_rate']:.2f}% |")
    else:
        lines.append("- 없음")

    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n\n---\n\n")

    print(f"[{now}] Markdown 파일 저장 완료 → {LOGFILE}")
    return len(summary['fall_below_15'])

def main():
    while True:
        try:
            # === 데이터 수집 및 분석 ===
            markets = get_upbit_markets()
            change_data = get_ticker_info(markets)
            summary = analyze(change_data)
            fall_count = save_to_markdown(LOG_DIR_FILENAME, summary)
            
            # === 현재 시각 확인 ===
            now = datetime.datetime.now()
            hour = now.hour

            # -15% 이상 하락한 종목이 15개 이상 일 경우 메시지 전송
            if fall_count >= 15:
                msg = (
                    f"📉 경고: -15% 이하 하락 종목이 {fall_count}개 이상 발생!\n"
                    f"({now.strftime('%Y-%m-%d %H:%M')})\n"
                    f"전체 종목: {summary['total']}개\n"
                    f"상승: +5%↑ {summary['rise_5']}개 | +10%↑ {summary['rise_10']}개 | +15%↑ {summary['rise_15']}개\n"
                    f"보합(-5%~+5%): {summary['neutral']}개\n"
                    f"하락: -5%↓ {summary['fall_5']}개 | -10%↓ {summary['fall_10']}개 | -15%↓ {summary['fall_15']}개\n"
                    f"파일: {os.path.basename(LOG_DIR_FILENAME)}"
                )
                send_telegram_message(msg)
                
            # === ② 오전 8~9시에는 summary 요약 전송 ===
            if 8 <= hour < 9:
                msg = (
                    f"📊 업비트 원화시장 요약 리포트 ({now.strftime('%Y-%m-%d %H:%M')})\n"
                    f"전체 종목: {summary['total']}개\n"
                    f"상승: +5%↑ {summary['rise_5']}개 | +10%↑ {summary['rise_10']}개 | +15%↑ {summary['rise_15']}개\n"
                    f"보합(-5%~+5%): {summary['neutral']}개\n"
                    f"하락: -5%↓ {summary['fall_5']}개 | -10%↓ {summary['fall_10']}개 | -15%↓ {summary['fall_15']}개\n"
                    f"파일: {os.path.basename(LOG_DIR_FILENAME)}"
                )
                send_telegram_message(msg)

        except Exception as e:
            print(f"[오류 발생] {e}")

        print("⏳ 1시간 대기 중...\n")
        time.sleep(MA_INTERVAL)

if __name__ == "__main__":
    main()
