from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routes.catalog import router as catalog_router
from .routes.club import router as club_router
from .routes.evolutions import import_router as evolutions_import_router
from .routes.evolutions import router as evolutions_router
from .routes.gallery import router as gallery_router
from .routes.imports import ImportBodyLimit
from .routes.imports import router as imports_router
from .routes.objectives import import_router as objectives_import_router
from .routes.objectives import router as objectives_router
from .routes.players import router as players_router
from .routes.sbc import router as sbc_router
from .routes.solve import router as solve_router
from .routes.squad import router as squad_router
from .routes.value import router as value_router

app = FastAPI(title="FC Squad Lab API")

app.add_middleware(ImportBodyLimit)  # dentro de CORS: el 413 también lleva cabeceras CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3030", "http://127.0.0.1:3030"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(solve_router)
app.include_router(imports_router)
app.include_router(club_router)
app.include_router(sbc_router)
app.include_router(squad_router)
app.include_router(players_router)
app.include_router(catalog_router)
app.include_router(value_router)
app.include_router(evolutions_import_router)
app.include_router(evolutions_router)
app.include_router(objectives_import_router)
app.include_router(objectives_router)
app.include_router(gallery_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db": "ok" if db.ping() else "down"}
