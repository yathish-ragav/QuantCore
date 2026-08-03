from fastapi import FastAPI

app = FastAPI(
    title="QuantCore API",
    description="AI-Powered Institutional Equity Research Platform",
    version="0.1.0",
)

@app.get("/")
def root():
    return {
        "project": "QuantCore",
        "status": "running",
        "version": "0.1.0"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}