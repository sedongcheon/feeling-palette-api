from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from domains.emotions.ui.routes import router as emotions_router

app = FastAPI(title="Feeling Palette API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(emotions_router)
