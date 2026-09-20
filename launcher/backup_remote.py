# -*- coding: utf-8 -*-
"""원격(SSH) 서버의 deploy/scripts/backup.sh·restore.sh 를 대신 실행하는 아주 작은
래퍼. 백업 파일 자체는 "런처가 실행된 컴퓨터"에 저장하고(원격 서버에는 남기지
않음), 복원할 때는 그 로컬 파일을 원격 서버로 올려서 restore.sh 를 돌린다 -
런처가 여러 서버를 오가며 관리하는 도구이므로, 서버 쪽에 백업이 흩어져 쌓이는
대신 운영자 PC 한 곳에 모아두는 편이 관리하기 쉽다."""
import json
import os
import re

import remote_conf

_BACKUP_TIMEOUT = 300
_RESTORE_TIMEOUT = 300
_TRANSFER_TIMEOUT = 300
_BACKUP_FILES = ("acore_auth.sql.gz", "acore_characters.sql.gz", "manifest.json")

# backup.sh 마지막 출력 줄: ">> 저장 위치: <deploy_dir>/backups/<backup_id>"
_BACKUP_ID_RE = re.compile(r"20\d{6}-\d{6}")


def run_backup_and_download(host, port, user, key_path, deploy_dir, local_dir):
    """원격에서 backup.sh 를 실행하고, 결과 파일을 local_dir/<backup_id>/ 로 내려받는다.
    성공하면 (backup_id, 백업 스크립트 출력), 실패하면 (None, 실패 이유)."""
    if not deploy_dir:
        return None, "원격 배포 폴더 경로가 비어 있습니다 (설정 > 원격 접속 정보)."
    cmd = f"cd {remote_conf.shell_quote(deploy_dir)} && ./scripts/backup.sh"
    ok, output = remote_conf.run_command(host, port, user, key_path, cmd, timeout=_BACKUP_TIMEOUT)
    if not ok:
        return None, output or "백업에 실패했습니다."

    m = _BACKUP_ID_RE.search(output)
    if not m:
        return None, "백업은 끝난 것 같지만 백업 ID를 출력에서 찾지 못했습니다:\n" + output
    backup_id = m.group(0)

    remote_backup_dir = f"{deploy_dir}/backups/{backup_id}"
    local_backup_dir = os.path.join(local_dir, backup_id)
    os.makedirs(local_backup_dir, exist_ok=True)

    for fname in _BACKUP_FILES:
        ok2, err2 = remote_conf.download_file(
            host, port, user, key_path,
            f"{remote_backup_dir}/{fname}", os.path.join(local_backup_dir, fname),
            timeout=_TRANSFER_TIMEOUT,
        )
        if not ok2:
            return None, f"백업은 서버에 만들어졌지만({backup_id}) 내려받기 실패 - {fname}: {err2}"

    return backup_id, output


def list_local_backups(local_dir):
    """local_dir 아래 저장된 백업들의 manifest.json 을 읽어 최신순으로 돌려준다.
    성공하면 (백업 목록, None) - 각 항목은 manifest.json 내용에 backup_id 를 채운
    dict. local_dir 이 아직 없으면 빈 목록을 돌려준다(에러 아님 - 첫 실행 시 정상)."""
    if not os.path.isdir(local_dir):
        return [], None
    backups = []
    for name in os.listdir(local_dir):
        manifest_path = os.path.join(local_dir, name, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError):
            continue
        manifest["backup_id"] = name
        backups.append(manifest)
    backups.sort(key=lambda m: m.get("backup_id", ""), reverse=True)
    return backups, None


def run_restore_from_local(host, port, user, key_path, deploy_dir, local_dir, backup_id):
    """local_dir/<backup_id>/ 의 백업 파일을 원격 서버로 올린 뒤 restore.sh 를
    실행한다. 런처 쪽에서 이미 강한 확인을 받은 뒤에만 호출한다는 전제로
    --force --yes 를 붙여서 대화형 프롬프트 없이 바로 진행한다.
    (성공여부, 스크립트 출력 또는 실패 이유)."""
    if not deploy_dir:
        return False, "원격 배포 폴더 경로가 비어 있습니다 (설정 > 원격 접속 정보)."
    if not backup_id:
        return False, "복원할 백업을 선택하세요."

    local_backup_dir = os.path.join(local_dir, backup_id)
    for fname in _BACKUP_FILES:
        if not os.path.isfile(os.path.join(local_backup_dir, fname)):
            return False, f"로컬 백업 파일이 없습니다: {os.path.join(local_backup_dir, fname)}"

    remote_backup_dir = f"{deploy_dir}/backups/{backup_id}"
    mkdir_cmd = f"mkdir -p {remote_conf.shell_quote(remote_backup_dir)}"
    ok, err = remote_conf.run_command(host, port, user, key_path, mkdir_cmd, timeout=30)
    if not ok:
        return False, f"원격에 백업 폴더를 만들지 못했습니다: {err}"

    for fname in _BACKUP_FILES:
        ok2, err2 = remote_conf.upload_file(
            host, port, user, key_path,
            os.path.join(local_backup_dir, fname), f"{remote_backup_dir}/{fname}",
            timeout=_TRANSFER_TIMEOUT,
        )
        if not ok2:
            return False, f"{fname} 업로드 실패: {err2}"

    cmd = (
        f"cd {remote_conf.shell_quote(deploy_dir)} && "
        f"./scripts/restore.sh {remote_conf.shell_quote(backup_id)} --force --yes"
    )
    return remote_conf.run_command(host, port, user, key_path, cmd, timeout=_RESTORE_TIMEOUT)
