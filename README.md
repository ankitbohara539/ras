# React + FastAPI + Supabase starter

This repository contains:

- `frontend/` — React, TypeScript, Vite, and Tailwind CSS
- `backend/` — FastAPI and the Supabase Python client

## Prerequisites

- Node.js 20+
- Python 3.11+
- A Supabase project

## 1. Configure Supabase

Create a project in Supabase, then copy the environment templates:

```powershell
Copy-Item frontend/.env.example frontend/.env
Copy-Item backend/.env.example backend/.env
```

Fill in the URL and keys from **Supabase Dashboard → Project Settings → API**.

- The frontend must only use the public anon/publishable key.
- Keep the service-role key only in `backend/.env`; never expose it in Vite variables.

The starter runs without Supabase credentials, but reports the integration as unconfigured.

## 2. Run the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API documentation is available at <http://localhost:8000/docs>.

## 3. Run the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` requests to FastAPI during development.

## Useful checks

```powershell
# frontend
cd frontend
npm run lint
npm run build

# backend
cd backend
python -m pytest
```

## Project structure

```text
.
├── frontend/
│   ├── src/
│   │   ├── lib/api.ts
│   │   ├── lib/supabase.ts
│   │   └── ...
│   └── vite.config.ts
└── backend/
    ├── app/
    │   ├── api/routes/health.py
    │   ├── core/config.py
    │   ├── services/supabase.py
    │   └── main.py
    └── tests/
```

