# -*- coding: utf-8 -*-
"""실행 중 바뀌는 상태(사용자가 고른 실제 설치 경로) 저장. config.py가 다루는
config/config.json은 배포자가 미리 채워서 exe와 함께 나눠주는 "기본값"이고, 이 파일은
그 반대로 이 PC에서 실행하면서 생기는 값이라 exe 옆(BASE_DIR)에 별도로 저장한다."""
import json
import os

from paths import BASE_DIR

STATE_PATH = os.path.join(BASE_DIR, "install_state.json")


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(data):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def get_install_dir(cfg):
    """마지막으로 사용자가 설치했던 폴더. 아직 한 번도 설치한 적 없으면
    config.json의 기본 위치(exe 기준 client_dir)로 대체."""
    saved = load_state().get("install_dir")
    if saved:
        return saved
    return os.path.join(BASE_DIR, cfg["client_dir"])


def set_install_dir(path):
    data = load_state()
    data["install_dir"] = path
    save_state(data)
