from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routes.solve import router as solve_router

app = FastAPI(title="FC Squad Lab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3030", "http://127.0.0.1:3030"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(solve_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db": "ok" if db.ping() else "down"}
