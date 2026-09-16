<div align="center">

# AzerothCore Playerbot Korean-Localized Repack (KR)

[한국어](README.md) | **[English](README.en.md)**

A personal custom build on top of [AzerothCore](https://www.azerothcore.org/) +
[mod-playerbots](https://github.com/mod-playerbots/mod-playerbots), with **65 bundled
modules**, **Korean localization patches**, and a **ready-to-deploy Docker stack**.

</div>

---

## Project Overview

This project is a fully Korean-localized personal server repack of **World of Warcraft:
Wrath of the Lich King (3.3.5a)**, run on the [AzerothCore](https://www.azerothcore.org/)
engine. Three things define it:

- **A living world filled with human-like bots** — built on
  [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots), so even a single
  player can run parties, raids, and battlegrounds with bots, and the world is
  populated with random bots questing and roaming like real players.
- **Gameplay extended by 65 bundled modules** — transmogrification, guild houses,
  automatic instance difficulty scaling (AutoBalance), challenge modes (hardcore,
  self-crafted-gear-only, etc.), staged expansion progression (Individual
  Progression), an auction house bot, account-wide mounts/achievements,
  cross-faction battlegrounds, and many more third-party and official modules
  combine into a much richer experience than vanilla AzerothCore
  (full list: [Wiki: Module list](../../wiki/사용-모듈-목록)).
- **Full Korean localization** — roughly 90,000 Korean playerbot names, translated
  and corrected item/NPC/guild-house text, 172 trainer/vendor NPCs on the "GM
  island," starting-gear grants, and more, across the game's content
  (details: [Wiki: Localization history](../../wiki/한글화-내역)).

On top of that, this repository ships a **Docker deploy stack** (world/auth
servers, a pre-baked and already-localized DB image, a web portal) and
**operational automation for account/character backup & restore, server reset,
and core/module updates** — everything needed for one person to stand up and run
the server end to end.

This repository exists for three reasons:
1. **Preserve** the Korean-localized source and configuration under version control.
2. Keep the update/rebuild process **convenient** by scripting it, for future reference.
3. Keep the core (AzerothCore) and modules on their original lineage, so upstream
   changes can still be tracked/merged later.

> This repository is based on
> [mod-playerbots/azerothcore-wotlk](https://github.com/mod-playerbots/azerothcore-wotlk),
> itself a fork of [azerothcore/azerothcore-wotlk](https://github.com/azerothcore/azerothcore-wotlk).
> The core itself is licensed under [GPL v2](LICENSE); the original project's own
> README is kept untouched at [.github/README.md](.github/README.md).

## What this repository adds/customizes

| Area | What | Where |
|---|---|---|
| **65 modules** | mod-playerbots and 64 others, installed at pinned commits | `modules.conf`, `modules.lock`, `install-modules.sh` |
| **Korean localization** | Names/items/NPCs/guild house etc. Korean SQL patches + Korean DBC | `한글화/`, `kr-patch/` — full list in **[Wiki: Localization history](../../wiki/한글화-내역)** |
| **Docker deploy stack** | DB (pre-baked, localized image) + world/auth server + web portal, 5-6 containers | `deploy/` (usage in [deploy/README.md](deploy/README.md)) |
| **Account/character backup & restore** | CLI scripts + admin web UI (`/admin/backups`) | `deploy/scripts/backup.sh`, `restore.sh` |
| **Server reset** | Safely revert to the baseline (modules + localization applied) state | `deploy/scripts/reset.sh` |
| **Core/module updates** | Check remote latest commits + automated incremental SQL apply | `deploy/scripts/check-updates.sh`, `apply-update.sh` |
| **Web portal** | Registration/server status/board/admin pages (Next.js) | To be split into its own repository |

The full module list (grouped by category) is in
**[Wiki: Module list](../../wiki/사용-모듈-목록)**.

## Quick start (deployment)

```bash
cd deploy
cp .env.example .env
vi .env   # set BASE_DATA_DIR, DOCKER_REGISTRY, etc.
./setup.sh
docker compose pull && docker compose up -d
```

See [deploy/README.md](deploy/README.md) for the full procedure, including
backup/restore/reset/update.

## Building the core yourself

This repository contains the full AzerothCore core source, so the standard
AzerothCore build procedure ([official wiki](http://www.azerothcore.org/wiki/installation))
applies as-is. `AGENTS.md` and `.agents/docs/` have build/coding guides specific to
this repository.

## Layout

```
├── src/, data/sql/base|updates, apps/, conf/   AzerothCore core (original lineage kept)
├── modules/                                     65 modules (created on install, not tracked)
├── modules.conf, modules.lock, install-modules.sh   Reproducible module install
├── kr-patch/                                    Dockerfiles/scripts that bake the localized DB
├── 한글화/                                       Korean localization SQL patches (source)
└── deploy/                                       Docker deploy stack (compose, ops scripts)
```

## Credits

- Core: [AzerothCore](https://github.com/azerothcore/azerothcore-wotlk) and contributors — [AUTHORS](AUTHORS)
- Playerbots: [mod-playerbots](https://github.com/mod-playerbots/mod-playerbots)
- The Korean localization and deployment automation in this repository is personal work.
