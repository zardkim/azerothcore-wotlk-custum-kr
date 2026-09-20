# -*- coding: utf-8 -*-
"""원격(SSH) 서버의 conf 파일을 읽고 쓰는 아주 작은 래퍼. Windows 10/11 에 기본
내장된 OpenSSH 클라이언트(ssh.exe/scp.exe) 를 subprocess 로 호출한다 - paramiko
같은 라이브러리를 추가로 묶지 않고, 사용자가 이미 쓰고 있는 ~/.ssh/config 나
known_hosts 를 그대로 활용하기 위함이다. 인증은 키 파일만 지원한다(비밀번호를
설정 파일에 평문으로 저장하고 싶지 않아서)."""
import os
import shutil
import subprocess
import tempfile

CREATE_NO_WINDOW = 0x08000000
_TIMEOUT = 15


def ssh_client_available():
    """ssh.exe / scp.exe 가 PATH 에 있는지. 대부분의 Win10/11 은 기본 내장이라
    거의 항상 True."""
    return bool(shutil.which("ssh")) and bool(shutil.which("scp"))


def _ssh_base_args(host, port, user, key_path):
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=accept-new"]
    if port:
        args += ["-p", str(port)]
    if key_path:
        args += ["-i", key_path]
    args.append(f"{user}@{host}" if user else host)
    return args


def read_text(host, port, user, key_path, remote_path, timeout=_TIMEOUT):
    """remote_path 파일 내용을 문자열로 읽어온다. 실패(연결 안 됨/파일 없음/권한
    없음 등)하면 None - 호출부가 "원격 서버에 연결하지 못했습니다" 같은 안내를
    보여주도록, 예외를 던지지 않는 이 프로젝트의 conf_reader.py 관례를 따른다."""
    content, _err = read_text_detailed(host, port, user, key_path, remote_path, timeout)
    return content


def read_text_detailed(host, port, user, key_path, remote_path, timeout=_TIMEOUT):
    """read_text() 와 같지만 실패 이유(문자열)까지 같이 돌려준다 - 설정 화면의
    "연결 테스트" 버튼처럼 사용자에게 왜 안 됐는지 보여줘야 하는 경우에 쓴다.
    성공하면 (내용, None), 실패하면 (None, 이유)."""
    if not host:
        return None, "호스트 주소가 비어 있습니다."
    if not ssh_client_available():
        return None, "이 컴퓨터에 SSH 클라이언트(ssh.exe)가 없습니다."
    if not remote_path:
        return None, "conf 경로가 비어 있습니다."
    cmd = _ssh_base_args(host, port, user, key_path) + [f"cat {shell_quote(remote_path)}"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return None, f"{timeout}초 안에 응답이 없습니다 (호스트/포트나 방화벽을 확인하세요)."
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        return None, stderr or f"파일을 읽지 못했습니다 (종료 코드 {result.returncode})."
    try:
        return result.stdout.decode("utf-8"), None
    except UnicodeDecodeError:
        return result.stdout.decode("utf-8", errors="replace"), None


def write_text(host, port, user, key_path, remote_path, content, timeout=_TIMEOUT):
    """write_text_detailed() 의 반환값에서 성공 여부(bool)만 돌려주는 얇은
    래퍼 - 기존 호출부(app.py 는 이제 write_text_detailed 를 직접 쓰지만, 혹시
    모를 다른 참조를 위해 남겨둔다)."""
    ok, _msg = write_text_detailed(host, port, user, key_path, remote_path, content, timeout)
    return ok


def write_text_detailed(host, port, user, key_path, remote_path, content, timeout=_TIMEOUT):
    """content 를 remote_path 에 통째로 덮어쓴다. 로컬 임시 파일에 먼저 쓴 뒤
    scp 로 올리고, 원격에서 mv 로 한 번에 옮겨 원자성을 보강한다(중간에 끊겨도
    대상 파일이 반쯤 쓰인 상태로 남지 않도록). 성공하면 (True, None), 실패하면
    (False, 이유) - scp 단계(업로드)와 mv 단계(원격 파일시스템에서 이동)는 실패
    원인이 서로 다르므로(예: scp 는 되는데 mv 만 권한 때문에 거부되는 경우도
    있음) 각각 어느 단계에서 막혔는지 알 수 있게 구분해서 돌려준다."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not remote_path:
        return False, "conf 경로가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(scp.exe)가 없습니다."
    tmp_local = None
    try:
        fd, tmp_local = tempfile.mkstemp(prefix="launcher_conf_")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)

        remote_tmp = remote_path + ".launcher-upload.tmp"

        def build_scp_args(legacy):
            args = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                    "-o", "StrictHostKeyChecking=accept-new"]
            if legacy:
                # 최신 Windows OpenSSH 클라이언트(9.0+)는 scp 기본 동작을 SFTP
                # 프로토콜로 바꿨는데, 시놀로지 등 일부 sshd 는 sftp-server
                # 서브시스템이 아예 설정돼 있지 않아 "subsystem request failed"
                # 로 거부한다. -O 는 예전(exec 기반) scp 프로토콜을 강제해서 이
                # 서브시스템 없이도 동작한다 - -O 를 모르는 구버전 클라이언트는
                # 애초에 이 문제 자체가 없으므로(이미 exec 방식이 기본) -O 없이
                # 첫 시도에서 성공한다.
                args.append("-O")
            if port:
                args += ["-P", str(port)]
            if key_path:
                args += ["-i", key_path]
            target = f"{user}@{host}:{remote_tmp}" if user else f"{host}:{remote_tmp}"
            args += [tmp_local, target]
            return args

        def run_scp(legacy):
            try:
                result = subprocess.run(
                    build_scp_args(legacy), capture_output=True, timeout=timeout,
                    creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            except subprocess.TimeoutExpired:
                return False, f"업로드(scp) {timeout}초 안에 응답이 없습니다."
            except (OSError, subprocess.SubprocessError) as e:
                return False, f"업로드(scp) 실패: {e}"
            if result.returncode == 0:
                return True, None
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            return False, f"업로드(scp) 실패: {stderr or f'종료 코드 {result.returncode}'}"

        ok, err = run_scp(legacy=False)
        if not ok and err and "subsystem" in err.lower():
            # sftp-server 서브시스템이 없어서 실패한 것으로 보이니, 구식 scp
            # 프로토콜(-O)로 한 번 더 시도해본다.
            ok, err = run_scp(legacy=True)
        if not ok:
            return False, err

        mv_cmd = _ssh_base_args(host, port, user, key_path) + [
            f"mv {shell_quote(remote_tmp)} {shell_quote(remote_path)}"
        ]
        try:
            result = subprocess.run(
                mv_cmd, capture_output=True, timeout=timeout,
                creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            return False, f"원격 파일 교체(mv) {timeout}초 안에 응답이 없습니다."
        except (OSError, subprocess.SubprocessError) as e:
            return False, f"원격 파일 교체(mv) 실패: {e}"
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            return False, f"원격 파일 교체(mv) 실패: {stderr or f'종료 코드 {result.returncode}'}"
        return True, None
    finally:
        if tmp_local:
            try:
                os.remove(tmp_local)
            except OSError:
                pass


def chmod_add_read(host, port, user, key_path, remote_path, timeout=_TIMEOUT):
    """remote_path 에 '다른 사용자도 읽기 가능'(o+r) 권한만 추가한다 - 쓰기/실행
    권한이나 소유자/그룹은 건드리지 않는 최소 변경. "연결 테스트"가 conf 파일을
    권한 문제로 못 읽었을 때 자동으로 한 번 시도해보는 용도. 파일 소유자가 SSH
    로그인 계정과 다르면(도커 컨테이너 안쪽 UID로 마운트된 경우 등) sudo 없인
    chmod 자체가 거부될 수 있는데, 그 경우도 예외를 던지지 않고 이유를 그대로
    돌려준다."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not remote_path:
        return False, "conf 경로가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(ssh.exe)가 없습니다."
    cmd = _ssh_base_args(host, port, user, key_path) + [f"chmod o+r {shell_quote(remote_path)}"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return False, f"{timeout}초 안에 응답이 없습니다."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if result.returncode == 0:
        return True, "권한 변경 성공"
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    return False, stderr or f"chmod 종료 코드 {result.returncode}"


def check_connection(host, port, user, key_path, timeout=8):
    """SSH 접속만 확인(파일 접근 없이) - 설정 화면의 "연결 테스트" 버튼용.
    성공하면 (True, "연결 성공"), 실패하면 (False, 이유)."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(ssh.exe)가 없습니다."
    cmd = _ssh_base_args(host, port, user, key_path) + ["echo ok"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return False, f"{timeout}초 안에 응답이 없습니다 (호스트/포트나 방화벽을 확인하세요)."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if result.returncode == 0:
        return True, "연결 성공"
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    return False, stderr or f"ssh 종료 코드 {result.returncode}"


def shell_quote(path):
    """원격(리눅스) 셸에 넘길 경로를 작은따옴표로 감싼다(공백/특수문자 대비)."""
    return "'" + path.replace("'", "'\\''") + "'"


def run_command(host, port, user, key_path, command, timeout=120):
    """임의의 원격 셸 명령을 실행하고 (성공여부, 출력 또는 실패 이유)를 돌려준다.
    deploy/scripts/backup.sh·restore.sh 처럼 실행에 몇 초~몇 분 걸릴 수 있는 명령용 -
    check_connection() 과 같은 패턴이지만 timeout 기본값을 훨씬 넉넉하게 뒀다.
    stdout/stderr 를 합쳐서 돌려준다(백업/복원 스크립트는 진행 메시지를 stdout 에
    쓰므로 둘을 분리해서 보여줄 실익이 없다)."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(ssh.exe)가 없습니다."
    if not command:
        return False, "실행할 명령이 비어 있습니다."
    cmd = _ssh_base_args(host, port, user, key_path) + [command]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return False, f"{timeout}초 안에 끝나지 않았습니다 (원격 서버에서 직접 진행 상황을 확인해 주세요)."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    out = result.stdout.decode("utf-8", errors="replace")
    err = result.stderr.decode("utf-8", errors="replace").strip()
    combined = (out + ("\n" + err if err else "")).strip()
    if result.returncode != 0:
        return False, combined or f"종료 코드 {result.returncode}"
    return True, combined


def _run_scp(local_path, remote_spec, port, key_path, timeout, upload, legacy):
    """scp 한 번 실행. upload=True 면 local_path -> remote_spec, False 면 반대.
    write_text_detailed() 와 같은 -O 폴백 이유(최신 Windows OpenSSH의 SFTP 기본
    전환 vs 일부 sshd 의 sftp-server 서브시스템 미설정)를 그대로 따른다."""
    args = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            "-o", "StrictHostKeyChecking=accept-new"]
    if legacy:
        args.append("-O")
    if port:
        args += ["-P", str(port)]
    if key_path:
        args += ["-i", key_path]
    if upload:
        args += [local_path, remote_spec]
    else:
        args += [remote_spec, local_path]
    try:
        result = subprocess.run(
            args, capture_output=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return False, f"{timeout}초 안에 응답이 없습니다."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    if result.returncode == 0:
        return True, None
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    return False, stderr or f"종료 코드 {result.returncode}"


def _scp_with_fallback(local_path, remote_spec, port, key_path, timeout, upload):
    ok, err = _run_scp(local_path, remote_spec, port, key_path, timeout, upload, legacy=False)
    if not ok and err and "subsystem" in err.lower():
        ok, err = _run_scp(local_path, remote_spec, port, key_path, timeout, upload, legacy=True)
    return ok, err


def download_file(host, port, user, key_path, remote_path, local_path, timeout=120):
    """remote_path 파일을 local_path 로 그대로 받아온다(바이너리, 인코딩 변환 없음 -
    conf 파일용 read_text()와 달리 백업 .sql.gz 같은 바이너리 파일에 쓴다).
    성공하면 (True, None), 실패하면 (False, 이유)."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(scp.exe)가 없습니다."
    remote_spec = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"
    return _scp_with_fallback(local_path, remote_spec, port, key_path, timeout, upload=False)


def upload_file(host, port, user, key_path, local_path, remote_path, timeout=120):
    """local_path 파일을 remote_path 로 그대로 올린다(바이너리, 인코딩 변환 없음).
    성공하면 (True, None), 실패하면 (False, 이유)."""
    if not host:
        return False, "호스트 주소가 비어 있습니다."
    if not ssh_client_available():
        return False, "이 컴퓨터에 SSH 클라이언트(scp.exe)가 없습니다."
    if not os.path.isfile(local_path):
        return False, f"로컬 파일이 없습니다: {local_path}"
    remote_spec = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"
    return _scp_with_fallback(local_path, remote_spec, port, key_path, timeout, upload=True)
