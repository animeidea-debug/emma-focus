#!/bin/sh
set -eu

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR=$(mktemp -d /tmp/emma-backup-wrapper.XXXXXX)
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/docker" <<'EOF'
#!/bin/sh
case "$1" in
    ps) echo site_backend ;;
    exec) exit "${FAKE_BACKUP_EXIT:-0}" ;;
    *) exit 2 ;;
esac
EOF
chmod +x "$TMP_DIR/docker"

STATE_DIR="$TMP_DIR/state"
TODAY=$(date +%Y%m%d)
DOCKER_BIN="$TMP_DIR/docker" BACKUP_STATE_DIR="$STATE_DIR" FAKE_BACKUP_EXIT=0 \
    sh "$PROJECT_ROOT/deploy/backup_data.sh"
test -f "$STATE_DIR/$TODAY.success"
test ! -f "$STATE_DIR/$TODAY.failed"

set +e
DOCKER_BIN="$TMP_DIR/docker" BACKUP_STATE_DIR="$STATE_DIR" FAKE_BACKUP_EXIT=7 \
    sh "$PROJECT_ROOT/deploy/backup_data.sh"
status=$?
set -e
test "$status" -eq 7
test -f "$STATE_DIR/$TODAY.failed"

echo "backup wrapper tests passed"
