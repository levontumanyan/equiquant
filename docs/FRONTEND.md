# EquiQuant Frontend Documentation

The EquiQuant frontend is a modern web dashboard built with **React**, **TypeScript**, and **Vite**. It provides a visual interface for stock analysis and market data.

## Zero-Pollution Architecture

The frontend is designed to run without requiring a global Node.js installation. 

- **Runtime**: Managed by `uv` via `nodejs-wheel`.
- **Package Manager**: Defaults to `uv run npm` for an isolated, zero-pollution experience.

## Quick Start

The easiest way to start the dashboard is from the root directory:

1.  **Install Everything**:
    ```bash
    make install
    ```
    This sets up both the Python backend and the React frontend dependencies.

2.  **Start the Dashboard**:
    ```bash
    make ui-start
    ```
    This starts the API server and the Vite development server simultaneously.
    - **Frontend**: [http://localhost:8888](http://localhost:8888)
    - **API**: [http://localhost:8000](http://localhost:8000)

## Manual Management

If you prefer to manage the UI separately, you can use the following commands from the **root directory**:

```bash
make ui-server   # Starts the API backend
make ui-dev      # Starts the Vite frontend
```

For package management (from the `ui/` directory):
- **Install**: `../.venv/bin/npm install` (or `uv run npm install` from root)
- **Dev**: `../.venv/bin/npm run dev` (or `uv run npm run dev` from root)

*Note: Developers who prefer `pnpm` can override the package manager: `make PM=pnpm ui-start`.*

## Available Scripts (in `ui/` directory)

- `dev`: Starts the development server.
- `build`: Builds the application for production.
- `lint`: Runs ESLint to check for code quality issues.
- `preview`: Previews the production build locally.

## Design Principles

- **Zero Global Dependencies**: Only `uv` is required to run the entire stack.
- **Component-Based**: We use small, reusable React components.
- **Type Safety**: TypeScript is used throughout the frontend.
- **Performance**: Vite is used for fast development and optimized production builds.
