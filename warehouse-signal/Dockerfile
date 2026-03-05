FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

EXPOSE 8000

CMD uvicorn warehouse_signal.api.server:app --host 0.0.0.0 --port ${PORT:-8000}
