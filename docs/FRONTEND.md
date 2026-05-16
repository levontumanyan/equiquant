# EquiQuant Frontend Documentation

The EquiQuant frontend is a modern web dashboard built with **React**, **TypeScript**, and **Vite**. It provides a visual interface for stock analysis and market data.

## Zero-Pollution Architecture

The frontend is designed to run without requiring a global Node.js installation. 

- **Runtime**: Managed by `uv` via `nodejs-wheel`.
- **Package Manager**: Automatically switches between `pnpm` (if available globally) and `uv run npm` (isolated).

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

If you prefer to manage the UI separately, navigate to the `ui` directory:

```bash
cd ui
make ui-dev   # (From root) Starts the Vite server
```

For package management:
- **Install**: `uv run npm install`
- **Dev**: `uv run npm run dev`

## Available Scripts (in `ui` directory)

- `dev`: Starts the development server.
- `build`: Builds the application for production.
- `lint`: Runs ESLint to check for code quality issues.
- `preview`: Previews the production build locally.

## Design Principles

- **Zero Global Dependencies**: Only `uv` is required to run the entire stack.
- **Component-Based**: We use small, reusable React components.
- **Type Safety**: TypeScript is used throughout the frontend.
- **Performance**: Vite is used for fast development and optimized production builds.
