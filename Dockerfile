FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency specifications first for optimal layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv sync (creates virtualenv (.venv) automatically)
RUN uv sync --frozen --no-dev

# Expose FastAPI port
EXPOSE 8000

# Run uvicorn using uv run inside the virtual environment with live reload
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]