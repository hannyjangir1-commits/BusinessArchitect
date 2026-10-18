# Business Architect client

The client is the React and TypeScript application for Business Architect. Vite serves the local development UI at `http://localhost:5173` and proxies `/api` requests to the FastAPI server at `http://127.0.0.1:8000`.

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Start the backend from `../server` as described in the repository's [main README](../README.md). Configure local backend settings using a safe local database and the required environment variables.

## Verify client changes

```bash
npm test
npm run build
npm run lint
```

The application presents four project stages (`Idea`, `MVP`, `Post-launch`, and `Growth`) and a single Roadmap & Execution Plan module. BMC and roadmap visualizations are interactive SVG mind maps; their full generated details are available through the module UI and exports.
