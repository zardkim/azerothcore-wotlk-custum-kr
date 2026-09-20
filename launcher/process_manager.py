# -*- coding: utf-8 -*-
"""mysqld / authserver / worldserver 를 콘솔창 없이 백그라운드로 실행하고
상태를 확인/중지/재시작하는 로직. 콘솔은 실제로는 생성해두되 숨겨서 실행하고,
나중에 사용자가 원하면 그 콘솔창을 다시 보여줄 수 있게 한다 (winproc 참고)."""
import os
import socket
import subprocess
import time

import psutil

import winproc

CREATE_NO_WINDOW = 0x08000000

STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
STOPPING = "stopping"
ERROR = "error"

STATUS_LABEL = {
    STOPPED: "정지됨",
    STARTING: "시작 중...",
    RUNNING: "실행 중",
    STOPPING: "중지 중...",
    ERROR: "오류",
}


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)) if path else ""


class ServiceProcess:
    """하나의 서버 프로세스(mysqld / authserver / worldserver)를 관리."""

    def __init__(self, key, display_name, port):
        self.key = key
        self.display_name = display_name
        self.port = port
        self.host = "127.0.0.1"
        self.console_title = f"WOWLegends-console-{key}"
        self._pid = None
        self._transient_stopping_until = 0.0
        self._last_error = None

    # ---- 외부에서 매번 최신 경로/작업폴더를 넣어줌 ----
    def configure(self, exe_path, cwd, args=None, extra_match_names=None):
        self.exe_path = exe_path
        self.cwd = cwd
        self.args = args or []
        # psutil 로 프로세스를 재탐색할 때 exe 경로 비교에 쓸 이름들
        self.extra_match_names = extra_match_names or []

    # ---------------- 내부 상태 탐지 ----------------
    def _is_batch_target(self):
        return bool(self.exe_path) and winproc.is_batch_file(self.exe_path)

    def _matches_batch(self, proc):
        """exe_path 가 .bat/.cmd 인 경우: 실제로 뜨는 건 cmd.exe 이고 그 안에서
        진짜 실행 파일(mysqld.exe 등)이 자식으로 뜬다. exe() 경로로는 절대 못 맞추므로
        cmd.exe 의 명령줄에 그 배치파일 이름이 들어있는지로 우리가 띄운 게 맞는지 확인한다."""
        try:
            if (proc.name() or "").lower() != "cmd.exe":
                return False
            bat_name = os.path.basename(self.exe_path).lower()
            return bat_name in " ".join(proc.cmdline()).lower()
        except Exception:
            return False

    def _find_running_pid(self):
        """이미 실행 중인 프로세스를 exe 경로로 재탐색 (런처를 껐다 켜도 상태 인식).
        exe 경로를 정확히 읽어서 비교할 수 있는 경우에만 매치시킨다 (이름만으로
        추측 매칭하면 전혀 무관한 프로세스를 우리 서버로 착각할 수 있어 제외함).
        단, .bat/.cmd 로 설정된 경우는 cmd.exe 의 명령줄로 매칭한다."""
        if not self.exe_path:
            return None
        is_batch = self._is_batch_target()
        target = _norm(self.exe_path)
        for proc in psutil.process_iter(["pid", "exe"]):
            try:
                exe = proc.info.get("exe")
                if exe and _norm(exe) == target:
                    return proc.info["pid"]
                if is_batch and self._matches_batch(proc):
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _pid_alive(self, pid):
        """pid 가 살아있을 뿐 아니라 실제로 우리가 실행한 그 exe(또는 배치파일)가 맞는지까지 확인.
        (Windows 는 죽은 프로세스의 PID 번호를 다른 프로세스에 재사용할 수 있어서,
        경로 재확인 없이 pid_exists 만 보면 엉뚱한 프로세스를 실행 중으로 오인함)"""
        if pid is None:
            return False
        try:
            if not psutil.pid_exists(pid):
                return False
            if not self.exe_path:
                return True
            proc = psutil.Process(pid)
            exe = proc.exe()
            if _norm(exe) == _norm(self.exe_path):
                return True
            if self._is_batch_target():
                return self._matches_batch(proc)
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception:
            return False

    def is_port_open(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.4):
                return True
        except OSError:
            return False

    def status(self) -> str:
        now = time.time()
        # 프로세스가 살아있는지 확인 (기억해둔 pid 우선, 없으면 재탐색)
        if self._pid and self._pid_alive(self._pid):
            pid = self._pid
        else:
            pid = self._find_running_pid()
            self._pid = pid

        if now < self._transient_stopping_until:
            return STOPPING

        if pid is not None:
            return RUNNING if self.is_port_open() else STARTING

        # pid 를 못 찾았어도(.bat 로 띄운 경우 등, 실행 파일 경로가 우리가 아는 것과 다름)
        # 포트가 응답하면 실행 중인 것으로 본다.
        return RUNNING if self.is_port_open() else STOPPED

    def pid(self):
        return self._pid

    # ---------------- 시작 ----------------
    def start(self, show_console=False):
        if not self.exe_path or not os.path.isfile(self.exe_path):
            self._last_error = f"실행파일을 찾을 수 없습니다: {self.exe_path}"
            return False, self._last_error

        if self.status() in (RUNNING, STARTING):
            return True, None

        try:
            self._pid = winproc.spawn_console_process(
                self.exe_path, self.args, self.cwd, self.console_title,
                visible=show_console,
            )
            self._last_error = None
            return True, None
        except OSError as e:
            self._last_error = str(e)
            return False, self._last_error

    # ---------------- 콘솔창 보기 ----------------
    def show_console(self):
        """숨겨둔 콘솔창을 다시 보여준다. 실행 중이 아니면 False.
        pid 기반(AttachConsole)으로 찾기 때문에 서버가 스스로 콘솔 제목을 바꿔도 찾을 수 있다."""
        pid = self._pid or self._find_running_pid()
        if not pid:
            return False
        return winproc.show_console(pid)

    def hide_console(self):
        pid = self._pid or self._find_running_pid()
        if not pid:
            return False
        return winproc.hide_console(pid)

    def toggle_console(self):
        """지금 보이면 숨기고, 숨겨져 있으면 보여준다."""
        pid = self._pid or self._find_running_pid()
        if not pid:
            return False
        if winproc.is_console_visible(pid):
            return winproc.hide_console(pid)
        return winproc.show_console(pid)

    def console_visible(self):
        pid = self._pid or self._find_running_pid()
        if not pid:
            return False
        return winproc.is_console_visible(pid)

    # ---------------- 중지 ----------------
    def _wait_until_dead(self, pid, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._pid_alive(pid):
                return True
            time.sleep(0.4)
        return False

    def stop(self, timeout=10):
        pid = self._pid or self._find_running_pid()
        if not pid or not self._pid_alive(pid):
            self._pid = None
            return True, None

        self._transient_stopping_until = time.time() + timeout

        # 1) 정상 종료를 시도할 방법이 있으면(mysql 의 mysqladmin shutdown 등) 먼저 시도.
        #    방법 자체가 없으면(authserver/worldserver) 기다려봐야 아무 일도 안 일어나므로
        #    바로 다음 단계로 넘어간다 (예전엔 여기서 이유 없이 최대 timeout 초를 그냥
        #    흘려보내는 버그가 있었음).
        if self._graceful_stop() and self._wait_until_dead(pid, timeout):
            self._pid = None
            self._transient_stopping_until = 0.0
            return True, None

        # 2) 콘솔 창에 닫기 요청(사용자가 창의 X 를 누른 것과 동일 효과) — 대부분의 콘솔
        #    프로그램은 이걸로 곱게 종료된다.
        winproc.close_console_window(pid)
        if self._wait_until_dead(pid, 3):
            self._pid = None
            self._transient_stopping_until = 0.0
            return True, None

        # 3) 그래도 살아있으면 강제 종료. 콘솔 창을 실제로 들고 있는 프로세스(conhost.exe 등,
        #    taskkill /T 로는 안 딸려오는 경우가 있음)가 따로 있으면 그것도 같이 정리해서
        #    빈 콘솔창이 고아로 남지 않게 한다.
        owner_pid = winproc.get_console_owner_pid(pid)
        kill_pids = {pid} | ({owner_pid} if owner_pid else set())
        for kp in kill_pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(kp), "/T", "/F"],
                    creationflags=CREATE_NO_WINDOW,
                    capture_output=True,
                    timeout=10,
                )
            except Exception as e:
                self._last_error = str(e)

        time.sleep(0.5)
        self._transient_stopping_until = 0.0
        self._pid = None
        return True, None

    def _graceful_stop(self):
        """서비스별 정상 종료 시도 (기본은 아무것도 안 함, mysql 은 오버라이드)."""
        return False

    def restart(self):
        self.stop()
        time.sleep(1.0)
        return self.start()

    def last_error(self):
        return self._last_error


class MysqlProcess(ServiceProcess):
    def __init__(self):
        super().__init__("mysql", "MySQL", 3306)
        self.mysqladmin_exe = None

    def configure(self, exe_path, cwd, args=None, extra_match_names=None, mysqladmin_exe=None):
        super().configure(exe_path, cwd, args, extra_match_names)
        self.mysqladmin_exe = mysqladmin_exe

    def _graceful_stop(self):
        if not self.mysqladmin_exe or not os.path.isfile(self.mysqladmin_exe):
            return False
        try:
            subprocess.run(
                [self.mysqladmin_exe, "-u", "root", "shutdown"],
                creationflags=CREATE_NO_WINDOW,
                capture_output=True,
                timeout=15,
            )
            return True
        except Exception as e:
            self._last_error = str(e)
            return False


def launch_client(exe_path):
    """WoW 클라이언트는 콘솔이 아니라 일반 GUI 게임이므로 그냥 보이게 실행."""
    if not exe_path or not os.path.isfile(exe_path):
        return False, f"클라이언트 실행파일을 찾을 수 없습니다: {exe_path}"
    try:
        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
        return True, None
    except OSError as e:
        return False, str(e)
