# The relevance scorer image: ONNX Runtime and FastAPI, no training code. The model and its thresholds are baked in
# by the release pipeline (artefacts/ holds what the gate promoted).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements-serving.txt .
RUN pip install --no-cache-dir -r requirements-serving.txt
COPY src/screening/__init__.py src/screening/__init__.py
COPY src/screening/serving src/screening/serving
COPY artefacts /models
RUN useradd --uid 10001 --create-home app
USER 10001
EXPOSE 8080
CMD ["uvicorn", "screening.serving.app:app", "--host", "0.0.0.0", "--port", "8080"]
