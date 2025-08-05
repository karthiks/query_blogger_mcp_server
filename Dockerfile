# Use a slim Python base image for a smaller footprint.
# Using 3.10-slim-buster to match your pyenv version, adjust as needed (e.g., 3.11-slim-bookworm for newer Python).
FROM python:3.13.5-slim

# Set the working directory inside the container.
WORKDIR /app

# Prevent Python from writing .pyc files to disk and ensure output is sent to stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy pyproject.toml first. Docker will use this to install dependencies.
# If this file doesn't change, Docker won't re-run the pip install command.
# COPY pyproject.toml README.md ./
COPY . .

# Install production dependencies directly from pyproject.toml.
# The 'pip install .' command reads dependencies from the [project] table in pyproject.toml.
# --no-cache-dir: Prevents pip from storing downloaded packages in a cache.
# --upgrade pip: Ensures pip itself is up-to-date.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy the entire source code (the 'src' directory) into the container.
# This assumes your project structure is:
# /project_root
# ├── pyproject.toml
# └── src/
#     └── query_blogger_mcp_server/
#         ├── __init__.py
#         ├── blogger_api_client.py
#         ├── config.py
#         └── server.py
COPY src/ /app/src/

# Expose the port Uvicorn will listen on. This should match UVICORN_PORT in config.py.
EXPOSE 8000

# Define the command to run your application using Uvicorn.
# 'query_blogger_mcp_server.server' refers to the server.py module inside your package.
# 'app' is the FastAPI application object exposed by your FastMCP instance.
# --host 0.0.0.0: Makes the server accessible from outside the container.
# --port 8000: Specifies the port Uvicorn listens on (matches EXPOSE and config.py default).
# --workers 1: For a simple setup, 1 worker is fine. For production, consider increasing this
#              based on CPU cores (e.g., --workers $(nproc) or a fixed number).
#              Using a process manager like Gunicorn with Uvicorn workers is common for
#              more robust production deployments, but this is a good starting point.
CMD ["uvicorn", "query_blogger_mcp_server.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
