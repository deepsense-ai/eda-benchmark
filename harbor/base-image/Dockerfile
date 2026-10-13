# Shared base for every task image: Python data stack plus the agent toolchain, so Harbor's
# per-trial agent setup finds everything in place instead of installing it from scratch
# (see README "Base image"). Built by `make base-image`; task Dockerfiles start FROM it.
FROM python:3.11.15-slim

# Small system deps Harbor's installers check for (curl, rg, pgrep); with them present
# Harbor skips its own apt-get, which otherwise pulls Debian's nodejs/npm (~650 packages).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates ripgrep procps \
 && rm -rf /var/lib/apt/lists/*

# Node via nvm in the location Harbor's install snippet uses, so `nvm install 22` is a no-op;
# the symlinks satisfy Harbor's `command -v node npm` checks.
ARG NVM_VERSION=v0.40.2
ARG NODE_VERSION_PIN=22.23.3
ENV NVM_DIR=/root/.nvm
RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh | env -u NODE_VERSION bash \
 && . "$NVM_DIR/nvm.sh" \
 && nvm install "$NODE_VERSION_PIN" && nvm alias default "$NODE_VERSION_PIN" \
 && ln -sf "$(command -v node)" /usr/local/bin/node \
 && ln -sf "$(command -v npm)" /usr/local/bin/npm \
 && ln -sf "$(command -v npx)" /usr/local/bin/npx

# Agent CLIs. Keep these versions in sync with `version` in harbor/model-benchmark*.yaml.
# codex and claude-code then skip installation entirely; opencode always reruns
# `npm i -g`, which the npm cache kept after its install serves (codex's is dropped).
ARG CODEX_VERSION=0.162.1
ARG OPENCODE_VERSION=1.19.0
ARG CLAUDE_CODE_VERSION=2.1.296
RUN . "$NVM_DIR/nvm.sh" \
 && npm install -g @openai/codex@"$CODEX_VERSION" \
 && npm cache clean --force
RUN . "$NVM_DIR/nvm.sh" \
 && npm install -g opencode-ai@"$OPENCODE_VERSION"
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s -- "$CLAUDE_CODE_VERSION"

# antigravity-cli: Harbor's `curl install.sh | bash` fails under pipefail when agy already exists,
# so `make base-image` copies this binary to harbor/.cache/agy and Harbor uploads it via
# binary_path. Auto-update is off so every trial uses this pinned build, from
# https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/linux_amd64.json
ENV AGY_CLI_DISABLE_AUTO_UPDATE=1
ARG AGY_URL=https://storage.googleapis.com/antigravity-public/antigravity-cli/1.3.4-5524158944247808/linux-x64/cli_linux_x64.tar.gz
ARG AGY_SHA512=dbdacfc5a1d9874fbbea3a21026d3990b4728e2e3487fd0316dc53cae9a3091023f969425828f3e2e0fadda43cea07dd978ea96f4ca7c202adf2201f419c56dd
RUN mkdir -p /tmp/agy /root/.local/bin \
 && curl -fsSL -o /tmp/agy/agy.tar.gz "$AGY_URL" \
 && echo "$AGY_SHA512  /tmp/agy/agy.tar.gz" | sha512sum -c - \
 && tar -xzf /tmp/agy/agy.tar.gz -C /tmp/agy antigravity \
 && install -m 755 /tmp/agy/antigravity /root/.local/bin/agy \
 && rm -rf /tmp/agy \
 && (/root/.local/bin/agy install || true) \
 && /root/.local/bin/agy --version

# Same data stack in every task; pinned to the versions the earlier benchmark images had.
RUN pip install --no-cache-dir pandas==3.0.3 numpy==2.4.6 scipy==1.17.1 scikit-learn==1.9.0
