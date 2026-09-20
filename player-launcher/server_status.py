# -*- coding: utf-8 -*-
"""서버 온라인/오프라인 확인 — TCP 포트 연결만 시도한다(관리자용 런처의
soap_client.py처럼 GM 계정으로 인증하는 방식은 일부러 쓰지 않는다: 이 런처는
불특정 다수 플레이어에게 배포되는 exe라서, 접속자 수를 보여주려고 실제 GM 계정
정보를 exe 안에 심어두면 누구나 그 exe를 분석해서 GM 권한을 빼낼 수 있다).
그래서 접속자 수/가동시간 없이 온라인 여부만 보여준다."""
import socket

_TIMEOUT = 2.0


def check_port(host, port, timeout=_TIMEOUT):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def check_server(auth_host, auth_port, world_host, world_port):
    """인증 서버 + 월드 서버 포트가 둘 다 열려 있어야 온라인으로 판단한다
    (둘 중 하나만 켜져 있으면 실제로는 접속이 안 되므로)."""
    return check_port(auth_host, auth_port) and check_port(world_host, world_port)
