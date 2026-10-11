# Image for the API. The tests are copied in too, so the same image runs pytest against
# the compose database (docker compose run --rm app pytest).
FROM python:3.12-slim

WORKDIR /code

# Dependencies first, so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY tests/ tests/

# 0.0.0.0 so the server is reachable from outside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
