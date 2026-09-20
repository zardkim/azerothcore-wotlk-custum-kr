# -*- coding: utf-8 -*-
"""숨겨진 관리자 모드(Ctrl+Shift + ⚙)의 DB 접속 설정. state.py와 같은 이유로
exe 옆(BASE_DIR)에 저장한다 - 배포자가 미리 채워서 나눠주는 config/config.json과
달리, 이건 운영자 본인 PC에서만 생기는 값이라 절대로 빌드에 포함되거나 다른
플레이어에게 배포되면 안 된다(.gitignore 에도 별도로 올려둘 것).

SSH/서버 스크립트 경유 없이 HeidiSQL 등과 똑같은 방식(host/port/계정)으로 DB에
직접 접속해서 백업/복원한다 - db_backup.py 참고."""
import json
import os

from paths import BASE_DIR

ADMIN_CONFIG_PATH = os.path.join(BASE_DIR, "admin_config.json")

DEFAULTS = {
    "db_host": "",
    "db_port": 3307,
    "db_user": "acore",
    "db_password": "acore",
    "auth_db": "acore_auth",
    "char_db": "acore_characters",
    "bot_prefix": "rndbot",
}


def load_admin_config():
    try:
        with open(ADMIN_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    return merged


def save_admin_config(data):
    try:
        with open(ADMIN_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def is_configured(cfg):
    return bool(cfg.get("db_host") and cfg.get("db_user"))
