# sync-configs.sh — deploy/configs/ 아래 파일 중 ${BASE_DATA_DIR}/configs/에 아직
# 없는 파일만 복사한다. 이미 있는 파일은 절대 건드리지 않는다 — 운영자가 직접
# 튜닝한 값(포트, 배율, GM 계정 등)을 업데이트 때마다 날려버리면 안 되기 때문이다.
#
# 새 모듈이 추가되면 그 모듈의 기본 conf가 deploy/configs/modules/ 아래 새 파일로
# 들어오는데, 이 함수가 apply-update.sh/setup.sh 양쪽에서 호출되면서 "새 파일이니까
# 갖다 놓고, 기존 파일은 그대로 둔다"를 자동으로 처리한다 — 그래서 새 모듈을 켜기
# 위해 SSH로 들어가 conf를 수동으로 하나씩 복사할 필요가 없다.
sync_new_configs() {
  local base_data_dir="$1"
  local src_dir="$2"   # 보통 "configs" (deploy/ 기준 상대경로)
  local added=0
  local f rel dest

  while IFS= read -r -d '' f; do
    rel="${f#"$src_dir"/}"
    dest="$base_data_dir/configs/$rel"
    if [ ! -f "$dest" ]; then
      mkdir -p "$(dirname "$dest")"
      cp "$f" "$dest"
      echo ">> 새 설정 파일 추가: $rel"
      added=$((added + 1))
    fi
  done < <(find "$src_dir" -type f -print0)

  if [ "$added" -eq 0 ]; then
    echo ">> 새로 추가할 설정 파일 없음 (기존 설정 그대로 유지)"
  fi
}
