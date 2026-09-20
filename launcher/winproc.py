# -*- coding: utf-8 -*-
"""Win32 API로 '숨겨진 콘솔' 프로세스를 띄우고, 나중에 그 콘솔창을 다시 보여주는 유틸.

CREATE_NO_WINDOW 로 띄우면 콘솔 자체가 아예 생성되지 않아서 나중에 "보여줄" 방법이 없다.
그래서 콘솔은 실제로 만들되(CREATE_NEW_CONSOLE) 시작할 때 창만 숨겨두고(SW_HIDE),
그 콘솔에 고유한 제목을 붙여서 나중에 FindWindow 로 다시 찾아 보여준다."""
import ctypes
import os
from ctypes import wintypes

CREATE_NEW_CONSOLE = 0x00000010
STARTF_USESHOWWINDOW = 0x00000001
SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9

kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
    wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

kernel32.AttachConsole.argtypes = [wintypes.DWORD]
kernel32.AttachConsole.restype = wintypes.BOOL
kernel32.FreeConsole.restype = wintypes.BOOL
kernel32.GetConsoleWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

WM_CLOSE = 0x0010


def _quote(arg):
    return f'"{arg}"' if " " in arg and not arg.startswith('"') else arg


def is_batch_file(exe_path):
    return exe_path.lower().endswith((".bat", ".cmd"))


def _build_cmdline(exe_path, args):
    """.bat/.cmd 는 CreateProcessW 가 직접 실행할 수 없으므로 cmd.exe /c 로 감싼다."""
    if is_batch_file(exe_path):
        comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        inner = " ".join(_quote(a) for a in [exe_path, *args])
        return f'{_quote(comspec)} /c "{inner}"'
    return " ".join(_quote(a) for a in [exe_path, *args])


def spawn_console_process(exe_path, args, cwd, title, visible=False):
    """새 콘솔을 가진 프로세스를 띄우고 pid 를 반환한다.
    visible=False 면 콘솔은 실제로 생성되지만 창은 숨긴 채로 시작한다.
    exe_path 가 .bat/.cmd 면 cmd.exe /c 로 감싸서 실행하며, 이때 반환되는 pid 는
    그 cmd.exe 의 pid 이다 (배치 스크립트가 내부에서 띄우는 실제 실행 파일은 그 자식 프로세스)."""
    cmdline = _build_cmdline(exe_path, args)
    buf = ctypes.create_unicode_buffer(cmdline)

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(STARTUPINFOW)
    si.dwFlags = STARTF_USESHOWWINDOW
    si.wShowWindow = SW_SHOW if visible else SW_HIDE
    si.lpTitle = title
    pi = PROCESS_INFORMATION()

    ok = kernel32.CreateProcessW(
        None, buf, None, None, False,
        CREATE_NEW_CONSOLE, None, cwd, ctypes.byref(si), ctypes.byref(pi),
    )
    if not ok:
        err = ctypes.GetLastError()
        raise OSError(err, ctypes.FormatError(err))
    kernel32.CloseHandle(pi.hProcess)
    kernel32.CloseHandle(pi.hThread)
    return pi.dwProcessId


def get_console_hwnd(pid):
    """대상 프로세스(pid)의 콘솔 창 핸들을 찾는다.

    창 제목으로 찾으면 그 프로세스가 스스로 SetConsoleTitle 로 제목을 바꿔버리는 경우
    (AzerothCore 계열 서버들이 실제로 그렇게 함) 못 찾게 되므로, 대신 그 프로세스의
    콘솔에 우리가 잠깐 AttachConsole 로 붙었다가 GetConsoleWindow 로 핸들만 얻고
    바로 떨어져 나오는 방식을 쓴다. pid 만 맞으면 제목이 뭐로 바뀌었든 항상 찾을 수 있다."""
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        return None
    try:
        hwnd = kernel32.GetConsoleWindow()
    finally:
        kernel32.FreeConsole()
    return hwnd if hwnd else None


def show_console(pid):
    hwnd = get_console_hwnd(pid)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.SetForegroundWindow(hwnd)
    return True


def hide_console(pid):
    hwnd = get_console_hwnd(pid)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_HIDE)
    return True


def is_console_visible(pid):
    hwnd = get_console_hwnd(pid)
    if not hwnd:
        return False
    return bool(user32.IsWindowVisible(hwnd))


def get_console_owner_pid(pid):
    """콘솔 창을 실제로 소유한 프로세스의 pid.
    Windows 10+ 에서는 콘솔 창이 conhost.exe 소속인 경우가 많아서, 대상 프로세스만
    taskkill 해서는 그 창이 안 닫힌 채(고아 창으로) 남을 수 있다. 이 pid 도 같이 정리해야 한다."""
    hwnd = get_console_hwnd(pid)
    if not hwnd:
        return None
    owner_pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
    return owner_pid.value or None


def close_console_window(pid):
    """콘솔 창에 WM_CLOSE 를 보낸다 — 사용자가 창의 X 를 누른 것과 같은 효과(그 콘솔에
    붙은 프로세스들에 CTRL_CLOSE_EVENT 가 가고, 창 자체도 정상적으로 닫힘).
    taskkill 로 강제 종료하기 전에 먼저 시도하면 좋다."""
    hwnd = get_console_hwnd(pid)
    if not hwnd:
        return False
    return bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))
