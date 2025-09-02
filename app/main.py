from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import routes_auth, routes_users, routes_onboarding
from app.db.supabase_client import supabase

# Initialize FastAPI
app = FastAPI(
    title="DispatchIQ Backend",
    version="1.0.0",
    description="Backend API powered by FastAPI + Supabase"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "supabase_connected": supabase is not None}

app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(routes_users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(routes_onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])

