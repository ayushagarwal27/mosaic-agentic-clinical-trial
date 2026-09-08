# MOSAIC : Multi Agent Clinical Trial Intelligence

- LangGraph
- LangMem
- LangSmith
- PostgresSQL, Vector Store (Neon)
- Backblaze B2
- React + Vite console, served by FastAPI

## Running

### Production-style — one server, one port

The API serves the compiled React console from the same process, so
there is nothing to deploy separately and no CORS to configure.

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000 — the console is at `/`, the API stays
at `/api/v1/*`, and Swagger remains at `/docs`.

If `frontend/dist` has not been built, the API still starts normally and
`/` returns the JSON descriptor instead of the console.

### Frontend development — hot reload

```bash
uvicorn api.main:app --reload     # terminal 1
cd frontend && npm run dev        # terminal 2 → http://localhost:5173
```

Vite proxies `/api` to uvicorn on port 8000, so the dev server talks to
the real backend and no environment variable needs setting.

## Console

| Tab       | Endpoint(s)                                     |
| --------- | ----------------------------------------------- |
| Analyze   | `POST /analyze`                                 |
| Signals   | `GET /signals`, `GET /signals/{id}`             |
| Review    | `GET /review/queue`, `PATCH /review/{queue_id}` |
| Memory    | `GET /memory/episodes`, `/memory/procedures/{agent}` |
| Sponsors  | `GET /sponsors`, `GET /sponsors/{name}`         |

An analysis run fans out six agents in parallel and takes minutes, so
the Analyze tab shows an elapsed timer rather than a progress bar —
the endpoint does not stream.
