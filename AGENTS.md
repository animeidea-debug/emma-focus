# Emma Focus collaboration guide

## Product purpose

Emma Focus is a private family tool for helping Emma build sustained attention and self-management habits. It turns daily activity records into understandable progress, then reinforces that progress through silver/gold coin rewards and a configurable privilege shop.

The primary user journeys are:

1. A parent records or imports a day's timeline and evaluation.
2. Emma and her parent review daily, monthly, and all-time focus trends.
3. The system derives token rewards or deductions from the evaluation.
4. Emma redeems accumulated tokens for configured rewards, or exchanges currencies.
5. Administrators maintain evaluations, rewards, exchange rates, and manual bonuses.

Time-lapse camera processing is an adjacent operational capability. It supports review of study/activity periods but is not part of the core web application's request path.

## Architecture and ownership

- `index.html`: family-facing dashboard, growth guide, token ledger, and redemption UI.
- `admin.html`: parent/admin data entry and reward configuration UI.
- `infra/web/backend/poc_main.py`: FastAPI business API on port 81; despite the historical `poc` name, it is the current GAS replacement.
- `infra/web/backend/main.py`: avatar API on port 80.
- SQLite database: `/app/data/poc.db` in the container, backed by a NAS host volume.
- `deploy/`: WebDAV deployment, backup wrapper, and disaster-recovery import tools.
- `video merge/`: Tdarr/ffmpeg time-lapse processing and notifications.
- `deprecated/`: historical reference only; do not revive without an explicit migration decision.

Repository boundary:

- This repository owns Emma Focus product code, backend code, data migration utilities, and application deployment scripts.
- The sibling NAS repository `animeidea-debug/NAS` owns production Docker Compose, nginx configuration, shared host mounts, and project cron.
- Do not recreate `infra/tdarr/` or `infra/webdav/` Compose files here. They were reconciled and removed on 2026-07-17; the NAS repository is their sole source of truth.
- Emma Focus backup code writes to `/app/backups` by default. The NAS repository must explicitly map that path and set `EMMA_BACKUP_BASE=/app/backups`; do not introduce a second production backup tree under `/app/data/Backups`.
- Normal Emma Focus deployment must exclude `video merge/.env`. Secrets are provisioned independently on the NAS and must never be copied, replaced, or permission-reset by the application deployment script.
- `/docker/backend` is shared with TMOS and Family Time Flow. Emma deployment may only use non-deleting `rclone copy` at that root; `rclone sync` is forbidden because it deletes sibling code and persistent data directories.
- The 08:00/20:00 backup schedule is owned by the NAS repository's UID 1002 user crontab. Do not add duplicate root cron entries here.

## Data model and invariants

The core SQLite tables are `evaluations`, `activity_logs`, `tokens`, `token_transactions`, `redeem_items`, `app_config`, and `api_log`.

Preserve these invariants:

- Production data lives outside containers through volume mapping: data outside, containers inside.
- Never commit `Emma_Focus_DB.xlsx`, SQLite databases, `.env` files, credentials, exported personal data, or avatar data.
- `Emma_Focus_DB.xlsx` is a disaster-recovery source, not the routine production database.
- Token balances are derived from `token_transactions` beginning at `TOKEN_START_DATE`; changes to reward logic require migration/recalculation analysis.
- Evaluation writes and their derived token transactions must remain consistent and idempotent for a given date.
- Backups must include a consistent SQLite snapshot plus readable CSV exports, retained independently of the running container.

## Safety rules

- Do not deploy automatically after editing. Validate locally, summarize the change, and obtain explicit approval before a production deployment.
- Do not commit, push, rewrite Git history, rotate credentials, or modify NAS production state unless explicitly requested.
- Never print or read credential values from Keychain or `.env` files during routine inspection.
- Before any production database mutation or recovery, verify a current backup and state the rollback path.
- Preserve existing uncommitted user changes. Do not reformat or rewrite unrelated files.
- Treat API authentication, authorization, and externally reachable write endpoints as security-sensitive.
- Do not edit files in `deprecated/` unless the task specifically concerns historical recovery.

## Development workflow

1. Read `README.md`, `docs/progress.md`, this file, and `git status` before changing the project.
2. Check whether the requested change belongs here or in the NAS repository.
3. Keep changes small and separate product behavior, infrastructure, documentation, and data migration work.
4. Run proportionate validation before handoff.
5. Update `README.md` or `docs/progress.md` when architecture, deployment, recovery, or operating status changes.
6. Deploy only after explicit approval, using `sh deploy/deploy.sh`; production Compose/nginx changes must be applied from the NAS repository.

Minimum static validation:

```sh
bash -n deploy/deploy.sh deploy/backup_data.sh
python3 -m py_compile infra/web/backend/main.py infra/web/backend/poc_main.py infra/web/backend/backup_data.py
git diff --check
```

Compilation may create `__pycache__` directories; remove only those generated by the current validation run and never use broad cleanup commands.

## Known priorities

- Review and split the current uncommitted work before committing it.
- Keep infrastructure requests documented and implement production Compose/nginx changes only in the NAS repository.
- Replace the historical shared secret and decide whether Git history needs sanitization.
- Add repeatable tests for token accounting, evaluation rewrites, redemption, exchange, backup, and XLSX recovery.
- Review authentication and exposure of all state-changing API routes before expanding external access.
