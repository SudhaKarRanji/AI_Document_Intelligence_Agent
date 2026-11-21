from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import ai_docu.api.health as health_api
import ai_docu.api.documents as documents_api
import ai_docu.api.chat as chat_api

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)

app = FastAPI(title="AI Documentation API", description="API for AI Documentation", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health_api.router)
app.include_router(documents_api.router)
app.include_router(chat_api.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the AI Documentation API!"}