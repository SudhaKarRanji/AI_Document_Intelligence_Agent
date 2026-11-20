from fastapi import FastAPI
from dotenv import load_dotenv
import ai_docu.api.health as health_api
import ai_docu.api.documents as documents_api
import ai_docu.api.chat as chat_api

load_dotenv()

app = FastAPI(title="AI Documentation API", description="API for AI Documentation", version="1.0.0")
app.include_router(health_api.router)
app.include_router(documents_api.router)
app.include_router(chat_api.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the AI Documentation API!"}