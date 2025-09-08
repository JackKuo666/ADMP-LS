# syntax=docker/dockerfile:1.5

# Use Astral's uv image with Python 3.11 for fast, reproducible installs
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim


RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main contrib non-free" > /etc/apt/sources.list.d/aliyun.list
RUN echo "deb-src http://mirrors.aliyun.com/debian/ bookworm main contrib non-free" >> /etc/apt/sources.list.d/aliyun.list

WORKDIR /app

# Ensure Python behaves well in containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy project metadata first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install only production dependencies using the lockfile
# --frozen ensures the lockfile is respected; --no-dev skips dev deps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Make the virtualenv binaries available on PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Now copy the application source
COPY . ./Review

EXPOSE 8000

# Start the FastAPI app with uvicorn
CMD ["uv", "run", "uvicorn", "Review.main:app", "--host", "0.0.0.0", "--port", "8000"]

