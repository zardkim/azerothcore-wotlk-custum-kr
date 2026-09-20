# -*- coding: utf-8 -*-
"""원격(SSH) 서버의 deploy/scripts/backup.sh·restore.sh 를 대신 실행하는 아주 작은
래퍼. remote_conf.py 의 run_command() 위에 "백업 목록 조회/생성/복원" 세 가지
동작만 얹는다 - SSH 접속 자체(ssh.exe 존재 확인, 에러 메시지 관례 등)는
remote_conf.py 를 그대로 재사용한다."""
import json

import remote_conf

_LIST_TIMEOUT = 20
_BACKUP_TIMEOUT = 300
_RESTORE_TIMEOUT = 300


def list_backups(host, port, user, key_path, deploy_dir):
    """deploy_dir/backups/*/manifest.json 을 전부 읽어서 최신순으로 돌려준다.
    성공하면 (백업 목록, None) - 목록의 각 항목은 manifest.json 내용에 "backup_id"
    를 채워 넣은 dict. 실패(연결 안 됨/backups 폴더 없음 등)하면 (None, 이유)."""
    if not deploy_dir:
        return None, "원격 배포 폴더 경로가 비어 있습니다 (설정 > 원격 접속 정보)."
    cmd = (
        f"cd {remote_conf.shell_quote(deploy_dir)} && "
        "for d in backups/*/; do "
        '[ -f "$d/manifest.json" ] || continue; '
        'printf "%s\\t" "$(basename "$d")"; '
        'tr -d "\\n" < "$d/manifest.json"; '
        'printf "\\n"; '
        "done"
    )
    ok, output = remote_conf.run_command(host, port, user, key_path, cmd, timeout=_LIST_TIMEOUT)
    if not ok:
        return None, output or "백업 목록을 가져오지 못했습니다."
    backups = []
    for line in output.splitlines():
        if not line.strip() or "\t" not in line:
            continue
        backup_id, _, manifest_raw = line.partition("\t")
        try:
            manifest = json.loads(manifest_raw)
        except ValueError:
            continue
        manifest["backup_id"] = backup_id
        backups.append(manifest)
    backups.sort(key=lambda m: m.get("backup_id", ""), reverse=True)
    return backups, None


def run_backup(host, port, user, key_path, deploy_dir):
    """deploy_dir/scripts/backup.sh 를 실행한다. 확인 프롬프트가 없는 스크립트라
    바로 실행해도 안전 - (성공여부, 스크립트 출력 또는 실패 이유)."""
    if not deploy_dir:
        return False, "원격 배포 폴더 경로가 비어 있습니다 (설정 > 원격 접속 정보)."
    cmd = f"cd {remote_conf.shell_quote(deploy_dir)} && ./scripts/backup.sh"
    return remote_conf.run_command(host, port, user, key_path, cmd, timeout=_BACKUP_TIMEOUT)


def run_restore(host, port, user, key_path, deploy_dir, backup_id):
    """deploy_dir/scripts/restore.sh <backup_id> 를 실행한다. 런처 쪽에서 이미
    강한 확인을 받은 뒤에만 호출한다는 전제로 --force --yes 를 붙여서 대화형
    프롬프트 없이 바로 진행한다 - (성공여부, 스크립트 출력 또는 실패 이유)."""
    if not deploy_dir:
        return False, "원격 배포 폴더 경로가 비어 있습니다 (설정 > 원격 접속 정보)."
    if not backup_id:
        return False, "복원할 백업을 선택하세요."
    cmd = (
        f"cd {remote_conf.shell_quote(deploy_dir)} && "
        f"./scripts/restore.sh {remote_conf.shell_quote(backup_id)} --force --yes"
    )
    return remote_conf.run_command(host, port, user, key_path, cmd, timeout=_RESTORE_TIMEOUT)
