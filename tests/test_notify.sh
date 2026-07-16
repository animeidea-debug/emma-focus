#!/bin/sh
set -eu

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NOTIFY_SCRIPT="${PROJECT_ROOT}/video merge/notify.sh"

test_success() (
    curl() { return 0; }
    export PUSHOVER_NAS_TOKEN=dummy-token
    export PUSHOVER_NAS_USER=dummy-user
    . "$NOTIFY_SCRIPT"
    pushover_notify "Test" "success" 0
)

test_failure() (
    curl() { return 22; }
    export PUSHOVER_NAS_TOKEN=dummy-token
    export PUSHOVER_NAS_USER=dummy-user
    . "$NOTIFY_SCRIPT"
    set +e
    pushover_notify "Test" "failure" 1
    status=$?
    set -e
    [ "$status" -eq 22 ]
)

test_success
test_failure
echo "notify tests passed"
