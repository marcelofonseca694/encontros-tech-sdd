FROM python:3.13-slim

ARG SERVICE_VERSION
RUN test -n "$SERVICE_VERSION" || (echo "SERVICE_VERSION build arg is required" >&2 && exit 1)
ENV SERVICE_VERSION=$SERVICE_VERSION

ENV PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "gunicorn -w 1 -b 0.0.0.0:${PORT} main:app"]
