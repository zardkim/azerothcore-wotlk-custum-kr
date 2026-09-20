# -*- coding: utf-8 -*-
"""AzerothCore 서버가 쓰는 authserver.conf / worldserver.conf 파일을 읽고(+일부는
다시 쓰는) 아주 작은 파서. 표준 라이브러리만 사용한다.

이 conf 파일들은 서버팩마다 실행파일과 같은 폴더에 있기도 하고, 그 밑의
configs 같은 하위 폴더에 있기도 하다(실제로 이 저장소의 서버팩도
configs/authserver.conf 형태) — find_conf_file() 이 몇 가지 흔한 위치를
순서대로 찾아본다."""
import os
import re
import shutil

# 실행파일과 같은 폴더에 없으면 순서대로 찾아볼 하위 폴더 이름들.
_CANDIDATE_SUBDIRS = ("", "configs", "etc", "conf")


def find_conf_file(exe_path, conf_name):
    """exe_path(예: worldserver_exe 설정값) 기준으로 conf_name(예:
    "authserver.conf") 파일을 찾는다. exe 와 같은 폴더 → configs\\ → etc\\ →
    conf\\ 순서로 찾아보고, 없으면 None."""
    if not exe_path:
        return None
    exe_dir = os.path.dirname(exe_path)
    if not exe_dir:
        return None
    for sub in _CANDIDATE_SUBDIRS:
        candidate = os.path.join(exe_dir, sub, conf_name) if sub else os.path.join(exe_dir, conf_name)
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_conf_value(conf_path, key):
    """conf 파일에서 "key = value" 형식의 줄을 찾아 값을 돌려준다(따옴표/뒤쪽
    주석은 정리해서 반환). 못 찾거나 파일을 못 읽으면 None."""
    try:
        with open(conf_path, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, _, v = stripped.partition("=")
                if k.strip() != key:
                    continue
                v = v.split("#", 1)[0].strip()
                if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                    v = v[1:-1]
                return v.strip()
    except OSError:
        pass
    return None


def parse_conf_value_from_text(text, key):
    """parse_conf_value() 의 텍스트 입력 버전 - SSH 로 통째로 가져온 conf 내용처럼
    파일이 아니라 문자열만 있는 경우(remote_conf.py) 에 쓴다."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        if k.strip() != key:
            continue
        v = v.split("#", 1)[0].strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        return v.strip()
    return None


def read_values_from_text(text, keys):
    """read_values() 의 텍스트 입력 버전(remote_conf.py 용)."""
    return {key: parse_conf_value_from_text(text, key) for key in keys}


def parse_database_info_string(value):
    """"host;port;user;password;dbname" 형식(AzerothCore 의 *DatabaseInfo 값)을
    분해한다. 형식이 안 맞으면(세미콜론 4개 미만) None."""
    if not value:
        return None
    parts = [p.strip() for p in value.split(";")]
    if len(parts) < 4:
        return None
    result = {"host": parts[0], "port": parts[1], "user": parts[2], "password": parts[3]}
    if len(parts) >= 5:
        result["database"] = parts[4]
    return result


def read_database_info(exe_path, conf_name, key="LoginDatabaseInfo"):
    """exe_path 근처에서 conf_name 파일을 찾아 key(기본 LoginDatabaseInfo) 값을
    읽어 {"host","port","user","password","database"} dict 로 반환. 파일이
    없거나 값이 없거나 형식이 안 맞으면 None — 호출 쪽에서 그냥 조용히
    건너뛰도록(팝업 없이) 만들어졌다."""
    conf_path = find_conf_file(exe_path, conf_name)
    if not conf_path:
        return None
    raw = parse_conf_value(conf_path, key)
    return parse_database_info_string(raw)


def read_values(conf_path, keys):
    """keys 각각에 대해 parse_conf_value 를 호출해 {key: 원본 문자열 또는 None}
    을 반환한다(못 찾은 키는 None). conf_path 자체가 없으면 전부 None."""
    return {key: parse_conf_value(conf_path, key) for key in keys}


def _split_eol(line):
    for eol in ("\r\n", "\n", "\r"):
        if line.endswith(eol):
            return line[: -len(eol)], eol
    return line, ""


def apply_updates_to_lines(lines, updates):
    """conf 파일 내용(각 원소가 자기 줄바꿈 문자까지 포함한 줄 리스트 - 예:
    str.splitlines(keepends=True) 나 newline="" 로 연 파일의 readlines() 결과)에
    대해, 주석이 아닌 줄에서 정확히 그 키로 시작하고 그 다음이 공백 또는 '=' 로
    바로 이어지는 줄만 찾아 값 부분만 교체한다 - 예를 들어 "Rate.XP.Quest" 를
    찾을 때 "Rate.XP.Quest.DF = 1" 줄은 키 뒤에 '.DF' 가 더 붙어 있어 매치하지
    않는다. 같은 줄에 값 뒤에 '#주석' 이 붙어 있으면 그 주석은 그대로 보존한다.

    파일 입출력이 전혀 없는 순수 함수라 로컬(파일 열기)과 원격(SSH로 텍스트
    가져오기) 양쪽이 이 함수 하나로 똑같은 편집 로직을 공유한다.

    반환: (새 줄 리스트, 실제로 바뀐 키의 집합, 못 찾은 키 리스트)."""
    lines = list(lines)
    pending = dict(updates)
    patterns = {
        key: re.compile(r"^(?P<key>" + re.escape(key) + r")(?P<sep>[ \t]*=[ \t]*)"
                         r"(?P<value>[^#]*)(?P<tail>.*)$")
        for key in pending
    }
    changed = set()
    for i, line in enumerate(lines):
        body, eol = _split_eol(line)
        stripped = body.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        for key, pattern in list(patterns.items()):
            if key in changed:
                continue
            m = pattern.match(body)
            if not m:
                continue
            new_value = str(pending[key])
            lines[i] = f"{m.group('key')}{m.group('sep')}{new_value}{m.group('tail')}{eol}"
            changed.add(key)
            break

    missing = [key for key in updates if key not in changed]
    return lines, changed, missing


def apply_updates_to_text(text, updates):
    """apply_updates_to_lines() 의 텍스트(문자열) 입출력 버전 - SSH 로 통째로
    가져온 conf 내용처럼 파일이 아니라 문자열만 있는 경우(remote_conf.py) 에 쓴다."""
    lines, changed, missing = apply_updates_to_lines(text.splitlines(keepends=True), updates)
    return "".join(lines), changed, missing


def set_values(conf_path, updates):
    """updates: {key: 새 값(문자열로 변환됨)}. conf_path 를 읽어
    apply_updates_to_lines() 로 편집하고 다시 쓴다.

    처음 쓰기 전에 conf_path + ".launcher-bak" 이 아직 없으면 원본을 그대로 한 번
    복사해 둔다 - 사용자가 언제든 원본으로 되돌릴 수 있는 안전망.

    반환: (성공적으로 바뀐 키의 집합, 파일에서 못 찾은 키 리스트). 파일을 아예
    못 열면 (빈 집합, updates 의 모든 키) 를 돌려준다 - 예외를 던지지 않고 호출부가
    사람이 읽을 결과를 표시하게 하는 이 모듈의 기존 관례를 따른다."""
    # newline="" 로 열어서 유니버설 개행 변환을 끈다 - 이 저장소의 실제
    # worldserver.conf 는 LF(\n)만 쓰는데, 변환을 켜둔 채로 다시 쓰면 파이썬이
    # 전부 CRLF(\r\n)로 바꿔버려서 건드리지 않은 줄까지 깨진 것처럼 보이게 된다.
    # 각 줄의 원래 줄바꿈 문자를 그대로 떼어뒀다가 그대로 다시 붙인다.
    try:
        with open(conf_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            lines = f.readlines()
    except OSError:
        return set(), list(updates.keys())

    lines, changed, missing = apply_updates_to_lines(lines, updates)
    if not changed:
        return changed, missing

    backup_path = conf_path + ".launcher-bak"
    if not os.path.isfile(backup_path):
        try:
            shutil.copy2(conf_path, backup_path)
        except OSError:
            pass

    tmp_path = conf_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)
        os.replace(tmp_path, conf_path)
    except OSError:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return set(), list(updates.keys())

    return changed, missing
