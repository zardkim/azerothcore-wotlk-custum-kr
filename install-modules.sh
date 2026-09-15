#!/usr/bin/env bash
#
# install-modules.sh
# AzerothCore Playerbot Docker 통합 구축 - 65개 모듈 자동 설치 스크립트
# 참조 문서: azerothcore_playerbot_docker_조사_계획서.md, 01~07 조사 문서, modules.lock
#
# 역할 (계획서 12장):
#   1 modules 디렉터리 생성          2 GitHub 저장소 clone (branch)
#   3 지정 branch checkout           4 필요한 commit checkout (modules.lock 고정)
#   5 의존성 검사(Tier 순서)         6 SQL 파일 수집
#   7 SQL custom 디렉터리 배치       8 설정 파일 수집
#   9 Docker 설정 안내               10 설치 결과 검증(요약/체크리스트 출력)
#
set -euo pipefail

# ── 경로 설정 ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${AC_BASE_DIR:-$SCRIPT_DIR}"
LOCK_FILE="$BASE_DIR/modules.lock"
MODULES_DIR="$BASE_DIR/modules"
SQL_CUSTOM_DIR="$BASE_DIR/data/sql/custom"
CONF_COLLECT_DIR="$BASE_DIR/env/dist/etc/modules"
LOG_DIR="$BASE_DIR/install-logs"
MANUAL_STEPS_FILE="$LOG_DIR/manual-steps.txt"
COLLISION_REPORT="$LOG_DIR/npc-id-collisions.txt"

# 옵션: FORCE=1 이면 이미 존재하는 모듈 디렉터리를 삭제 후 재설치
FORCE="${FORCE:-0}"
# 옵션: CORE_DIR 를 지정하면 core-PR/commit 요구사항을 실제로 검증한다 (03장 3절)
CORE_DIR="${CORE_DIR:-}"

mkdir -p "$MODULES_DIR" "$SQL_CUSTOM_DIR"/{db-world,db-characters,db-auth} "$CONF_COLLECT_DIR" "$LOG_DIR"
: > "$MANUAL_STEPS_FILE"
: > "$COLLISION_REPORT"

log()  { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }

# ── Tier 순서 (07-install-order.md 참조, 의존성 위반 방지) ──────────────
TIER1=(mod-playerbots)
TIER2=(mod-guildhouse)
TIER3=(mod-player-bot-guildhouse mod-ollama-chat mod-multibot-bridge mod-dungeon-clear mod-player-bot-level-brackets)
TIER4=(
  mod-individual-progression mod-autobalance mod-arac mod-auto-revive BGQueueChecker
  mod-breaking-news-override mod-challenge-modes mod-duel-reset mod-dynamic-xp mod-instance-reset
  mod-changeablespawnrates mod-TimeIsTime mod-ah-bot mod-boss-announcer mod-dead-means-dead
  mod-dynamic-loot-rates mod-improved-bank mod-phased-duels mod-pvp-titles mod-junk-to-gold
  mod-rdf-expansion mod-npc-beastmaster mod-npc-enchanter mod-reagent-bank mod-solo-lfg
  mod-transmog mod-who-logged mod-individual-xp mod-npc-spectator mod-1v1-arena
  mod-account-achievements mod-npc-buffer mod-npc-talent-template mod-low-level-rbg
  mod-better-item-reloading mod-desertion-warnings mod-emblem-transfer mod-fireworks-on-level
  mod-morphsummon mod-queue-list-cache mod-quick-teleport mod-reward-played-time mod-top-arena
  mod-racial-trait-swap mod_weather_vibe mod-fly-anywhere mod-leech mod-money-for-kills
  mod-no-hearthstone-cooldown mod-pvp-zones mod-skip-dk-starting-area mod-cfbg
  mod-npc-free-professions mod-random-enchants mod-war-effort mod-server-auto-shutdown
  mod-aoe-loot mod-account-mounts
)
ALL_MODULES=("${TIER1[@]}" "${TIER2[@]}" "${TIER3[@]}" "${TIER4[@]}")

# core 커밋 검증이 필요한 모듈 (03-module-dependencies.md 3절)
declare -A CORE_COMMIT_REQ=(
  [mod-ah-bot]=9adba48
  [mod-npc-beastmaster]=3f0739f
  [mod-improved-bank]=5b8bc79
  [mod-transmog]=b6cb9247
  [mod-npc-spectator]=5143872
  [mod-guildhouse]=77f1363
  [mod-racial-trait-swap]=de13bf4
  [mod-skip-dk-starting-area]=de13bf4
  [mod-no-hearthstone-cooldown]=5af98783
  [mod-cfbg]=d40e8946
)

# 기본 비활성 권장 모듈 (아직 clone/build는 하되 conf 활성화는 운영자가 판단, 06장 7절)
DISABLE_BY_DEFAULT=(mod-aoe-loot mod-dungeon-clear)

# Creatures.CustomIDs 공유 설정 (mod-npc-beastmaster README의 실제 예시값 기준, 05장 3절)
declare -A NPC_CUSTOM_IDS=(
  [mod-npc-beastmaster]=601026
  [mod-racial-trait-swap]=98888
  [mod-transmog]=190010
  [mod-guildhouse]=55005
  [mod-1v1-arena]=999991
  [mod-skip-dk-starting-area]=25462
)

# ── modules.lock 조회 ────────────────────────────────────────────────────
lock_field() { # lock_field <module-name> <field#(2=url,3=branch,4=commit)>
  awk -F'|' -v name="$1" '$1==name{print $'"$2"'}' "$LOCK_FILE"
}

# ── 1~4단계: clone + branch + commit checkout ───────────────────────────
install_one_module() {
  local name="$1"
  local url branch commit dest
  url="$(lock_field "$name" 2)"
  branch="$(lock_field "$name" 3)"
  commit="$(lock_field "$name" 4)"
  dest="$MODULES_DIR/$name"

  if [[ -z "$url" ]]; then
    err "modules.lock에 '$name' 항목이 없습니다 — 건너뜀"
    return 1
  fi

  if [[ -d "$dest" ]]; then
    if [[ "$FORCE" == "1" ]]; then
      warn "$name: 기존 디렉터리 삭제 후 재설치 (FORCE=1)"
      rm -rf "$dest"
    else
      log "$name: 이미 설치됨 (건너뜀, 재설치하려면 FORCE=1)"
      return 0
    fi
  fi

  log "$name: clone ($url, branch=$branch)"
  git clone --quiet --branch "$branch" "$url" "$dest"

  log "$name: checkout $commit"
  git -C "$dest" checkout --quiet "$commit"

  # core 커밋 요구사항 검증 (CORE_DIR 지정 시)
  if [[ -n "${CORE_COMMIT_REQ[$name]:-}" ]]; then
    local req="${CORE_COMMIT_REQ[$name]}"
    if [[ -n "$CORE_DIR" ]]; then
      if git -C "$CORE_DIR" merge-base --is-ancestor "$req" HEAD 2>/dev/null; then
        log "$name: core 커밋 요구사항($req) 충족 확인"
      else
        warn "$name: core 커밋 요구사항($req)이 $CORE_DIR 에서 확인되지 않음 — 수동 검증 필요"
        echo "[core-commit] $name requires core commit $req (unverified)" >> "$MANUAL_STEPS_FILE"
      fi
    else
      warn "$name: core 커밋 요구사항($req) — CORE_DIR 미지정으로 검증 생략"
      echo "[core-commit] $name requires core commit $req (verification skipped, set CORE_DIR to check)" >> "$MANUAL_STEPS_FILE"
    fi
  fi

  collect_sql "$name" "$dest"
  collect_conf "$name" "$dest"
  note_manual_steps "$name"
}

# ── 6~7단계: SQL 수집 (04-module-sql.md 참조) ───────────────────────────
collect_sql() {
  local name="$1" dest="$2"
  local db src target

  for db in db-world db-characters db-auth; do
    src="$dest/data/sql/$db"
    if [[ -d "$src" ]]; then
      target="$SQL_CUSTOM_DIR/$db/$name"
      mkdir -p "$target"
      cp -r "$src"/. "$target"/ 2>/dev/null || true
    fi
  done

  # 비표준 경로 처리: mod-player-bot-level-brackets는 data/sql/characters/ (db- 접두어 없음)
  if [[ -d "$dest/data/sql/characters" ]]; then
    target="$SQL_CUSTOM_DIR/db-characters/$name"
    mkdir -p "$target"
    cp -r "$dest/data/sql/characters"/. "$target"/ 2>/dev/null || true
    warn "$name: 비표준 SQL 경로(data/sql/characters/) 감지 → db-characters/custom으로 정규화 복사"
  fi

  # flat sql (표준 3분류 밖: mod-playerbots/playerbots, mod-ollama-chat, optional/sql)
  if [[ -d "$dest/data/sql/playerbots" ]]; then
    mkdir -p "$SQL_CUSTOM_DIR/playerbots"
    cp -r "$dest/data/sql/playerbots"/. "$SQL_CUSTOM_DIR/playerbots"/ 2>/dev/null || true
  fi

  # NPC entry ID 충돌 스캔 (03장 6절)
  if [[ -d "$SQL_CUSTOM_DIR" ]]; then
    grep -rhoE "INSERT INTO \`?creature_template\`? .*VALUES *\(([0-9]+)" "$SQL_CUSTOM_DIR" 2>/dev/null \
      | grep -oE "[0-9]+$" >> "$LOG_DIR/.all_creature_ids.tmp" || true
  fi
}

# ── 8단계: 설정 파일 수집 (05-module-config.md 참조) ────────────────────
collect_conf() {
  local name="$1" dest="$2"
  if [[ -d "$dest/conf" ]]; then
    mkdir -p "$CONF_COLLECT_DIR"
    find "$dest/conf" -maxdepth 1 -iname "*.conf.dist*" -exec cp {} "$CONF_COLLECT_DIR"/ \; 2>/dev/null || true
  fi

  # 기본 비활성 권장 모듈은 안내만 남기고 conf 내용은 건드리지 않는다
  # (정확한 Enable 키 이름이 문서상 확정되지 않은 경우 임의 sed는 위험하므로 수동 확인 유도)
  for d in "${DISABLE_BY_DEFAULT[@]}"; do
    if [[ "$name" == "$d" ]]; then
      warn "$name: 기본 비활성 권장 모듈 — env/dist/etc/modules/*.conf.dist 확인 후 Enable 옵션을 0으로 유지할 것"
      echo "[disable-by-default] $name: 06-docker-integration.md 7절 참조" >> "$MANUAL_STEPS_FILE"
    fi
  done
}

# ── 모듈별 수동 조치 기록 (07-install-order.md 체크리스트 참조) ─────────
note_manual_steps() {
  local name="$1"
  case "$name" in
    mod-instance-reset)
      echo "[manual] mod-instance-reset: 인게임 GM 명령 '.npc add 300000' 필요 (자동 스폰 안 됨)" >> "$MANUAL_STEPS_FILE" ;;
    mod-arac)
      echo "[manual] mod-arac: world DB에 arac.sql 수동 적용 확인 + 클라이언트 Patch-A.MPQ 배포 필요" >> "$MANUAL_STEPS_FILE" ;;
    mod-fly-anywhere)
      echo "[manual] mod-fly-anywhere: 클라이언트 Patch-O.mpq 배포 + 캐시 클리어 안내 필요, 서버 AreaTable.dbc 교체 확인" >> "$MANUAL_STEPS_FILE" ;;
    mod-multibot-bridge)
      echo "[manual] mod-multibot-bridge: 클라이언트 애드온 MultiBot-Chatless 배포 필요 (없으면 기능 전혀 안 보임)" >> "$MANUAL_STEPS_FILE" ;;
    mod-ollama-chat)
      echo "[manual] mod-ollama-chat: 외부 Ollama LLM 서버 기동 필요 + playerbots.conf 채팅충돌방지 7개 키 설정 필요" >> "$MANUAL_STEPS_FILE" ;;
    mod-player-bot-level-brackets)
      echo "[manual] mod-player-bot-level-brackets: mod-playerbots에 BotLevelBrackets.* 설정이 이미 있는지 확인 후 중복이면 비활성화" >> "$MANUAL_STEPS_FILE" ;;
    mod-changeablespawnrates)
      echo "[manual] mod-changeablespawnrates: custom_creatures 테이블 생성 SQL 수동 적용 확인" >> "$MANUAL_STEPS_FILE" ;;
    mod-npc-enchanter)
      echo "[manual] mod-npc-enchanter: README가 'SQL 없음'이라 하나 실제로는 world SQL 존재 — 반드시 적용 확인" >> "$MANUAL_STEPS_FILE" ;;
  esac
}

# ── worldserver.conf 공유 설정 계산 (Creatures.CustomIDs 등, 05장 3절) ──
generate_shared_conf_notes() {
  local ids=()
  local m
  for m in "${ALL_MODULES[@]}"; do
    if [[ -d "$MODULES_DIR/$m" && -n "${NPC_CUSTOM_IDS[$m]:-}" ]]; then
      ids+=("${NPC_CUSTOM_IDS[$m]}")
    fi
  done
  local joined
  joined=$(IFS=,; echo "${ids[*]}")

  {
    echo "# worldserver.conf 에 반영해야 하는 공유 설정 (05-module-config.md 3절)"
    echo "Creatures.CustomIDs = \"$joined\""
    [[ -d "$MODULES_DIR/mod-individual-progression" ]] && echo "EnablePlayerSettings = 1"
    [[ -d "$MODULES_DIR/mod-challenge-modes" ]] && echo "EnablePlayerSettings = 1"
    [[ -d "$MODULES_DIR/mod-individual-progression" ]] && echo "DBC.EnforceItemAttributes = 0"
    [[ -d "$MODULES_DIR/mod-dead-means-dead" ]] && echo "Instance.UnloadDelay = 0   # RAM 트레이드오프 있음, 06장 참조"
    [[ -d "$MODULES_DIR/mod_weather_vibe" ]] && echo "ActivateWeather = 0        # mod_weather_vibe 필수, 다른 날씨 기능과 배타적"
  } > "$LOG_DIR/worldserver-conf-overrides.txt"

  log "worldserver.conf 반영 필요 설정 → $LOG_DIR/worldserver-conf-overrides.txt"
}

# ── 10단계: NPC entry ID 충돌 검증 ───────────────────────────────────────
check_npc_id_collisions() {
  if [[ -f "$LOG_DIR/.all_creature_ids.tmp" ]]; then
    sort "$LOG_DIR/.all_creature_ids.tmp" | uniq -d > "$COLLISION_REPORT" || true
    rm -f "$LOG_DIR/.all_creature_ids.tmp"
    if [[ -s "$COLLISION_REPORT" ]]; then
      warn "NPC entry ID 충돌 의심 항목 발견 → $COLLISION_REPORT (수동 확인 필요)"
    else
      log "NPC entry ID 충돌 없음 (스캔 완료)"
    fi
  fi
}

# ── 메인 ─────────────────────────────────────────────────────────────────
main() {
  log "=== AzerothCore Playerbot 65개 모듈 설치 시작 ==="
  log "Tier 1 (Playerbot 핵심) 설치 중..."
  for m in "${TIER1[@]}"; do install_one_module "$m"; done

  log "Tier 2 (선행 요구 모듈) 설치 중..."
  for m in "${TIER2[@]}"; do install_one_module "$m"; done

  log "Tier 3 (Playerbot 의존 확장 모듈) 설치 중..."
  for m in "${TIER3[@]}"; do install_one_module "$m"; done

  log "Tier 4 (독립 모듈 58개) 설치 중..."
  for m in "${TIER4[@]}"; do install_one_module "$m"; done

  generate_shared_conf_notes
  check_npc_id_collisions

  local installed_count
  installed_count=$(find "$MODULES_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l)

  echo
  log "=== 설치 완료: ${installed_count}/65 모듈 ==="
  log "SQL 수집 위치     : $SQL_CUSTOM_DIR"
  log "설정 수집 위치    : $CONF_COLLECT_DIR"
  log "수동 조치 목록    : $MANUAL_STEPS_FILE"
  log "worldserver.conf 반영 필요 설정: $LOG_DIR/worldserver-conf-overrides.txt"
  [[ -s "$COLLISION_REPORT" ]] && warn "NPC ID 충돌 리포트: $COLLISION_REPORT"
  echo
  log "다음 단계: docker compose build --no-cache worldserver authserver && docker compose up -d"
  log "검증 절차는 07-install-order.md '검증 단계 매핑' 참조"
}

main "$@"
