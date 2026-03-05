from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routers import health, stories

app = FastAPI(
    title="Bedtime Stories API",
    description="API for generating illustrated children's storybooks",
    version="1.0.0",
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(stories.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")
