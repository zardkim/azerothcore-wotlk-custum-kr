# -*- coding: utf-8 -*-
"""사용자 설정(경로 등) 저장/로드. launcher\\config\\config.json 에 저장됨.

exe 옆에 파일을 그냥 흩어두지 않고 config\\ 하위 폴더에 모아둬서, 이 launcher 폴더
(exe + _internal + assets + config) 하나만 통째로 복사해도 설정까지 포함해서 독립적으로
그대로 옮겨 쓸 수 있게 했다. 예전 버전(v0.1.17 이전)은 exe 바로 옆에 config.json /
presets.json 을 뒀는데, 처음 실행할 때 그 자리에 파일이 있으면 자동으로 config\\ 로
옮겨서(_migrate_legacy_file) 기존 사용자 설정이 사라지지 않게 한다."""
import json
import os
import shutil
import uuid

from paths import BASE_DIR

LAUNCHER_DIR = BASE_DIR
CONFIG_DIR = os.path.join(LAUNCHER_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
PRESETS_PATH = os.path.join(CONFIG_DIR, "presets.json")

_LEGACY_CONFIG_PATH = os.path.join(LAUNCHER_DIR, "config.json")
_LEGACY_PRESETS_PATH = os.path.join(LAUNCHER_DIR, "presets.json")


def _migrate_legacy_file(legacy_path, new_path):
    """new_path 에 아직 파일이 없고 legacy_path(구버전 위치)에 파일이 있으면 한 번만
    옮긴다. 실패해도(권한 등) 조용히 넘어가고, 이 경우 legacy 위치의 파일은 그대로
    남아있으니 다음 실행 때 다시 시도된다."""
    if os.path.isfile(new_path) or not os.path.isfile(legacy_path):
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.move(legacy_path, new_path)
    except OSError:
        pass

def _looks_like_repack_root(path):
    return os.path.isfile(os.path.join(path, "authserver.exe"))


def detect_root_dir(start_dir):
    """authserver.exe 가 있는 폴더를 자동으로 찾는다.

    스크립트로 실행할 땐 launcher 폴더의 '부모'가 repack 루트였지만, exe 로 빌드하면
    실행파일이 launcher\\dist\\ 안에 있어서 한 단계 더 위로 올라가야 한다 — 그 가정이
    깨지면 인증서버/월드서버 기본 경로가 전부 엉뚱한 곳을 가리켜서 시작 버튼을 눌러도
    아무 반응이 없는 것처럼 보인다. 그래서 실행 위치부터 몇 단계 위까지 실제로
    authserver.exe 가 있는지 확인해서 찾는다."""
    candidate = os.path.abspath(start_dir)
    for _ in range(4):
        if _looks_like_repack_root(candidate):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    # 못 찾았으면 예전 방식대로(launcher 폴더의 부모)라도 추측해둔다
    return os.path.dirname(start_dir)


DEFAULT_ROOT = detect_root_dir(LAUNCHER_DIR)


def defaults_for_root(root_dir: str) -> dict:
    """주어진 루트 폴더 기준으로 각 실행파일/설정파일의 기본 경로를 계산."""
    j = lambda *parts: os.path.join(root_dir, *parts)
    return {
        "root_dir": root_dir,
        "mysqld_exe": j("mysql", "bin", "mysqld.exe"),
        "mysql_ini": j("mysql", "my.ini"),
        "mysqladmin_exe": j("mysql", "bin", "mysqladmin.exe"),
        "authserver_exe": j("authserver.exe"),
        "worldserver_exe": j("worldserver.exe"),
        "wow_client_exe": "",
    }


DEFAULT_CONFIG = {
    **defaults_for_root(DEFAULT_ROOT),
    "mysql_host": "127.0.0.1",
    "mysql_port": 3306,
    "auth_port": 3724,
    "world_port": 8085,
    "window_pos": None,
    "db_user": "wowlegends",
    "db_password": "",
    "realmlist_list": ["127.0.0.1"],
    "realmlist_active": "127.0.0.1",
    "opt_autostart": False,
    "opt_show_console": False,
    "opt_stop_on_exit": False,
    "gm_account": "",
    "gm_password": "",
    "soap_port": 7878,
    "online_list_limit": 100,
    "theme": "wotlk",
    "ui_font": "",
    "mode": "local",
    "remote_host": "",
    "remote_ssh_port": 22,
    "remote_ssh_user": "",
    "remote_ssh_key_path": "",
    "remote_worldserver_conf_path": "",
    "remote_authserver_conf_path": "",
    "remote_deploy_dir": "",
    "servers": [],
    "active_server_id": "",
}

# "서버" 하나에 속하는 필드들(로컬/원격 여부 + 접속 정보 + GM 계정 + 렐름리스트 +
# 클라이언트) - 런처 전체 설정(테마/폰트/자동시작 등)과 구분해서 서버별로 따로
# 저장한다. cfg 최상위에는 "지금 활성 서버"의 값이 그대로 복사돼 있으므로(아래
# flatten_active_server), 이 목록 밖의 코드는 전부 지금처럼 cfg.get(...) 만
# 쓰면 된다. wow_client_exe 는 원래 "서버가 바뀌어도 같은 클라이언트를 쓸 것"
# 이라는 전제로 전역 설정이었는데, 서버마다 클라이언트가 다를 수 있다는 요구가
# 생겨서 서버별 필드로 옮겼다(_migrate_client_exe_to_servers 참고 - 이미 쓰던
# 전역 값을 잃지 않도록 마이그레이션함).
SERVER_FIELDS = [
    "mode",
    "mysql_host", "mysql_port", "db_user", "db_password",
    "mysqld_exe", "authserver_exe", "worldserver_exe", "auth_port", "world_port",
    "remote_host", "remote_ssh_port", "remote_ssh_user", "remote_ssh_key_path",
    "remote_worldserver_conf_path", "remote_authserver_conf_path", "remote_deploy_dir",
    "gm_account", "gm_password", "soap_port",
    "realmlist_list", "realmlist_active",
    "wow_client_exe",
]

MY_PROFILE_NAME = "내 설정"


def _migrate_realmlist(cfg, saved):
    """예전 버전은 렐름리스트 주소를 하나만(cfg["realmlist"] = "set realmlist X"
    줄 전체)저장했다. realmlist_list 가 저장된 파일에 아직 없으면(= 이 마이그레이션을
    한 번도 안 거침) 예전 값에서 주소만 뽑아 새 형식(목록 + 활성 주소)으로 한 번만
    옮긴다. saved(필터링 전 원본 JSON)에서 읽어야 한다 - DEFAULT_CONFIG 에서
    "realmlist" 키를 뺐기 때문에 필터링된 cfg 에는 이미 그 값이 안 남아있다."""
    if "realmlist_list" in saved:
        return
    old = str(saved.get("realmlist", "")).strip()
    prefix = "set realmlist"
    addr = old[len(prefix):].strip() if old.lower().startswith(prefix) else old
    if not addr:
        addr = "127.0.0.1"
    cfg["realmlist_list"] = [addr]
    cfg["realmlist_active"] = addr


def _new_server_id():
    return uuid.uuid4().hex[:8]


def _server_from_flat(source, name):
    """source(cfg 형태의 dict)에서 SERVER_FIELDS 값들만 뽑아 새 서버 항목을
    만든다. 없는 값은 DEFAULT_CONFIG 기본값으로 채운다."""
    entry = {"id": _new_server_id(), "name": name, "pack_name": ""}
    for key in SERVER_FIELDS:
        entry[key] = source.get(key, DEFAULT_CONFIG.get(key))
    entry["realmlist_list"] = list(entry.get("realmlist_list") or ["127.0.0.1"])
    return entry


def _migrate_to_servers(cfg, saved):
    """예전 버전(로컬/원격 "모드" 하나만 있던 시절)에서 업그레이드하는 경우,
    지금까지 쓰던 평평한 설정으로 서버 하나("서버1")를 만든다. 그 시절에 있던
    "프리셋"(presets.json)도 각각 서버 하나씩으로 변환해서 같이 옮긴다 - 사용자가
    이미 만들어둔 프리셋을 그대로 서버 목록으로 이어받게. 이미 servers 가 저장된
    적이 있으면(= 이 마이그레이션을 한 번이라도 거쳤으면) 아무것도 안 한다."""
    if saved.get("servers"):
        cfg["servers"] = saved["servers"]
        ids = {s.get("id") for s in cfg["servers"]}
        cfg["active_server_id"] = saved.get("active_server_id") or next(iter(ids), "")
        return

    first = _server_from_flat(cfg, "서버1")
    servers = [first]
    try:
        presets = load_presets()
    except Exception:
        presets = {}
    for pname, pvalues in presets.items():
        if pname == MY_PROFILE_NAME or not isinstance(pvalues, dict):
            continue  # "내 설정" 은 활성 서버(위의 first)와 값이 같으니 중복 추가 안 함
        servers.append(_server_from_flat(pvalues, pname))

    cfg["servers"] = servers
    cfg["active_server_id"] = first["id"]


def _migrate_client_exe_to_servers(cfg, saved):
    """wow_client_exe 는 원래 "서버를 바꿔도 같은 클라이언트를 쓸 것"이라는
    전제로 전역 설정이었는데(서버별 필드 목록인 SERVER_FIELDS 에 없었음),
    서버마다 다른 클라이언트를 쓸 수 있어야 한다는 요구로 서버별 필드가 됐다.
    이미 서버 항목에 이 값이 있으면(이 마이그레이션을 거쳤으면) 아무것도 안
    하고, 없으면 지금까지 쓰던 전역 값(saved 최상위, 필터링 전 원본)을 모든
    서버에 그대로 복사해서 기존 설정을 잃지 않게 한다 - 이후엔 서버마다 따로
    바꾸면 된다."""
    servers = cfg.get("servers") or []
    if not servers or all("wow_client_exe" in s for s in servers):
        return
    old_global = saved.get("wow_client_exe", "")
    for server in servers:
        if "wow_client_exe" not in server:
            server["wow_client_exe"] = old_global


def flatten_active_server(cfg):
    """cfg["servers"] 에서 active_server_id 와 일치하는 항목을 찾아 그 값들을
    cfg 최상위에 덮어쓴다 - 이후 코드는 지금까지처럼 cfg.get("gm_account") 같은
    식으로 그냥 읽으면 "활성 서버"의 값을 읽게 된다. 못 찾으면(삭제된 경우 등)
    목록의 첫 번째 서버로 대체."""
    servers = cfg.get("servers") or []
    if not servers:
        return
    active_id = cfg.get("active_server_id")
    server = next((s for s in servers if s.get("id") == active_id), None)
    if server is None:
        server = servers[0]
        cfg["active_server_id"] = server.get("id")
    for key in SERVER_FIELDS:
        # 예전에 만들어진 서버 항목엔 그 뒤에 SERVER_FIELDS 에 추가된 키(예:
        # auth_port/world_port)가 아예 없을 수 있다 - 그 경우 건너뛰면 cfg
        # 최상위에 남아있던 "다른 서버"의 값이 그대로 새 활성 서버의 값인 것
        # 처럼 잘못 쓰이게 된다(실제로 이래서 원격 서버에서 자동 보정한 포트가
        # 로컬 서버로 전환한 뒤에도 안 지워지고 남아있던 버그가 있었음).
        # DEFAULT_CONFIG 기본값으로 채워서 항상 명확한 값이 들어가게 한다.
        cfg[key] = server.get(key, DEFAULT_CONFIG.get(key))


def sync_active_server(cfg):
    """flatten_active_server() 의 반대 방향 - cfg 최상위의 서버별 필드 값들을
    다시 활성 서버 항목에 써넣는다. 설정 창에서 "저장"을 누른 뒤 호출해서,
    편집한 내용이 서버 목록에도 남아있게 한다."""
    servers = cfg.get("servers") or []
    active_id = cfg.get("active_server_id")
    server = next((s for s in servers if s.get("id") == active_id), None)
    if server is None:
        return
    for key in SERVER_FIELDS:
        if key in cfg:
            server[key] = cfg[key]


def new_server(name):
    """빈 서버 항목(로컬 모드, 기본값)을 하나 만든다 - "서버 관리" 창의 "추가"
    버튼에서 씀."""
    return _server_from_flat(DEFAULT_CONFIG, name)


def load_config() -> dict:
    _migrate_legacy_file(_LEGACY_CONFIG_PATH, CONFIG_PATH)
    cfg = dict(DEFAULT_CONFIG)
    cfg["servers"] = list(DEFAULT_CONFIG.get("servers") or [])
    saved = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update({k: v for k, v in saved.items() if k in cfg})
        except (OSError, json.JSONDecodeError):
            pass
    _migrate_realmlist(cfg, saved)
    _migrate_to_servers(cfg, saved)
    _migrate_client_exe_to_servers(cfg, saved)
    flatten_active_server(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_presets() -> dict:
    """이름 -> 설정값(dict) 으로 저장해둔 프리셋 목록. launcher\\config\\presets.json 에 저장됨."""
    _migrate_legacy_file(_LEGACY_PRESETS_PATH, PRESETS_PATH)
    if os.path.exists(PRESETS_PATH):
        try:
            with open(PRESETS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_presets(presets: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PRESETS_PATH, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
