# -*- coding: utf-8 -*-
"""
매일 월~금 18:00 (장 마감 후) 네이버 금융 공식 종가 자동 수집 및 대시보드 갱신 스크립트
"""
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
import pytz

def get_naver_close_price(code):
    """네이버 금융 공식 종가 조회"""
    # A 접두사 제거
    clean_code = code.replace("A", "").strip()
    
    # 현금성 자산 및 펀드/MMF 예외 처리
    if clean_code in ["00001", "1051068"]:
        return 1.0  # 1원 고정
    if clean_code in ["1058298", "1058337"]:
        # 펀드 상품의 경우 기준가 조회 또는 기존가 유지
        return None

    # 네이버 금융 모바일 API 호출
    url = f"https://m.stock.naver.com/api/stock/{clean_code}/basic"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # nowPrice 또는 closePrice 추출
            close_price_str = data.get("nowPrice") or data.get("closePrice")
            if close_price_str:
                return float(str(close_price_str).replace(",", ""))
    except Exception as e:
        print(f"[{code}] 네이버 금융 시세 수신 실패: {e}")
    return None

def update_dashboard():
    # 1. 파일 읽기
    target_file = "index.html"
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        target_file = "etf_portfolio_dashboard_final.html"
        with open(target_file, "r", encoding="utf-8") as f:
            html = f.read()

    # 2. holdingsData 추출
    holdings_match = re.search(r'const holdingsData = (\[[\s\S]*?\]);', html)
    if not holdings_match:
        print("holdingsData를 찾을 수 없습니다.")
        return

    holdings = json.loads(holdings_match.group(1))
    print(f"총 {len(holdings)}개 종목 시세 수집 시작...")

    # 3. 각 종목별 종가 업데이트
    covered_call_keywords = ['커버드콜', '타겟데일리', '위클리']
    total_eval = 0.0
    total_buy = 0.0
    covered_call_eval = 0.0

    for h in holdings:
        ticker = h.get("ticker", "")
        qty = h.get("qty", 0)
        buy_total = h.get("buyTotal", 0.0)
        
        new_close = get_naver_close_price(ticker)
        if new_close is not None and qty > 0:
            h["evalTotal"] = round(new_close * qty, 1)
            h["diff"] = round(h["evalTotal"] - buy_total, 1)
            h["ret"] = round((h["diff"] / buy_total * 100), 2) if buy_total > 0 else 0.0
        
        eval_amt = h.get("evalTotal", 0.0)
        total_eval += eval_amt
        total_buy += buy_total
        
        if any(k in h.get("name", "") for k in covered_call_keywords):
            covered_call_eval += eval_amt

    # 4. 상단 요약 지표 재계산
    total_profit = total_eval - total_buy
    total_ret = (total_profit / total_buy * 100) if total_buy > 0 else 0.0
    covered_pct = (covered_call_eval / total_eval * 100) if total_eval > 0 else 0.0

    print(f"갱신 완료: 총 평가 ₩ {total_eval:,.0f} (수익률 {total_ret:.2f}%) / 커버드콜 {covered_pct:.2f}%")

    # 5. holdingsData 치환
    new_holdings_json = json.dumps(holdings, ensure_ascii=False, indent=2)
    html = re.sub(r'const holdingsData = \[[\s\S]*?\];', f'const holdingsData = {new_holdings_json};', html)

    # 6. 상단 요약 카드 수치 치환
    # 총 평가금액
    html = re.sub(
        r'<div class="summary-val" style="color:#ffffff;">₩ [0-9,]+</div>\s*<div class="summary-sub down">▼ -₩ [0-9,]+ \([0-9.-]+%\)</div>',
        f'<div class="summary-val" style="color:#ffffff;">₩ {int(total_eval):,}</div>\n      <div class="summary-sub down">▼ -₩ {abs(int(total_profit)):,} ({total_ret:.2f}%)</div>',
        html
    )
    # 커버드콜 비중
    html = re.sub(
        r'₩ [0-9,]+ \([0-9.]+%\)</div>\s*<div class="summary-sub" style="color:#fca5a5;">⚠️ 권장 상한',
        f'₩ {int(covered_call_eval):,} ({covered_pct:.2f}%)</div>\n      <div class="summary-sub" style="color:#fca5a5;">⚠️ 권장 상한',
        html
    )

    # 7. 마지막 갱신 일시 (KST) 반영
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    html = re.sub(r'마지막 갱신: <strong id="lastUpdatedTime"[^>]*>.*?</strong>',
                  f'마지막 갱신: <strong id="lastUpdatedTime" style="color:#ffffff; font-family:monospace; font-size:0.88rem;">{now_kst} (자동 마감 확정)</strong>',
                  html)

    # 8. 저장
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("etf_portfolio_dashboard_final.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML 파일 성공적으로 업데이트 완료!")

if __name__ == "__main__":
    update_dashboard()
