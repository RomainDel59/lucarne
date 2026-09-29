# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS builder

ARG TARGETARCH
ARG FRP_VERSION=0.61.1
ARG FRP_AMD64_SHA256=bff260b68ca7b1461182a46c4f34e9709ba32764eed30a15dd94ac97f50a2c40
ARG FRP_ARM64_SHA256=af6366f2b43920ebfe6235dba6060770399ed1fb18601e5818552bd46a7621f8
ARG DENO_VERSION=2.9.7
ARG DENO_AMD64_SHA256=c6527f24f4b16031d3ae4fa9f658d5f11534c8d84ce7dc8502420280919c3490
ARG DENO_ARM64_SHA256=c832298b1ad4422481334855f6003e0f54145762c5a134f20a489511d2f65bbf

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl unzip \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
  pip install --prefix=/install --no-compile --no-cache-dir -r /tmp/requirements.txt

RUN set -eux; \
  case "${TARGETARCH:-amd64}" in \
    arm64) archive_arch=arm64; expected="$FRP_ARM64_SHA256" ;; \
    *) archive_arch=amd64; expected="$FRP_AMD64_SHA256" ;; \
  esac; \
  curl -fsSL "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${archive_arch}.tar.gz" -o /tmp/frp.tar.gz; \
  echo "$expected  /tmp/frp.tar.gz" | sha256sum -c -; \
  tar -C /tmp -xzf /tmp/frp.tar.gz; \
  cp "/tmp/frp_${FRP_VERSION}_linux_${archive_arch}/frpc" /install/bin/frpc

RUN set -eux; \
  case "${TARGETARCH:-amd64}" in \
    arm64) archive_arch=aarch64; expected="$DENO_ARM64_SHA256" ;; \
    *) archive_arch=x86_64; expected="$DENO_AMD64_SHA256" ;; \
  esac; \
  curl -fsSL --retry 3 \
    "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-${archive_arch}-unknown-linux-gnu.zip" \
    -o /tmp/deno.zip; \
  echo "$expected  /tmp/deno.zip" | sha256sum -c -; \
  unzip /tmp/deno.zip -d /tmp/deno; \
  install -m 0755 /tmp/deno/deno /install/bin/deno

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=23000

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg procps tini \
  && rm -rf /var/lib/apt/lists/* \
  && useradd --create-home --uid 10001 --shell /usr/sbin/nologin lucarne

COPY --from=builder /install/ /usr/local/
COPY --chown=lucarne:lucarne src/ /app/src/
COPY --chown=lucarne:lucarne static/ /app/static/
COPY --chmod=0755 start.sh healthcheck.sh /

WORKDIR /app
ENTRYPOINT ["/usr/bin/tini", "--", "/start.sh"]
CMD ["python", "-m", "src.main"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=30 CMD ["/healthcheck.sh"]
