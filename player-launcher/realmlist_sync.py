# -*- coding: utf-8 -*-
"""웹사이트(ac-web)의 공개 /api/realmlist에서 현재 렐름 접속 주소를 가져온다.
로그인/계정 정보와는 무관한 완전히 공개된 읽기 전용 정보라(홈페이지에도 그대로
보이는 값) 인증이 필요 없다. 이 동기화는 어디까지나 부가 기능이라, 실패해도
예외를 던지지 않고 조용히 None을 돌려준다 — 실패해도 기존 config.json의 값으로
그대로 플레이할 수 있어야 한다."""
import json
import urllib.error
import urllib.request

_TIMEOUT = 5


def fetch_realmlist(api_url, timeout=_TIMEOUT):
    """성공하면 "host:port"(또는 포트를 모르면 "host") 문자열, 실패하면 None."""
    if not api_url:
        return None
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "WOWLegendsPlayerLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None

    address = data.get("address")
    if not address:
        return None
    port = data.get("port")
    return f"{address}:{port}" if port else address
