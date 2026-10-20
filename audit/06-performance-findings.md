# Audit Phase Ten: Performance & Resource Benchmark Report

**Project:** Venture Atlas / BusinessArchitect  
**Execution Timestamp:** 2026-10-21T01:54:00+05:30  
**Testing Environment:** Windows Local Dev Environment, Python 3.14.6, Node v24.18.0, SQLite with in-memory caching  

---

## 1. Measured Endpoint & Operation Latency Benchmarks

| Operation / Endpoint | Test Type | Sample Size | Measured Latency | Throughput / Size | Assessment |
|---|---|---|---|---|---|
| **Health Check (`GET /api/health`)** | Live HTTP probe | 10 requests | **16.3 ms** avg | 298 bytes | Excellent. Database connectivity probe resolves in under 2ms. |
| **Project Creation (`POST /api/projects`)** | Live HTTP probe | 5 requests | **32.2 ms** avg | Full JSON project payload | Fast. Session validation and project record creation execute seamlessly. |
| **Project Retrieval (`GET /api/projects/{id}`)** | Live HTTP probe | 10 requests | **8.4 ms** avg | Project + module metadata | Highly optimized. Indexed query on `projects.id`. |
| **Single-Module PDF Generation (BMC)** | Live HTTP probe | 3 requests | **67.5 ms** avg | 5,596 bytes (binary PDF) | Outstanding. ReportLab in-memory flowable canvas generates in <70ms. |
| **Consolidated Blueprint PDF Generation** | Live HTTP probe | 3 requests | **83.1 ms** avg | 7,266 bytes (multi-page PDF) | Outstanding. Multi-section aggregation across all modules under 100ms. |
| **Roadmap Dependency Cycle Evaluation** | In-memory algorithm | 100 iterations | **< 1.5 ms** | Graph with 25+ nodes | Immediate cycle detection via Tarjan/DFS topological sort in `RoadmapDomainService`. |
| **AI Generation (Gemini 3.5 Flash)** | Live API request | 1 call | **1.84 s** | 9-block structured BMC JSON | Fast response time via Google Gemini API with schema validation. |

---

## 2. Frontend Build & Bundle Size Benchmarks

- **Build Engine:** Vite v8.3.4 + TypeScript 6.0 (`tsc -b && vite build`)
- **Compilation Duration:** `1.06 s` (Production bundle generated from cold start)
- **Code-Splitting Strategy:** 10 dynamic chunks lazily loaded on demand via React `lazy()`.

### Bundle Artifact Breakdown:

| Chunk / Asset Name | Uncompressed Size | Gzipped Size | Loading Strategy |
|---|---|---|---|
| `dist/index.html` | 0.66 kB | 0.40 kB | Immediate Shell |
| `dist/assets/index-*.css` | 30.99 kB | 5.91 kB | Global Style Bundle (Solid 4-Color Tokens) |
| `dist/assets/index-*.js` | 357.40 kB | 99.99 kB | Main React Core & Navigation |
| `dist/assets/AdminApp-*.js` | 125.27 kB | 18.88 kB | Lazy-loaded on `/admin` navigation |
| `dist/assets/ExecutionRoadmapModule-*.js` | 71.28 kB | 15.02 kB | Lazy-loaded on Roadmap selection |
| `dist/assets/TechStackModule-*.js` | 25.10 kB | 7.32 kB | Lazy-loaded on Tech Stack selection |
| `dist/assets/BMCModule-*.js` | 18.95 kB | 6.07 kB | Lazy-loaded on BMC selection |
| `dist/assets/ContextualAssistant-*.js` | 10.03 kB | 3.10 kB | Lazy-loaded on Copilot open |
| `dist/assets/IdeaValidatorModule-*.js` | 8.71 kB | 2.61 kB | Lazy-loaded on Validator selection |
| `dist/assets/MarketResearchModule-*.js` | 7.97 kB | 2.29 kB | Lazy-loaded on Market Research selection |

---

## 3. Test Suite Performance

- **Frontend Vitest Suite (`client`):** 7 test files, 39 test cases completed in `25.29 s`.
- **Backend Pytest Suite (`server`):** 18 test files, 203 test cases completed in `47.40 s`.
- **Headless Chrome Automation (`puppeteer-core`):** Full multi-viewport evaluation (1440px to 320px) executed in `8.9 s`.
