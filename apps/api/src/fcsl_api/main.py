from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FC Squad Lab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3030"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db": "unchecked"}
