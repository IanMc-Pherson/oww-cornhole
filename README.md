# oww-cornhole

This repository contains the product and technical specification for a cornhole tournament MVP.
See [MVP_SPEC.md](MVP_SPEC.md) for details.

## Backend

A minimal FastAPI app lives under `backend/`. To run it locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/health` for a health check endpoint.

## Frontend

A placeholder static page lives under `frontend/index.html`.
