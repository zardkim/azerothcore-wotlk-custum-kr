# -*- coding: utf-8 -*-
"""웹사이트의 "지금 플레이하기"가 이미 설치된 런처를 직접 실행할 수 있도록,
Discord(discord://)·Steam(steam://)과 같은 방식으로 전용 URL 프로토콜을 등록하고,
이미 떠 있는 인스턴스가 있으면 새로 띄우는 대신 그 창을 앞으로 가져온다.

두 기능 모두 exe로 빌드되어(frozen) 실행 중일 때만 의미가 있다 - 개발 중
`python app.py` 실행에는 적용하지 않는다(app.py에서 그 판단을 하고 이 모듈을 호출)."""
import ctypes
import winreg

SCHEME = "wowlegends"
_MUTEX_NAME = "Local\\WOWLegendsPlayerLauncherMutex"
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9


def ensure_protocol_registered(exe_path: str) -> None:
    """HKEY_CURRENT_USER에만 쓰므로 관리자 권한이 필요 없다. 매번(앱 실행마다)
    다시 써도 비용이 거의 없어서, 이미 올바른지 먼저 확인하는 대신 그냥 항상
    최신 값으로 덮어쓴다 - 설치 위치가 바뀌는 경우는 없지만 혹시 레지스트리가
    손상되었을 때도 다음 실행에서 스스로 복구된다. 레지스트리 접근 자체가
    막혀 있는 환경이어도(그룹 정책 등) 런처 실행 자체는 막지 않는다."""
    command = f'"{exe_path}" "%1"'
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{SCHEME}") as key:
            winreg.SetValueEx(key, None, 0, winreg.REG_SZ, f"URL:{SCHEME} Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, rf"Software\Classes\{SCHEME}\shell\open\command"
        ) as cmd_key:
            winreg.SetValueEx(cmd_key, None, 0, winreg.REG_SZ, command)
    except OSError:
        pass


def acquire_single_instance_lock(window_title: str):
    """이미 실행 중인 인스턴스가 있으면 그 창을 앞으로 가져오고 None을 돌려준다
    (호출부는 새 창을 띄우지 말고 바로 종료해야 함). 없으면 뮤텍스 핸들을
    돌려준다 - 반환값을 변수에 계속 들고 있어야 프로세스가 끝날 때까지
    "실행 중"으로 유지된다(지역 변수라 함수 리턴과 함께 사라지면 즉시 풀림)."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    already_running = ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
    if not already_running:
        return mutex

    hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, _SW_RESTORE)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    return None
