# -*- coding: utf-8 -*-
"""원격 모드에서 process_manager.ServiceProcess 를 대신하는 "원격판" 서비스
클래스. 로컬 프로세스를 직접 못 보니 네트워크로만 상태를 판단한다:
mysql/authserver 는 TCP 포트 연결 시도, worldserver 는 이미 있는 SOAP
"server info" 호출 성공 여부로 판단한다 - SSH 는 전혀 안 쓴다(포트/SOAP 는
원래 네트워크 프로토콜이라 원격 호스트를 그대로 대상으로 호출하면 됨).

app.py 의 새로고침 로직(_refresh_worker/_apply_refresh)은 이 클래스가
process_manager.ServiceProcess 와 똑같은 메서드(status/pid/console_visible/
start/stop)를 갖고 있다고만 가정하고 동작하므로, 새 UI 코드 없이 모드만
갈아끼우면 메인 화면이 그대로 재사용된다. ServiceProcess 가 host/port 를
단순 속성으로 두고 apply_config() 가 저장할 때마다 그 값을 바로 갱신하는
관례(process_manager.ServiceProcess.host 등)를 그대로 따른다."""
import socket

import soap_client
from process_manager import RUNNING, STOPPED  # noqa: F401 (app.py 에서 재사용)

_PORT_TIMEOUT = 2.0
_SOAP_TIMEOUT = 8


class RemoteServiceProcess:
    """kind="port" (mysql/authserver, TCP 연결만 확인) 또는 kind="soap"
    (worldserver, GM 명령 성공 여부로 확인). host/port/soap_port/gm_account/
    gm_password 는 다른 ServiceProcess 처럼 단순 속성이라, LauncherApp.apply_config()
    가 설정 저장 때마다 바로 덮어써서 항상 최신 값을 쓴다."""

    def __init__(self, key, display_name, kind, port=None):
        self.key = key
        self.display_name = display_name
        self.kind = kind
        self.host = ""
        self.port = port
        self.soap_port = 7878
        self.gm_account = ""
        self.gm_password = ""

    def status(self):
        if not self.host:
            return STOPPED
        if self.kind == "port":
            if not self.port:
                return STOPPED
            try:
                with socket.create_connection((self.host, int(self.port)), timeout=_PORT_TIMEOUT):
                    return RUNNING
            except OSError:
                return STOPPED
        # kind == "soap": worldserver 는 전용 포트를 직접 열어보는 대신, 이미
        # 계정 관리/게임 설정에서 쓰는 것과 같은 SOAP "server info" 호출이
        # 성공하는지로 판단한다(GM 계정이 설정돼 있어야 확인 가능).
        if not self.gm_account or not self.gm_password:
            return STOPPED
        ok, _msg = soap_client.execute_command(
            self.host, int(self.soap_port), self.gm_account, self.gm_password,
            "server info", timeout=_SOAP_TIMEOUT,
        )
        return RUNNING if ok else STOPPED

    def pid(self):
        return None

    def console_visible(self):
        return False

    def start(self, show_console=False):
        return False, "원격 모드에서는 시작을 지원하지 않습니다. 원격 서버에서 직접 실행해 주세요."

    def stop(self, timeout=10):
        return False, "원격 모드에서는 중지를 지원하지 않습니다. 원격 서버에서 직접 중지해 주세요."
