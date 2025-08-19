from fastapi import FastAPI

app = FastAPI(title="Cornhole Tournament API")


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}
