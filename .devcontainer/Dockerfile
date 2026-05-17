FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
	&& apt-get -y install --no-install-recommends make sqlite3 curl git ca-certificates \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a non-root user (vscode) to match DevContainer standards
RUN groupadd --gid 1000 vscode \
	&& useradd --uid 1000 --gid 1000 -m vscode \
	&& apt-get update && apt-get install -y sudo \
	&& echo vscode ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/vscode \
	&& chmod 0440 /etc/sudoers.d/vscode

# Set up workspace directory
WORKDIR /workspaces/equiquant
RUN chown vscode:vscode /workspaces/equiquant

# Set the default user to vscode
USER vscode

# Install uv as the vscode user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/vscode/.local/bin:${PATH}"
ENV UV_LINK_MODE=copy

# Install Node.js and pnpm manually (to keep it slim)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - \
	&& sudo apt-get install -y nodejs \
	&& sudo npm install -g pnpm \
	&& sudo apt-get clean && sudo rm -rf /var/lib/apt/lists/*

# Pre-install dependencies with persistent cache mounts
# This ensures that a single library update doesn't force a full re-download
COPY --chown=vscode:vscode pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/home/vscode/.cache/uv,uid=1000,gid=1000 \
	uv sync --no-install-project

COPY --chown=vscode:vscode ui/package.json ui/pnpm-lock.yaml ./ui/
RUN --mount=type=cache,id=pnpm,target=/home/vscode/.pnpm-store,uid=1000,gid=1000 \
	cd ui && pnpm install

# Ensure the rest of the app is available
COPY --chown=vscode:vscode . .
