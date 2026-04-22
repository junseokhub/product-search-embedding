import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from app.routers.search import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    force=True
)
load_dotenv()

app = FastAPI()
app.include_router(router)