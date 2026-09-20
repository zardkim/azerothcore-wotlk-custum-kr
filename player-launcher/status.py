# -*- coding: utf-8 -*-
"""theme.status_colors()가 참조하는 상태 상수. 관리자용 런처의 process_manager.py는
로컬 프로세스 시작/중지까지 다루지만, 플레이어용 런처는 네트워크로 온라인/오프라인만
확인하면 되므로 그 무거운 모듈 전체 대신 상수만 따로 뗀 작은 모듈을 쓴다."""
STOPPED = "stopped"
STARTING = "starting"
RUNNING = "running"
STOPPING = "stopping"
ERROR = "error"
