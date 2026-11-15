# PSST admin (správa pozvánok a členov) — https://<APP_DOMAIN>/admin, DECISIONS D56
FROM docker.io/library/python:3.13-slim
RUN useradd -r -u 10001 -d /app psst && mkdir -p /app /data && chown psst /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
USER psst
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/admin/healthz')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "172.30.0.0/24", "--no-server-header"]
