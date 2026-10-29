#!/bin/sh
set -eu
[ "${3:-}" = '..data' ] || exit 0
[ -s /tmp/nginx.pid ] || exit 0
if nginx -t -c /tmp/nginx.conf >/dev/null 2>&1 && nginx -s reload -c /tmp/nginx.conf >/dev/null 2>&1; then
  rm -f /tmp/tls-reload-failed
  echo 'Redis TLS frontend certificate/trust reloaded'
  exit 0
fi
# Keep the previous workers and all existing broker connections intact.
touch /tmp/tls-reload-failed
echo 'Redis TLS frontend reload failed; previous TLS context retained' >&2
exit 0
