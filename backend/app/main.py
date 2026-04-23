from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routers.search import router
from loguru import logger
from contextlib import asynccontextmanager
from elasticsearch import AsyncElasticsearch
from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.es = AsyncElasticsearch(settings.ELASTICSEARCH_URL)
    yield
    await app.state.es.close()

app = FastAPI()
app.include_router(router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"error": "서버 오류가 발생했습니다"})
