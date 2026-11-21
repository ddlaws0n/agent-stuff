# Runtime dependencies are prepared online; smoke tests run with --network none.
FROM python:3.13-slim-bookworm@sha256:4178fea840d0d85a1f4d4e768b4cc2ad71b5df43954e1836650c6d239039a4a3
COPY --from=ghcr.io/astral-sh/uv:0.12.22@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /usr/local/bin/uv
COPY requirements.txt /checks/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN uv pip install --system --no-cache --requirement /checks/requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /tmp
