#!/bin/sh
set -eu

if [ -n "${HP_SHARED_KEY:-}" ]; then
  if [ -d /certs/frp ]; then
    tls_config='transport.tls.enable = true
transport.tls.certFile = "/certs/frp/client.crt"
transport.tls.keyFile = "/certs/frp/client.key"
transport.tls.trustedCaFile = "/certs/frp/ca.crt"
transport.tls.serverName = "harp.nc"'
  else
    tls_config='transport.tls.enable = false'
  fi
  cat > /frpc.toml <<EOF
serverAddr = "${HP_FRP_ADDRESS}"
serverPort = ${HP_FRP_PORT}
loginFailExit = false

${tls_config}

metadatas.token = "${HP_SHARED_KEY}"

[[proxies]]
remotePort = ${APP_PORT}
type = "tcp"
name = "${APP_ID}"
[proxies.plugin]
type = "unix_domain_socket"
unixPath = "${HP_EXAPP_SOCK:-/tmp/exapp.sock}"
EOF
  frpc -c /frpc.toml &
fi

exec "$@"
