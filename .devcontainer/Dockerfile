FROM mcr.microsoft.com/devcontainers/python:3.12

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
	&& apt-get -y install --no-install-recommends make sqlite3 curl git

# Set the default user to vscode
USER vscode

# Install uv as the vscode user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js using nvm (pre-installed in the base image)
ARG NODE_VERSION=20
RUN bash -c "source /usr/local/share/nvm/nvm.sh && nvm install ${NODE_VERSION} && nvm use ${NODE_VERSION} && npm install -g pnpm"

# Ensure uv and node are in the path
ENV PATH="/home/vscode/.local/bin:${PATH}"
