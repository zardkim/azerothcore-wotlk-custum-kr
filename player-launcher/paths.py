# -*- coding: utf-8 -*-
"""폴더 두 종류를 구분한다:

- BASE_DIR: exe(또는 스크립트)가 실제로 놓여있는 위치. install_state.json처럼
  실행 중 새로 쓰는 파일은 항상 여기 기준.
- RESOURCE_DIR: assets/config.json처럼 빌드에 내장된(읽기 전용) 자료를 찾을 위치.
  onefile로 빌드하면 PyInstaller가 실행할 때마다 임시 폴더(sys._MEIPASS)에 풀어두므로
  BASE_DIR과 다르다 — onedir/스크립트 실행이면 둘이 같다."""
import os
import sys


def _compute_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _compute_resource_dir():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return BASE_DIR


BASE_DIR = _compute_base_dir()
RESOURCE_DIR = _compute_resource_dir()
