# EquiQuant Frontend Documentation

The EquiQuant frontend is a modern web dashboard built with **React**, **TypeScript**, and **Vite**. It provides a visual interface for stock analysis and market data.

## Getting Started

### Prerequisites

- **Node.js**: Version 18 or higher is recommended.
- **npm**: Usually comes with Node.js.

### Running in Development Mode

To run the frontend dashboard in development mode with Hot Module Replacement (HMR):

1.  **Start the Backend API**:
    The frontend requires the backend API to be running to fetch data.
    ```bash
    make ui-server
    ```
    This will start the FastAPI server at `http://localhost:8000`.

2.  **Start the Frontend**:
    In a new terminal window, navigate to the `ui` directory and start the Vite development server:
    ```bash
    cd ui
    npm install
    npm run dev
    ```
    The dashboard will be available at `http://localhost:5173`.

### Alternative: Using Make

For convenience, you can use the following `make` commands:

- **Start Backend**: `make ui-server`
- **Start Frontend**: `make ui-dev` (Requires `npm` to be installed)

## Project Structure

- `ui/src/`: Contains the React components and logic.
- `ui/public/`: Static assets.
- `ui/index.html`: Main entry point for the browser.
- `ui/vite.config.ts`: Configuration for Vite.

## Available Scripts

In the `ui` directory, you can run:

- `npm run dev`: Starts the development server.
- `npm run build`: Builds the application for production.
- `npm run lint`: Runs ESLint to check for code quality issues.
- `npm run preview`: Previews the production build locally.

## Design Principles

- **Component-Based**: We use small, reusable React components.
- **Type Safety**: TypeScript is used throughout the frontend to ensure type safety.
- **Performance**: Vite is used for fast development and optimized production builds.
