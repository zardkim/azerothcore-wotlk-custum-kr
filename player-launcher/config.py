# -*- coding: utf-8 -*-
"""플레이어용 런처 설정. 관리자용 런처와 달리 플레이어가 직접 건드릴 항목이 없으므로
(서버 경로/DB/SSH 등 설정 화면 자체가 없음), config/config.json 하나에 배포자가
미리 채워서 exe와 함께 배포한다. 파일이 없으면 아래 DEFAULTS로 동작한다."""
import json
import os

from paths import RESOURCE_DIR

CONFIG_DIR = os.path.join(RESOURCE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    # 서버 상태 확인 + 접속에 쓰는 렐름 주소
    "auth_host": "127.0.0.1",
    "auth_port": 3724,
    "world_host": "127.0.0.1",
    "world_port": 8085,
    # 클라이언트 설치 위치 (이 exe 기준 상대 경로) 및 실행 파일 이름
    "client_dir": "client",
    "client_exe": "Wow.exe",
    # 클라이언트 배포 파일(7-Zip SFX exe) 다운로드 주소
    "download_url": "",
    # 클라이언트 폴더의 realmlist.wtf에 자동으로 써줄 접속 주소
    # ("set realmlist <값>" 형태로 저장됨). 비워두면 auth_host를 그대로 씀.
    # realmlist_api_url이 설정되어 있고 응답이 오면 이 값 대신 그 결과를 쓴다.
    "realmlist": "",
    # 웹사이트(ac-web)의 공개 렐름리스트 API 주소. 설정해두면 설치 시 및 실행할 때마다
    # 이 주소에서 최신 접속 주소를 가져와 realmlist.wtf를 자동으로 맞춰준다
    # (예: "https://xbox.pe.kr:11220/api/realmlist"). 비워두면 동기화를 하지 않고
    # 위 realmlist 값을 그대로 쓴다.
    "realmlist_api_url": "",
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


# client_exe(config.json에 배포자가 지정한 이름) 외에 흔히 쓰이는 클라이언트 실행
# 파일 이름들. 설정(⚙)에서 사용자가 이미 설치되어 있는 폴더를 직접 지정했을 때, 그
# 폴더의 실제 실행 파일 이름이 config.json에 적힌 이름과 다르면(예: 배포자는
# "Wow.exe"로 설정해뒀는데 실제 클라이언트는 "Wow_hd.exe") PLAY 대신 다운로드 버튼이
# 잘못 표시되는 문제를 막기 위한 대체 후보 목록.
CLIENT_EXE_CANDIDATES = ("Wow.exe", "Wow_hd.exe")


def find_client_exe(install_dir, cfg):
    """install_dir(사용자가 실제로 설치를 골랐던 또는 이미 설치되어 있는 폴더 -
    state.get_install_dir()로 얻음) 안에서 클라이언트 실행 파일을 찾는다.
    config.json의 client_exe를 먼저 확인하고, 없으면 CLIENT_EXE_CANDIDATES도 차례로
    확인한다. 찾으면 전체 경로, 못 찾으면 None."""
    if not install_dir:
        return None
    names = [cfg["client_exe"]]
    names += [c for c in CLIENT_EXE_CANDIDATES if c.lower() != cfg["client_exe"].lower()]
    for name in names:
        path = os.path.join(install_dir, name)
        if os.path.isfile(path):
            return path
    return None


def realmlist_value(cfg):
    return cfg["realmlist"].strip() or cfg["auth_host"]
