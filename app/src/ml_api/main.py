import os
import time

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from ml_api.metrics import PREDICTION_LATENCY, REQUEST_COUNT
from ml_api.model import ModelService

app = FastAPI(title="MLOps Kubernetes Demo API")

model_service = ModelService()

MODEL_VERSION = os.getenv("MODEL_VERSION", "local")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class PredictionRequest(BaseModel):
    features: list[float]


class PredictionResponse(BaseModel):
    prediction: float
    model_version: str


@app.get("/")
def root():
    REQUEST_COUNT.labels(endpoint="/").inc()
    return {
        "message": "MLOps API is running",
        "model_version": MODEL_VERSION,
        "log_level": LOG_LEVEL,
    }


@app.get("/health/live")
def live():
    REQUEST_COUNT.labels(endpoint="/health/live").inc()
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    REQUEST_COUNT.labels(endpoint="/health/ready").inc()

    if model_service.ready:
        return {"status": "ready"}

    return Response(status_code=503)


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    REQUEST_COUNT.labels(endpoint="/predict").inc()

    start = time.time()
    prediction = model_service.predict(request.features)
    PREDICTION_LATENCY.observe(time.time() - start)

    return PredictionResponse(
        prediction=prediction,
        model_version=MODEL_VERSION,
    )


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=(
            CONTENT_TYPE_LATEST.decode("utf-8")
            if isinstance(CONTENT_TYPE_LATEST, bytes)
            else CONTENT_TYPE_LATEST
        ),
    )
