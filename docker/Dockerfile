FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Market analyzer (local package)
COPY ../market_analyzer /opt/market_analyzer
RUN pip install --no-deps -e /opt/market_analyzer

# App code
COPY . .
RUN pip install -e .

# Frontend (pre-built)
COPY frontend/dist /app/frontend/dist

# Default: run API server
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "trading_cotrader.web.approval_api:create_approval_app", "--host", "0.0.0.0", "--port", "8080", "--factory"]
