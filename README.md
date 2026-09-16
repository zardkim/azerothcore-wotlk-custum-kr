<div align="center">

# AzerothCore Playerbot 한글화 리팩 (KR)

**[한국어](README.md)** | [English](README.en.md)

[AzerothCore](https://www.azerothcore.org/) + [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots) 기반,
**65개 모듈**과 **한글화 패치**를 적용하고 **Docker로 바로 배포**할 수 있게 만든 개인용 커스텀 빌드

</div>

---

## 프로젝트 소개

이 프로젝트는 **월드 오브 워크래프트: 리치 왕의 분노(3.3.5a)** 서버를 [AzerothCore](https://www.azerothcore.org/)
엔진으로 직접 구동하는, 완전히 한글화된 개인 서버 리팩입니다. 핵심은 다음 세 가지입니다.

- **사람처럼 행동하는 봇으로 채워진 살아있는 월드** — [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots)를
  기반으로 하고 있어서, 사람이 적어도 파티/레이드/전장을 봇과 함께 진행할 수 있고,
  월드에는 퀘스트를 하고 돌아다니는 랜덤 봇들이 실제 플레이어처럼 존재합니다.
- **65개 모듈로 확장된 게임플레이** — 트랜스모그, 길드하우스, 인스턴스 난이도 자동
  조절(AutoBalance), 하드코어/자체제작장비 등 챌린지 모드, 확장팩별 단계적 진행
  (Individual Progression), 경매장 봇, 계정 공용 마운트/업적, 크로스팩션 전장 등
  다양한 서드파티·공식 모듈을 조합해 바닐라보다 훨씬 풍부한 플레이 경험을 제공합니다
  (전체 목록: [Wiki: 사용 모듈 목록](../../wiki/사용-모듈-목록)).
- **완전한 한글화** — 플레이어봇 9만여 개의 한글 이름, 아이템·NPC·길드하우스 텍스트,
  GM섬 트레이너/벤더 172종, 초반 지급 아이템 등 게임 콘텐츠 전반이 한글로 번역·보정돼
  있습니다 (자세히: [Wiki: 한글화 내역](../../wiki/한글화-내역)).

여기에 더해, 이 서버를 실제로 운영하기 위한 **Docker 배포 스택**(월드/인증서버, 이미
한글화가 적용된 DB 이미지, 웹 포털)과 **계정/캐릭터 백업·복원, 서버 초기화, 코어/모듈
업데이트를 위한 운영 자동화 스크립트**까지 함께 갖추고 있어서, 개인이 처음부터 끝까지
서버를 세우고 운영할 수 있도록 만들어졌습니다.

## 이 저장소의 목적
1. 한글화된 소스와 설정을 **버전관리로 보전**한다.
2. 나중에 **업데이트/재구축을 편리하게** 할 수 있도록 절차를 스크립트로 남긴다.
3. 코어(AzerothCore)와 모듈은 원본 계보를 그대로 유지해서, 나중에 upstream 변경사항을
   추적/병합할 수 있게 한다.

> 이 저장소는 [azerothcore/azerothcore-wotlk](https://github.com/azerothcore/azerothcore-wotlk)의
> 포크인 [mod-playerbots/azerothcore-wotlk](https://github.com/mod-playerbots/azerothcore-wotlk)를
> 기반으로 합니다. 코어 자체의 라이선스는 [GPL v2](LICENSE)이며, 원본 프로젝트 소개는
> [.github/README.md](.github/README.md)에 그대로 남겨뒀습니다.

## 이 저장소에 추가/커스터마이징한 것

| 구분 | 내용 | 위치 |
|---|---|---|
| **모듈 65개** | mod-playerbots 포함 65개 모듈을 특정 commit에 고정 설치 | `modules.conf`, `modules.lock`, `install-modules.sh` |
| **한글화** | 이름/아이템/NPC/길드하우스 등 한글 패치 SQL + 한글 DBC | `한글화/`, `kr-patch/` — 자세한 목록은 **[Wiki: 한글화 내역](../../wiki/한글화-내역)** |
| **Docker 배포 스택** | DB(한글화 완료본 베이크드 이미지)+월드/인증서버+웹 포털, 5~6개 컨테이너 | `deploy/` (사용법은 [deploy/README.md](deploy/README.md)) |
| **계정/캐릭터 백업·복원** | CLI 스크립트 + 관리자 웹 UI(`/admin/backups`) | `deploy/scripts/backup.sh`, `restore.sh` |
| **서버 초기화** | 베이스라인(모듈+한글화 적용 완료 상태)으로 안전하게 되돌리기 | `deploy/scripts/reset.sh` |
| **코어/모듈 업데이트** | 원격 최신 commit 확인 + 증분 SQL 반영 자동화 | `deploy/scripts/check-updates.sh`, `apply-update.sh` |
| **웹 포털** | 계정가입/서버상태/게시판/관리자 페이지 (Next.js) | 별도 저장소로 분리 예정 |

전체 모듈 목록(카테고리별 표)은 **[Wiki: 사용 모듈 목록](../../wiki/사용-모듈-목록)**에
정리해뒀습니다.

## 빠른 시작 (배포)

```bash
cd deploy
cp .env.example .env
vi .env   # BASE_DATA_DIR, DOCKER_REGISTRY 등 지정
./setup.sh
docker compose pull && docker compose up -d
```

자세한 절차, 백업/복원/초기화/업데이트 방법은 [deploy/README.md](deploy/README.md)를
참고하세요.

## 코어를 직접 빌드하고 싶다면

이 저장소는 AzerothCore 코어 소스를 그대로 포함하고 있어서, 표준 AzerothCore 빌드
절차([공식 위키](http://www.azerothcore.org/wiki/installation))를 그대로 따르면 됩니다.
`AGENTS.md`와 `.agents/docs/`에 이 저장소 기준 빌드/코딩 가이드가 정리돼 있습니다.

## 구조

```
├── src/, data/sql/base|updates, apps/, conf/   AzerothCore 코어 (원본 계보 유지)
├── modules/                                     65개 모듈 (설치 시 생성, git 추적 안 함)
├── modules.conf, modules.lock, install-modules.sh   모듈 설치 자동화
├── kr-patch/                                    한글화 DB를 굽는 Dockerfile/스크립트
├── 한글화/                                       한글화 SQL 패치 원본
└── deploy/                                       Docker 배포 스택 (compose, 운영 스크립트)
```

## 크레딧

- 코어: [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk)와 기여자 — [AUTHORS](AUTHORS)
- 플레이어봇: [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots)
- 이 저장소의 한글화/배포 자동화는 개인 작업입니다.
