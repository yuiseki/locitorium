FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src
RUN uv sync --frozen

ENV PYTHONUNBUFFERED=1

EXPOSE 8010

CMD ["uv", "run", "uvicorn", "locitorium.api.app:app", "--host", "0.0.0.0", "--port", "8010"]
