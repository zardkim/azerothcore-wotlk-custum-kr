# -*- coding: utf-8 -*-
"""SSH나 서버 쪽 스크립트를 거치지 않고, 이 컴퓨터에서 MySQL(pymysql)로 직접
접속해서 봇 계정(기본 접두어 rndbot)을 제외한 실제 플레이어 계정/캐릭터만
백업/복원한다 - HeidiSQL 등으로 이미 host:port 접속이 되는 것과 같은 방식이다.
백업 파일은 이 컴퓨터(호출부가 넘겨주는 local_dir)에만 저장된다.

deploy/scripts/lib/player-tables.sh, web/wow-web/src/lib/backup-storage.ts 와
정확히 같은 테이블 목록·WHERE 조건을 쓴다 - 셋 중 하나만 고치면 백업 범위가
서로 달라지니 항상 같이 수정할 것."""
import datetime
import gzip
import json
import os

import pymysql
from pymysql.converters import escape_item

DEFAULT_BOT_PREFIX = "rndbot"
CHARSET = "utf8mb4"

# deploy/scripts/lib/player-tables.sh 와 반드시 같은 목록.
PLAYER_CHAR_TABLES = [
    ("account_data", "accountId IN ({ACCOUNT_SQL})"),
    ("account_instance_times", "accountId IN ({ACCOUNT_SQL})"),
    ("account_tutorial", "accountId IN ({ACCOUNT_SQL})"),
    ("characters", "account IN ({ACCOUNT_SQL})"),
    ("character_account_data", "guid IN ({GUID_SQL})"),
    ("character_achievement", "guid IN ({GUID_SQL})"),
    ("character_achievement_progress", "guid IN ({GUID_SQL})"),
    ("character_action", "guid IN ({GUID_SQL})"),
    ("character_arena_stats", "guid IN ({GUID_SQL})"),
    ("character_aura", "guid IN ({GUID_SQL})"),
    ("character_banned", "guid IN ({GUID_SQL})"),
    ("character_declinedname", "guid IN ({GUID_SQL})"),
    ("character_equipmentsets", "guid IN ({GUID_SQL})"),
    ("character_gifts", "guid IN ({GUID_SQL})"),
    ("character_glyphs", "guid IN ({GUID_SQL})"),
    ("character_homebind", "guid IN ({GUID_SQL})"),
    ("character_instance", "guid IN ({GUID_SQL})"),
    ("character_inventory", "guid IN ({GUID_SQL})"),
    ("character_queststatus", "guid IN ({GUID_SQL})"),
    ("character_queststatus_daily", "guid IN ({GUID_SQL})"),
    ("character_queststatus_monthly", "guid IN ({GUID_SQL})"),
    ("character_queststatus_rewarded", "guid IN ({GUID_SQL})"),
    ("character_queststatus_seasonal", "guid IN ({GUID_SQL})"),
    ("character_queststatus_weekly", "guid IN ({GUID_SQL})"),
    ("character_reputation", "guid IN ({GUID_SQL})"),
    ("character_skills", "guid IN ({GUID_SQL})"),
    ("character_spell", "guid IN ({GUID_SQL})"),
    ("character_spell_cooldown", "guid IN ({GUID_SQL})"),
    ("character_stats", "guid IN ({GUID_SQL})"),
    ("character_talent", "guid IN ({GUID_SQL})"),
    ("character_social", "guid IN ({GUID_SQL}) AND friend IN ({GUID_SQL})"),
    ("character_pet", "owner IN ({GUID_SQL})"),
    ("character_pet_declinedname", "id IN ({PET_SQL})"),
    ("pet_aura", "guid IN ({PET_SQL})"),
    ("pet_spell", "guid IN ({PET_SQL})"),
    ("pet_spell_cooldown", "guid IN ({PET_SQL})"),
    ("item_instance", "owner_guid IN ({GUID_SQL})"),
    ("item_refund_instance", "player_guid IN ({GUID_SQL})"),
    ("item_soulbound_trade_data", "itemGuid IN (SELECT guid FROM item_instance WHERE owner_guid IN ({GUID_SQL}))"),
    ("mail", "receiver IN ({GUID_SQL}) OR sender IN ({GUID_SQL})"),
    ("mail_items", "receiver IN ({GUID_SQL})"),
    ("auctionhouse", "itemowner IN ({GUID_SQL}) OR buyguid IN ({GUID_SQL})"),
    ("guild", "guildid IN ({GUILD_SQL})"),
    ("guild_member", "guid IN ({GUID_SQL})"),
    ("guild_rank", "guildid IN ({GUILD_SQL})"),
    ("guild_bank_tab", "guildid IN ({GUILD_SQL})"),
    ("guild_bank_right", "guildid IN ({GUILD_SQL})"),
    ("guild_bank_item", "guildid IN ({GUILD_SQL})"),
    ("guild_bank_eventlog", "guildid IN ({GUILD_SQL})"),
    ("guild_eventlog", "guildid IN ({GUILD_SQL})"),
    ("guild_member_withdraw", "guid IN ({GUID_SQL})"),
    ("arena_team", "arenaTeamId IN ({ARENA_SQL})"),
    ("arena_team_member", "guid IN ({GUID_SQL})"),
    ("groups", "guid IN ({GROUP_SQL})"),
    ("group_member", "memberGuid IN ({GUID_SQL})"),
    ("instance", "id IN (SELECT instance FROM character_instance WHERE guid IN ({GUID_SQL}))"),
    ("petition", "ownerguid IN ({GUID_SQL})"),
    ("petition_sign", "ownerguid IN ({GUID_SQL}) OR playerguid IN ({GUID_SQL})"),
    ("calendar_events", "creator IN ({GUID_SQL})"),
    ("calendar_invites", "invitee IN ({GUID_SQL}) OR sender IN ({GUID_SQL})"),
    ("lfg_data", "guid IN ({GUID_SQL})"),
    ("pvpstats_players", "character_guid IN ({GUID_SQL})"),
    ("pvpstats_battlegrounds", "id IN (SELECT battleground_id FROM pvpstats_players WHERE character_guid IN ({GUID_SQL}))"),
    ("gm_ticket", "playerGuid IN ({GUID_SQL})"),
    ("corpse", "guid IN ({GUID_SQL})"),
    ("lag_reports", "guid IN ({GUID_SQL})"),
]


def resolve_player_where(where_tpl, auth_db, bot_prefix):
    account_sql = f"SELECT id FROM {auth_db}.account WHERE username NOT LIKE '{bot_prefix}%'"
    guid_sql = f"SELECT guid FROM characters WHERE account IN ({account_sql})"
    guild_sql = f"SELECT guildid FROM guild_member WHERE guid IN ({guid_sql})"
    arena_sql = f"SELECT arenaTeamId FROM arena_team_member WHERE guid IN ({guid_sql})"
    group_sql = f"SELECT guid FROM group_member WHERE memberGuid IN ({guid_sql})"
    pet_sql = f"SELECT id FROM character_pet WHERE owner IN ({guid_sql})"
    return (
        where_tpl.replace("{ACCOUNT_SQL}", account_sql)
        .replace("{GUID_SQL}", guid_sql)
        .replace("{GUILD_SQL}", guild_sql)
        .replace("{ARENA_SQL}", arena_sql)
        .replace("{GROUP_SQL}", group_sql)
        .replace("{PET_SQL}", pet_sql)
    )


def _connect(host, port, user, password, database, timeout=10):
    return pymysql.connect(
        host=host, port=int(port), user=user, password=password,
        database=database, charset=CHARSET, connect_timeout=timeout,
    )


def test_connection(host, port, user, password, timeout=8):
    """(True, "연결 성공") 또는 (False, 이유)."""
    try:
        conn = pymysql.connect(host=host, port=int(port), user=user, password=password,
                                charset=CHARSET, connect_timeout=timeout)
        conn.close()
        return True, "연결 성공"
    except Exception as e:
        return False, str(e)


def _table_exists(conn, db_name, table):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s LIMIT 1",
            (db_name, table),
        )
        return cur.fetchone() is not None


def _dump_table_sql(conn, table, where):
    """(insert문 목록, 행 수)."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM `{table}` WHERE {where}")
        columns = [d[0] for d in cur.description]
        col_sql = ", ".join(f"`{c}`" for c in columns)
        rows = cur.fetchall()
    lines = []
    for row in rows:
        vals = ", ".join(escape_item(v, CHARSET) for v in row)
        lines.append(f"INSERT INTO `{table}` ({col_sql}) VALUES ({vals});")
    return lines, len(rows)


def _new_backup_id():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_backup(host, port, user, password, auth_db, char_db, local_dir, bot_prefix=DEFAULT_BOT_PREFIX):
    """봇 계정을 제외한 실제 플레이어 계정/캐릭터를 이 컴퓨터(local_dir)로 백업한다.
    성공하면 (backup_id, None), 실패하면 (None, 에러메시지)."""
    try:
        auth_conn = _connect(host, port, user, password, auth_db)
    except Exception as e:
        return None, f"DB 접속 실패({auth_db}): {e}"
    try:
        char_conn = _connect(host, port, user, password, char_db)
    except Exception as e:
        auth_conn.close()
        return None, f"DB 접속 실패({char_db}): {e}"

    try:
        account_where = f"username NOT LIKE '{bot_prefix}%'"
        account_id_where = resolve_player_where("{ACCOUNT_SQL}", auth_db, bot_prefix)

        auth_lines = ["SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS=0;"]
        acc_lines, account_count = _dump_table_sql(auth_conn, "account", account_where)
        auth_lines += acc_lines
        for t in ("account_access", "account_banned"):
            if _table_exists(auth_conn, auth_db, t):
                lines, _n = _dump_table_sql(auth_conn, t, f"id IN ({account_id_where})")
                auth_lines += lines
        if _table_exists(auth_conn, auth_db, "account_muted"):
            lines, _n = _dump_table_sql(auth_conn, "account_muted", f"guid IN ({account_id_where})")
            auth_lines += lines
        auth_lines.append("SET FOREIGN_KEY_CHECKS=1;")

        char_lines = ["SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS=0;"]
        character_count = 0
        for table, where_tpl in PLAYER_CHAR_TABLES:
            if not _table_exists(char_conn, char_db, table):
                continue
            where = resolve_player_where(where_tpl, auth_db, bot_prefix)
            lines, n = _dump_table_sql(char_conn, table, where)
            char_lines += lines
            if table == "characters":
                character_count = n
        char_lines.append("SET FOREIGN_KEY_CHECKS=1;")

        backup_id = _new_backup_id()
        backup_dir = os.path.join(local_dir, backup_id)
        os.makedirs(backup_dir, exist_ok=True)
        with gzip.open(os.path.join(backup_dir, "acore_auth.sql.gz"), "wt", encoding="utf-8") as f:
            f.write("\n".join(auth_lines) + "\n")
        with gzip.open(os.path.join(backup_dir, "acore_characters.sql.gz"), "wt", encoding="utf-8") as f:
            f.write("\n".join(char_lines) + "\n")

        manifest = {
            "backup_id": backup_id,
            "created_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "account_count": account_count,
            "character_count": character_count,
            "bot_prefix_excluded": bot_prefix,
            "excluded_databases": ["acore_playerbots", "acore_world"],
            "scope": "account/character 단위 선별 백업 (전체 DB 덤프 아님)",
            "source": "launcher",
            "files": {"acore_auth": "acore_auth.sql.gz", "acore_characters": "acore_characters.sql.gz"},
        }
        with open(os.path.join(backup_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return backup_id, None
    except Exception as e:
        return None, f"백업 실패: {e}"
    finally:
        auth_conn.close()
        char_conn.close()


def list_local_backups(local_dir):
    """local_dir 아래 저장된 백업들의 manifest.json 을 읽어 최신순으로 돌려준다."""
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


def _count_real_accounts(conn, bot_prefix):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM account WHERE username NOT LIKE %s", (f"{bot_prefix}%",))
        return cur.fetchone()[0]


def _execute_sql_file(conn, gz_path):
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        with conn.cursor() as cur:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                cur.execute(line)
    conn.commit()


def run_restore(host, port, user, password, auth_db, char_db, local_dir, backup_id,
                 bot_prefix=DEFAULT_BOT_PREFIX, force=False):
    """local_dir/<backup_id>/ 의 백업을 DB에 직접 복원한다. 대상 DB에 이미 실제
    계정(봇 제외)이 있으면 force=True 가 아닌 한 거부한다 - 병합이 아니라 교체.
    성공하면 (True, 결과메시지), 실패하면 (False, 이유)."""
    backup_dir = os.path.join(local_dir, backup_id)
    auth_path = os.path.join(backup_dir, "acore_auth.sql.gz")
    char_path = os.path.join(backup_dir, "acore_characters.sql.gz")
    if not os.path.isfile(auth_path) or not os.path.isfile(char_path):
        return False, f"백업 파일을 찾을 수 없습니다: {backup_dir}"

    try:
        auth_conn = _connect(host, port, user, password, auth_db)
    except Exception as e:
        return False, f"DB 접속 실패({auth_db}): {e}"
    try:
        char_conn = _connect(host, port, user, password, char_db)
    except Exception as e:
        auth_conn.close()
        return False, f"DB 접속 실패({char_db}): {e}"

    try:
        current = _count_real_accounts(auth_conn, bot_prefix)
        if current > 0 and not force:
            return False, (
                f"대상 DB에 이미 실제 계정이 {current}개 있습니다(봇 제외). "
                "이 복원은 병합이 아니라 교체입니다 - 강제 복원으로 다시 시도하세요."
            )

        account_id_where = resolve_player_where("{ACCOUNT_SQL}", auth_db, bot_prefix)

        with char_conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            for table, where_tpl in PLAYER_CHAR_TABLES:
                if not _table_exists(char_conn, char_db, table):
                    continue
                where = resolve_player_where(where_tpl, auth_db, bot_prefix)
                cur.execute(f"DELETE FROM `{table}` WHERE {where}")
        char_conn.commit()

        with auth_conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            cur.execute(f"DELETE FROM account_access WHERE id IN ({account_id_where})")
            cur.execute(f"DELETE FROM account_banned WHERE id IN ({account_id_where})")
            if _table_exists(auth_conn, auth_db, "account_muted"):
                cur.execute(f"DELETE FROM account_muted WHERE guid IN ({account_id_where})")
            cur.execute("DELETE FROM account WHERE username NOT LIKE %s", (f"{bot_prefix}%",))
        auth_conn.commit()

        _execute_sql_file(auth_conn, auth_path)
        _execute_sql_file(char_conn, char_path)

        new_accounts = _count_real_accounts(auth_conn, bot_prefix)
        return True, f"복원 완료: 실제 계정 {new_accounts}개 (봇 계정은 변경 없음)"
    except Exception as e:
        return False, f"복원 실패: {e}"
    finally:
        auth_conn.close()
        char_conn.close()
