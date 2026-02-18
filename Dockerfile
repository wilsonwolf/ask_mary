FROM node:20-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ src/
COPY comms_templates/ comms_templates/
COPY alembic/ alembic/
COPY alembic.ini ./

# Copy built frontend from first stage
COPY --from=frontend /frontend/dist frontend/dist/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
