from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dishka.integrations.fastapi import setup_dishka
from bson import ObjectId
from fastapi.encoders import ENCODERS_BY_TYPE

from src.di import setup_http_di
from src.routers import router
from src.core.exceptions import NotFoundError
from src.indecies import on_startup


ENCODERS_BY_TYPE[ObjectId] = str

EXCEPTION_HANDLERS: dict[type[Exception], tuple[int, str]] = {
    NotFoundError: (404, "Not found"),
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    await on_startup()
    yield


app = FastAPI(lifespan=lifespan)
setup_dishka(setup_http_di(), app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(NotFoundError)
async def exception_handler(_: Request, exc: Exception) -> Response:
    status_code, message = EXCEPTION_HANDLERS[type(exc)]
    raise HTTPException(status_code=status_code, detail=message)
