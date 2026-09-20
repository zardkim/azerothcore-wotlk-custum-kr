# player-tables.sh — backup.sh(덤프)와 restore.sh(복원 전 삭제)가 공유하는
# "실제 플레이어 계정에 딸린 acore_characters 테이블" 목록. 한 곳에서만 관리해야
# 두 스크립트가 서로 다른 시점에 다른 테이블 집합을 건드리는 사고를 막을 수 있다.
#
# 각 원소는 "테이블명|WHERE절" 형식이고, WHERE절 안의 {ACCOUNT_SQL}/{GUID_SQL}/
# {GUILD_SQL}/{ARENA_SQL}/{GROUP_SQL}/{PET_SQL} 는 backup.sh/restore.sh가 실제
# SQL 서브쿼리 문자열로 치환한다(플레이스홀더 - 여기엔 진짜 $변수를 안 써서
# 호스트 bash/heredoc 이스케이프 문제를 원천적으로 피한다).
#
# 원본: Windows 리팩용 계정 이관 도구(acore_migration V12)의 Get-ExportTableList를
# 그대로 옮겼다 (AzerothCore 공식 스키마 기준). group_instance, guild_finder_*
# 두 테이블은 이 프로젝트의 현재 스키마에 없어서 뺐다 — 그래도 모든 테이블은
# dump/delete 양쪽에서 실행 직전에 존재 여부를 확인하므로, 코어 업데이트로 스키마가
# 바뀌어도(테이블 생기거나 없어져도) 안전하다.
PLAYER_CHAR_TABLES=(
  "account_data|accountId IN ({ACCOUNT_SQL})"
  "account_instance_times|accountId IN ({ACCOUNT_SQL})"
  "account_tutorial|accountId IN ({ACCOUNT_SQL})"
  "characters|account IN ({ACCOUNT_SQL})"
  "character_account_data|guid IN ({GUID_SQL})"
  "character_achievement|guid IN ({GUID_SQL})"
  "character_achievement_progress|guid IN ({GUID_SQL})"
  "character_action|guid IN ({GUID_SQL})"
  "character_arena_stats|guid IN ({GUID_SQL})"
  "character_aura|guid IN ({GUID_SQL})"
  "character_banned|guid IN ({GUID_SQL})"
  "character_declinedname|guid IN ({GUID_SQL})"
  "character_equipmentsets|guid IN ({GUID_SQL})"
  "character_gifts|guid IN ({GUID_SQL})"
  "character_glyphs|guid IN ({GUID_SQL})"
  "character_homebind|guid IN ({GUID_SQL})"
  "character_instance|guid IN ({GUID_SQL})"
  "character_inventory|guid IN ({GUID_SQL})"
  "character_queststatus|guid IN ({GUID_SQL})"
  "character_queststatus_daily|guid IN ({GUID_SQL})"
  "character_queststatus_monthly|guid IN ({GUID_SQL})"
  "character_queststatus_rewarded|guid IN ({GUID_SQL})"
  "character_queststatus_seasonal|guid IN ({GUID_SQL})"
  "character_queststatus_weekly|guid IN ({GUID_SQL})"
  "character_reputation|guid IN ({GUID_SQL})"
  "character_skills|guid IN ({GUID_SQL})"
  "character_spell|guid IN ({GUID_SQL})"
  "character_spell_cooldown|guid IN ({GUID_SQL})"
  "character_stats|guid IN ({GUID_SQL})"
  "character_talent|guid IN ({GUID_SQL})"
  "character_social|guid IN ({GUID_SQL}) AND friend IN ({GUID_SQL})"
  "character_pet|owner IN ({GUID_SQL})"
  "character_pet_declinedname|id IN ({PET_SQL})"
  "pet_aura|guid IN ({PET_SQL})"
  "pet_spell|guid IN ({PET_SQL})"
  "pet_spell_cooldown|guid IN ({PET_SQL})"
  "item_instance|owner_guid IN ({GUID_SQL})"
  "item_refund_instance|player_guid IN ({GUID_SQL})"
  "item_soulbound_trade_data|itemGuid IN (SELECT guid FROM item_instance WHERE owner_guid IN ({GUID_SQL}))"
  "mail|receiver IN ({GUID_SQL}) OR sender IN ({GUID_SQL})"
  "mail_items|receiver IN ({GUID_SQL})"
  "auctionhouse|itemowner IN ({GUID_SQL}) OR buyguid IN ({GUID_SQL})"
  "guild|guildid IN ({GUILD_SQL})"
  "guild_member|guid IN ({GUID_SQL})"
  "guild_rank|guildid IN ({GUILD_SQL})"
  "guild_bank_tab|guildid IN ({GUILD_SQL})"
  "guild_bank_right|guildid IN ({GUILD_SQL})"
  "guild_bank_item|guildid IN ({GUILD_SQL})"
  "guild_bank_eventlog|guildid IN ({GUILD_SQL})"
  "guild_eventlog|guildid IN ({GUILD_SQL})"
  "guild_member_withdraw|guid IN ({GUID_SQL})"
  "arena_team|arenaTeamId IN ({ARENA_SQL})"
  "arena_team_member|guid IN ({GUID_SQL})"
  "groups|guid IN ({GROUP_SQL})"
  "group_member|memberGuid IN ({GUID_SQL})"
  "instance|id IN (SELECT instance FROM character_instance WHERE guid IN ({GUID_SQL}))"
  "petition|ownerguid IN ({GUID_SQL})"
  "petition_sign|ownerguid IN ({GUID_SQL}) OR playerguid IN ({GUID_SQL})"
  "calendar_events|creator IN ({GUID_SQL})"
  "calendar_invites|invitee IN ({GUID_SQL}) OR sender IN ({GUID_SQL})"
  "lfg_data|guid IN ({GUID_SQL})"
  "pvpstats_players|character_guid IN ({GUID_SQL})"
  "pvpstats_battlegrounds|id IN (SELECT battleground_id FROM pvpstats_players WHERE character_guid IN ({GUID_SQL}))"
  "gm_ticket|playerGuid IN ({GUID_SQL})"
  "corpse|guid IN ({GUID_SQL})"
  # 참조 도구는 lag_reports.accountId를 가정했지만, 이 스키마 버전은 accountId
  # 컬럼이 없고 guid(캐릭터 guid)만 있다 (docker exec ... DESCRIBE로 실측 확인함).
  "lag_reports|guid IN ({GUID_SQL})"
)

# 플레이스홀더 -> 실제 SQL 서브쿼리 치환. $1=BOT_PREFIX 를 넘겨 받는다.
# 호출부(backup.sh/restore.sh)에서 이 함수로 각 줄의 WHERE절을 완성한 뒤 그대로
# 원격 스크립트 문자열에 이어붙인다.
resolve_player_where() {
  local where="$1" bot_prefix="$2"
  local account_sql="SELECT id FROM acore_auth.account WHERE username NOT LIKE '${bot_prefix}%'"
  local guid_sql="SELECT guid FROM characters WHERE account IN ($account_sql)"
  local guild_sql="SELECT guildid FROM guild_member WHERE guid IN ($guid_sql)"
  local arena_sql="SELECT arenaTeamId FROM arena_team_member WHERE guid IN ($guid_sql)"
  local group_sql="SELECT guid FROM group_member WHERE memberGuid IN ($guid_sql)"
  local pet_sql="SELECT id FROM character_pet WHERE owner IN ($guid_sql)"
  where="${where//\{ACCOUNT_SQL\}/$account_sql}"
  where="${where//\{GUID_SQL\}/$guid_sql}"
  where="${where//\{GUILD_SQL\}/$guild_sql}"
  where="${where//\{ARENA_SQL\}/$arena_sql}"
  where="${where//\{GROUP_SQL\}/$group_sql}"
  where="${where//\{PET_SQL\}/$pet_sql}"
  printf '%s' "$where"
}
