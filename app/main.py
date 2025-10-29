from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import routes_auth, routes_onboarding
from app.db.supabase_client import supabase
from app.api.deps import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Initialize FastAPI
app = FastAPI(
    title="DispatchIQ Backend",
    version="1.0.0",
    description="Backend API powered by FastAPI + Supabase"
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "supabase_connected": supabase is not None}

app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(routes_onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
