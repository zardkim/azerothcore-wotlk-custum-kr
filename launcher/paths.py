# -*- coding: utf-8 -*-
"""이 런처가 스크립트로 실행되는지, PyInstaller 로 빌드된 exe 로 실행되는지에
따라 기준 폴더(설정/프리셋/assets 를 찾을 위치)를 계산한다.
빌드된 exe 는 exe 가 있는 폴더를 기준으로 삼아야 assets/config.json 이 제대로 보인다."""
import os
import sys


def _compute_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _compute_base_dir()
