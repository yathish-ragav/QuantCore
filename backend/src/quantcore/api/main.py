from fastapi import FastAPI

from quantcore.api.router import router


app = FastAPI(
    title="QuantCore API",
    version="1.0.0",
    description="AI-Powered Institutional Equity Research Platform",
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "project": "QuantCore",
        "status": "running",
        "version": "1.0.0",
    }