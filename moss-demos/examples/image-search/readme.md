<!-- markdownlint-disable-next-line MD033 -->
# <img src="https://github.com/user-attachments/assets/c4e39933-40c4-462d-a9a3-135458c6705f" alt="Moss logo" width="48" style="vertical-align: middle; margin-right: 8px;" /> Moss Demo Project - Image Search

Moss is a high-performance runtime for real-time semantic search. It delivers sub-10 ms lookups, instant index updates, and zero infra overhead. Moss runs where your agent lives - cloud, in-browser, or on-device - so search feels native and users never wait. You connect your data once; Moss handles indexing, packaging, distribution and updates.

This repo bundles thin, working examples that show how to talk to Moss from Python and JavaScript. Each sample keeps the scaffolding light so you can copy the essentials straight into your own projects.

> **Try out the live deployment of this sample project at https://moss-image-search-demo.vercel.app/**
> <img width="1512" height="942" alt="Image" src="https://github.com/user-attachments/assets/826715b2-4ea0-4346-b24e-2481b8f1d03a" />

## Quick Start

**1. Create a single `.env` at the repo root** — copy `.env.example` and fill in your Moss credentials:
```bash
cp .env.example .env
```
All sub-projects read from this one file.

**2. Create the Moss index** (`coco-data-1k.json` is included — no download needed):
```bash
cd setup-js && npm install && npx tsx createIndex.ts && cd ..
```

**3. Start the Python backend** (in one terminal):
```bash
cd backend-py
uv venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv sync
uvicorn main:app --reload
```

**4. Start the React app** (in another terminal):
```bash
cd react-app && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173) and start searching.

---

## 1. Go to Moss Portal and Get API Keys

- Visit [usemoss.dev](https://usemoss.dev/) to sign up, create an account, confirm your email, and sign in.
- From the dashboard, open **View secrets** and save the values as `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` in the root `.env` file (copy `.env.example` → `.env`).

> ![Moss Portal walkthrough](https://github.com/user-attachments/assets/c3db9d2d-0df5-4cec-99fd-7d49d0a30844)

## 2. Setup - Upload data and create index

All setup scripts read credentials from the **root `.env`** file (created in step 1). Use either the JS or Python tooling — they produce identical indexes.

### Setup JS

1. Navigate to the `setup-js` folder.
2. Install Node.js and npm.
3. Run `npm install` to install dependencies.
4. `npx tsx createIndex.ts` to create the index.
5. `npx tsx query.ts` to load the index and run sample queries.

### Setup Python

1. Navigate to the `setup-py` folder.
2. Install Python 3.10+ and uv.
3. Create and activate a virtual environment:
   - `uv venv`
   - On Windows: `.\venv\Scripts\activate`
   - On macOS/Linux: `source .venv/bin/activate`
4. Run `uv sync` to install dependencies.
5. Run `python create_index.py` to create the index.
6. Run `python query.py` to load the index and run sample queries.

## 4. Backend

A FastAPI backend is included in the `backend-py` folder. It proxies queries to Moss, keeping your API keys off the client. It reads credentials from the **root `.env`** file.

All routes are mounted under the `/demo/image-search` prefix:
- `GET /demo/image-search/search` — semantic search endpoint
- `GET /demo/image-search/health` — health check
- `GET /demo/image-search/image-proxy` — secure image proxy (rewrites `http://` COCO URLs to pass through the backend)

**Development server:**
1. Navigate to the `backend-py` folder.
2. Install Python 3.10+ and uv.
3. `uv venv && source .venv/bin/activate`
4. `uv sync` to install dependencies.
5. Run `uvicorn main:app --reload` to start the server.

**Docker:**
```bash
cd backend-py
docker build -t moss-backend .
docker run -p 8080:8080 --env-file ../.env moss-backend
```

## 5. React App powered by Moss

A sample React app is included in the `react-app` folder that demonstrates how to integrate Moss for semantic search. It reads `MOSS_PYTHON_API_URL` from the **root `.env`** file via Vite's env loading.

1. Navigate to the `react-app` folder.
2. Install Node.js and npm.
3. Run `npm install` to install dependencies.
4. Run `npm run dev` to start the development server.

## Resources

- [Docs](https://docs.moss.dev/?utm_source=github&utm_medium=readme&utm_campaign=image-search)
- [Portal](https://portal.usemoss.dev/?utm_source=github&utm_medium=readme&utm_campaign=image-search)
- [GitHub](https://github.com/usemoss/moss)
- [Discord](https://discord.com/invite/eMXExuafBR?utm_source=github&utm_medium=readme&utm_campaign=image-search)
