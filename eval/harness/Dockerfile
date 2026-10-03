# Based on Pi's documented plain-Docker starter; no host config or keys are copied in.
FROM node:24-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git python3 ripgrep \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.87.1
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /usr/local/bin/

RUN useradd --uid 10001 --create-home --shell /bin/bash eval
USER 10001:10001
ENV HOME=/tmp/eval-home
WORKDIR /workspace
CMD ["pi", "--version"]
