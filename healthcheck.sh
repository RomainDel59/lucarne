#!/bin/sh
set -eu
if [ -n "${HP_SHARED_KEY:-}" ]; then
  pgrep -x frpc >/dev/null
  test -S "${HP_EXAPP_SOCK:-/tmp/exapp.sock}"
else
  curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT:-23000}/heartbeat" >/dev/null
fi
