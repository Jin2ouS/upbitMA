# utils_upbit.py - 업비트/텔레그램 공통 유틸리티
# created : 2026-02-03 (upbitMA 분리)

import os
import requests

from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def _ensure_telegram_config():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID가 .env에 필요합니다.")


def send_telegram_message(message):
    """텔레그램 알림 전송"""
    _ensure_telegram_config()
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print(f"[텔레그램 전송 실패] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[텔레그램 전송 실패] {e}")


def get_upbit_markets():
    """업비트 원화시장 종목 목록 가져오기"""
    url = "https://api.upbit.com/v1/market/all"
    res = requests.get(url).json()
    return [m["market"] for m in res if m["market"].startswith("KRW-")]


def get_upbit_markets_all():
    """업비트 마켓 전체 조회 (종목명→마켓코드 매핑용)"""
    url = "https://api.upbit.com/v1/market/all"
    resp = requests.get(url, params={"isDetails": "true"}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_ticker_info(markets):
    """현재가, 전일가 기준으로 등락률 계산"""
    url = "https://api.upbit.com/v1/ticker"
    res = requests.get(url, params={"markets": ",".join(markets)}).json()

    result = []
    for r in res:
        change_rate = (r["trade_price"] - r["prev_closing_price"]) / r["prev_closing_price"] * 100
        result.append({"market": r["market"], "change_rate": change_rate})
    return result


def get_all_ticker_prices(markets):
    """전종목 시세 1회 API 호출로 조회 → { market: 현재가(int) } 반환"""
    if not markets:
        return {}
    url = "https://api.upbit.com/v1/ticker"
    try:
        resp = requests.get(url, params={"markets": ",".join(markets)}, timeout=15)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        return {
            r["market"]: int(float(r["trade_price"]))
            for r in data
            if r.get("trade_price") is not None
        }
    except Exception:
        return {}
