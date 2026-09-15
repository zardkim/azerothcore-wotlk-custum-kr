#!/usr/bin/env bash
#
# check-updates.sh — 코어(azerothcore-wotlk 저장소 자신)와 modules.lock에 고정된
# 65개 모듈의 최신 commit을 원격에서 조회해서, 지금 고정된 버전과 몇 커밋 차이나는지
# 보여준다. 아무것도 자동으로 바꾸지 않는다 — mod-playerbots처럼 코어에 큰 영향을 주는
# 모듈도 있어서, 실제 반영 여부는 사람이 변경 로그를 보고 판단해야 한다
# (.agents/plans/ops-backup-reset-update/ 계획서 3.1절 참고).
#
# 반영 절차(자동화 안 됨): modules.lock의 해당 줄을 새 commit으로 수정
#   -> install-modules.sh 재실행 -> 이미지 재빌드 -> scripts/apply-update.sh로 배포.
#
# 사용법: ./check-updates.sh
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."   # repo 루트로 이동 (modules.lock 기준)

if [ ! -f modules.lock ]; then
  echo "[오류] modules.lock을 찾을 수 없습니다 (repo 루트에서 실행하세요)." >&2
  exit 1
fi

echo "########################################################################"
echo " 코어(azerothcore-wotlk) 업데이트 확인"
echo "########################################################################"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
LOCAL_HEAD=$(git rev-parse HEAD)
if git fetch origin "$CURRENT_BRANCH" --quiet 2>/dev/null; then
  REMOTE_HEAD=$(git rev-parse "origin/$CURRENT_BRANCH")
  if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "  최신 상태입니다 (origin/$CURRENT_BRANCH == HEAD)."
  else
    BEHIND=$(git rev-list --count "HEAD..origin/$CURRENT_BRANCH")
    echo "  origin/$CURRENT_BRANCH 가 HEAD보다 $BEHIND 커밋 앞서 있습니다. 최근 변경:"
    # head로 자르면 git log가 SIGPIPE를 받아 set -e pipefail 아래서 스크립트 전체가
    # 죽는다 (실제로 겪은 버그) - git 자체의 -<n>으로 제한해서 파이프를 하나 줄인다.
    git log -10 --oneline "HEAD..origin/$CURRENT_BRANCH" | sed 's/^/    /'
  fi
else
  echo "  [경고] origin/$CURRENT_BRANCH fetch 실패 — 네트워크 또는 브랜치명을 확인하세요." >&2
fi

echo
echo "########################################################################"
echo " 모듈 업데이트 확인 (modules.lock 기준)"
echo "########################################################################"
printf "%-34s %-12s %-12s %s\n" "모듈" "고정 commit" "최신 commit" "상태"
printf "%-34s %-12s %-12s %s\n" "----" "----------" "----------" "----"

UPDATED_COUNT=0
FAILED_COUNT=0

while IFS='|' read -r name url branch commit _date; do
  name="${name//$'\r'/}"
  url="${url//$'\r'/}"
  branch="${branch//$'\r'/}"
  commit="${commit//$'\r'/}"
  [[ -z "$name" || "$name" == \#* ]] && continue

  remote_commit=$(git ls-remote "$url" "refs/heads/$branch" 2>/dev/null | cut -f1)
  if [ -z "$remote_commit" ]; then
    printf "%-34s %-12s %-12s %s\n" "$name" "${commit:0:10}" "-" "조회 실패"
    FAILED_COUNT=$((FAILED_COUNT + 1))
    continue
  fi

  if [ "$remote_commit" = "$commit" ]; then
    printf "%-34s %-12s %-12s %s\n" "$name" "${commit:0:10}" "${remote_commit:0:10}" "최신"
  else
    printf "%-34s %-12s %-12s %s\n" "$name" "${commit:0:10}" "${remote_commit:0:10}" "업데이트 있음"
    UPDATED_COUNT=$((UPDATED_COUNT + 1))
  fi
done < <(grep -v '^#' modules.lock | grep -v '^[[:space:]]*$')

echo
echo "총 업데이트 있음: $UPDATED_COUNT, 조회 실패: $FAILED_COUNT"
echo "반영은 modules.lock을 직접 수정한 뒤 install-modules.sh 재실행 -> 이미지 재빌드로 진행하세요."
