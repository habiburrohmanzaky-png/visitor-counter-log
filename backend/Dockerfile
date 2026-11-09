
FROM python:3.12-alpine

ARG APP_VERSION=1.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    DATA_DIR=/var/lib/backend_data \
    DATA_FILE=visitor_logs.json \
    APP_VERSION=${APP_VERSION}

WORKDIR /app

RUN addgroup -S app && adduser -S -G app app \
    && mkdir -p /var/lib/backend_data \
    && chown -R app:app /var/lib/backend_data

COPY --chown=app:app app.py .

USER app

VOLUME ["/var/lib/backend_data"]

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"

CMD ["python", "app.py"]
