# -*- coding: utf-8 -*-
"""AzerothCore worldserver 에 내장된 SOAP 관리자 인터페이스로 GM 명령 하나를 보내고
결과 텍스트를 받아오는 아주 작은 클라이언트. 표준 라이브러리만 사용한다.

콘솔에 직접 명령을 치는 대신 이걸 쓰는 이유: 이 런처는 서버들을 콘솔 없이(숨겨서)
띄우기 때문에, "계정 생성" 같은 관리 명령을 치려면 매번 숨겨둔 콘솔을 열어야 했다.
SOAP 은 HTTP 요청 하나로 명령 하나를 실행하고 응답을 바로 받는 무상태 방식이라
콘솔을 열 필요가 없다. worldserver.conf 에서 `SOAP.Enabled = 1` 이어야 동작한다."""
import base64
import http.client
import re
import socket
import xml.etree.ElementTree as ET

SOAP_NS = "urn:AC"

# WotLK 종족은 얼라이언스 5종/호드 5종으로 고정돼 있다. `.pinfo <이름>` 응답 안에는
# 이 영어 종족명이 그대로 박혀 나온다("... Male Human Warrior ..." 같은 식) — 정확한
# 주변 문구/구분자는 서버마다 조금씩 다를 수 있어서, 줄 형식을 특정하지 않고 응답
# 텍스트 전체에서 이 키워드가 있는지만 찾는다(가장 덜 깨지는 방식).
RACE_TO_FACTION = {
    "human": "alliance", "dwarf": "alliance", "night elf": "alliance",
    "nightelf": "alliance", "gnome": "alliance", "draenei": "alliance",
    "orc": "horde", "undead": "horde", "scourge": "horde",
    "tauren": "horde", "troll": "horde", "blood elf": "horde", "bloodelf": "horde",
}

# ".account onlinelist" 응답 한 줄 형식(실제 서버로 라이브 확인함):
# -[         Account][   Character][             IP][Map][Zone][Exp][GMLev]-
# -[RNDBOT50][어떤캐릭터][127.0.0.1][571][67][2][0]-
# 데이터 줄만 골라내기 위해, 마지막 칸(GMLev)이 숫자인 줄만 데이터로 취급한다
# (머리글 줄은 "GMLev" 처럼 글자라 자동으로 걸러짐, 구분선 줄은애초에 대괄호 7개
# 패턴 자체가 안 맞아서 걸러짐).
_ONLINE_LIST_ROW_RE = re.compile(
    r"^-\[(.*?)\]\[(.*?)\]\[(.*?)\]\[(.*?)\]\[(.*?)\]\[(.*?)\]\[(.*?)\]-$"
)


def _build_envelope(command):
    # gSOAP 이 생성하는 표준 executeCommand 봉투. AzerothCore 가 실제로 요구하는
    # 정확한 네임스페이스/구조는 라이브 서버로 한 번 검증해서 맞춘다.
    escaped = (command.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace('"', "&quot;"))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<SOAP-ENV:Body>'
        f'<ns1:executeCommand xmlns:ns1="{SOAP_NS}">'
        f'<command>{escaped}</command>'
        '</ns1:executeCommand>'
        '</SOAP-ENV:Body>'
        '</SOAP-ENV:Envelope>'
    ).encode("utf-8")


def _parse_response(body_text):
    """성공 시 (True, 결과문자열). SOAP Fault 시 (False, 오류문자열)."""
    try:
        root = ET.fromstring(body_text)
    except ET.ParseError:
        return False, body_text.strip() or "서버 응답을 해석할 수 없습니다."

    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "Fault":
            fault_text = " ".join(e.text.strip() for e in el.iter() if e.text and e.text.strip())
            return False, fault_text or "명령 실행 중 오류가 발생했습니다."
        if tag == "result":
            return True, (el.text or "").strip() or "(명령이 실행되었지만 출력이 없습니다)"

    return True, "(응답을 받았지만 결과 텍스트를 찾지 못했습니다)"


def _decode_response_bytes(raw):
    """AzerothCore SOAP 응답이 XML 상으로는 UTF-8 이라고 선언돼 있어도, 실제 한글
    텍스트(캐릭터명 등)는 서버 로케일(한글 Windows 는 보통 CP949) 원본 바이트 그대로
    오는 경우가 있다 — UTF-8 로 그냥 디코딩하면 한글이 다 깨진다(라이브로 확인함).
    UTF-8 로 먼저 시도해서 성공하면 그대로 쓰고, 실패하면 CP949 로 다시 시도한다."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp949")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


def execute_command(host, port, username, password, command, timeout=10):
    """SOAP 로 GM 명령 하나를 실행한다. (성공여부, 응답/오류 메시지) 를 반환.
    실패해도 예외를 던지지 않고 항상 사람이 읽을 수 있는 메시지로 돌려준다."""
    if not username or not password:
        return False, "설정에서 GM 계정을 먼저 지정하세요."

    body = _build_envelope(command)
    auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f"{SOAP_NS}#executeCommand",
        "Authorization": f"Basic {auth}",
        "Content-Length": str(len(body)),
    }

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("POST", "/", body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = _decode_response_bytes(resp.read())

        if resp.status == 401:
            return False, "GM 계정 인증에 실패했습니다 (계정명/비밀번호를 확인하세요)."
        if resp.status >= 400 and not resp_body.strip():
            return False, f"서버가 오류를 반환했습니다 (HTTP {resp.status})."
        return _parse_response(resp_body)
    except (ConnectionRefusedError, socket.timeout, TimeoutError, OSError) as e:
        return False, f"서버에 연결할 수 없습니다 — 월드서버가 실행 중인지 확인하세요. ({e})"
    finally:
        conn.close()


def _parse_online_list(text):
    """'account onlinelist' 응답 텍스트를 줄 단위로 파싱해서
    [{"account":.., "character":.., "map":.., "zone":.., "gmlevel":..}, ...] 로 반환.
    머리글/구분선 줄은 대괄호 7개 형식이 아니거나 마지막 칸(GMLev)이 숫자가 아니라서
    자동으로 걸러진다."""
    entries = []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = _ONLINE_LIST_ROW_RE.match(line.strip())
        if not m:
            continue
        account, character, ip, map_id, zone, exp, gmlev = (g.strip() for g in m.groups())
        if not gmlev.isdigit():
            continue
        entries.append({
            "account": account, "character": character,
            "map": map_id, "zone": zone, "gmlevel": gmlev,
        })
    return entries


def list_online_accounts(host, port, username, password, limit=500,
                          timeout=10, pinfo_timeout=6, progress_cb=None):
    """지금 접속 중인 계정/캐릭터 목록을 얼라이언스/호드 진영과 함께 가져온다.
    'account onlinelist' 는 종족을 안 알려주므로, 목록에 있는 캐릭터마다
    '.pinfo <캐릭터명>' 을 한 번씩 더 호출해서(SOAP 명령이라 앞에 점 없이 보냄)
    응답 텍스트에서 종족 키워드를 찾아 진영으로 매긴다. 캐릭터 수만큼 순차 호출이
    생기므로(봇이 많은 서버는 수백 번) `progress_cb(done, total)` 로 진행 상황을
    알려줄 수 있게 했다 — 실패해도 예외 없이 (False, [], 오류메시지) 형태로 돌려준다."""
    ok, msg = execute_command(host, port, username, password, "account onlinelist", timeout=timeout)
    if not ok:
        return False, [], msg

    entries = _parse_online_list(msg)[:limit]
    total = len(entries)
    for i, entry in enumerate(entries):
        char_ok, char_msg = execute_command(
            host, port, username, password, f"pinfo {entry['character']}", timeout=pinfo_timeout,
        )
        entry["faction"] = None
        if char_ok:
            lower = char_msg.lower()
            for race, faction in RACE_TO_FACTION.items():
                if race in lower:
                    entry["faction"] = faction
                    break
        if progress_cb:
            try:
                progress_cb(i + 1, total)
            except Exception:
                pass

    return True, entries, ""


# "server info" 응답 형식(실제 서버로 라이브 확인함):
#   AzerothCore rev. 82d3bf237d51+ ... (Playerbot branch) (Win64, RelWithDebInfo, Static)
#   Connected players: 0. Characters in world: 380.
#   Connection peak: 0.
#   Server uptime: 41 second(s)
#   Update time diff: 105ms. Last 142 diffs summary:
#   |- Mean: 88ms
#   ...
_SERVER_INFO_PATTERNS = {
    "players": re.compile(r"Connected players:\s*(\d+)"),
    "characters": re.compile(r"Characters in world:\s*(\d+)"),
    "peak": re.compile(r"Connection peak:\s*(\d+)"),
    "update_diff_ms": re.compile(r"Update time diff:\s*(\d+)\s*ms"),
}
_UPTIME_UNIT_PATTERNS = [
    (re.compile(r"(\d+)\s*day\(s\)"), "일"),
    (re.compile(r"(\d+)\s*hour\(s\)"), "시간"),
    (re.compile(r"(\d+)\s*minute\(s\)"), "분"),
    (re.compile(r"(\d+)\s*second\(s\)"), "초"),
]


def parse_server_info(text):
    """'server info' 응답에서 접속 인원/최고 접속/가동 시간/응답 지연을 뽑아낸다.
    가동 시간은 영어 원문("1 day(s) 3 hour(s) ...")을 그대로 보여주면 한글 UI와
    어색하게 섞이므로, 가장 큰 단위 2개만 골라 한글로 짧게 다시 조합한다
    (예: "1일 3시간", "41초"). 값을 못 찾은 항목은 결과 dict 에서 그냥 빠진다 —
    호출 쪽에서 .get() 으로 다뤄야 한다."""
    result = {}
    for key, pattern in _SERVER_INFO_PATTERNS.items():
        m = pattern.search(text)
        if m:
            result[key] = int(m.group(1))

    m = re.search(r"Server uptime:\s*(.+)", text)
    if m:
        uptime_text = m.group(1).strip()
        units = []
        for pattern, suffix in _UPTIME_UNIT_PATTERNS:
            um = pattern.search(uptime_text)
            if um and int(um.group(1)) > 0:
                units.append(f"{um.group(1)}{suffix}")
        result["uptime"] = " ".join(units[:2]) if units else uptime_text

    return result
