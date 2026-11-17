from fastapi import FastAPI

app = FastAPI(title="FC Squad Lab API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db": "unchecked"}
