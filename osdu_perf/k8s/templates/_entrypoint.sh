#!/bin/sh
# Container entrypoint for osdu_perf k8s runs. Branches on $LOCUST_ROLE.
set -eu

cd /app

ROLE=${LOCUST_ROLE:-master}
LOCUSTFILE=${LOCUSTFILE:-/app/locustfile.py}
HOST=${LOCUST_HOST:?LOCUST_HOST is required}

COMMON="-f ${LOCUSTFILE} --headless --host=${HOST} --only-summary"

if [ "$ROLE" = "master" ]; then
    USERS=${LOCUST_USERS:?LOCUST_USERS is required}
    SPAWN_RATE=${LOCUST_SPAWN_RATE:-1}
    EXPECT_WORKERS=${LOCUST_EXPECT_WORKERS:-1}
    WEB_UI=${WEB_UI:-false}

    if [ "$WEB_UI" = "true" ]; then
        # Web-UI mode: keep master alive, expose UI on 0.0.0.0:8089.
        # User triggers runs from the browser; --headless and --run-time omitted.
        WEB_COMMON="-f ${LOCUSTFILE} --host=${HOST} --web-host=0.0.0.0 --web-port=8089"
        if [ -n "${LOCUST_WEB_BASE_PATH:-}" ]; then
            WEB_COMMON="$WEB_COMMON --web-base-path=${LOCUST_WEB_BASE_PATH}"
        fi
        if [ "$EXPECT_WORKERS" -le 0 ]; then
            unset LOCUST_EXPECT_WORKERS
            exec locust $WEB_COMMON
        fi
        exec locust $WEB_COMMON --master --master-bind-host=0.0.0.0 \
            --expect-workers "$EXPECT_WORKERS"
    fi

    RUN_TIME=${LOCUST_RUN_TIME:?LOCUST_RUN_TIME is required}
    if [ "$EXPECT_WORKERS" -le 0 ]; then
        # Standalone: no workers requested, run a single in-process Locust.
        unset LOCUST_EXPECT_WORKERS
        exec locust $COMMON \
            --users "$USERS" --spawn-rate "$SPAWN_RATE" --run-time "$RUN_TIME" \
            --csv=/tmp/locust/run --html=/tmp/locust/run.html
    fi
    exec locust $COMMON --master --master-bind-host=0.0.0.0 \
        --users "$USERS" --spawn-rate "$SPAWN_RATE" --run-time "$RUN_TIME" \
        --expect-workers "$EXPECT_WORKERS" \
        --csv=/tmp/locust/run --html=/tmp/locust/run.html
fi

if [ "$ROLE" = "worker" ]; then
    MASTER_HOST=${LOCUST_MASTER_HOST:?LOCUST_MASTER_HOST is required}
    exec locust $COMMON --worker --master-host="$MASTER_HOST"
fi

echo "ERROR: Unknown LOCUST_ROLE='$ROLE' (expected 'master' or 'worker')" >&2
exit 64
