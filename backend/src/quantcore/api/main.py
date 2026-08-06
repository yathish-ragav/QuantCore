from fastapi import FastAPI

from quantcore.api.router import router

app = FastAPI(
    title="QuantCore API",
    version="1.0.0",
    description="AI Equity Analysis Platform",
)

app.include_router(router)