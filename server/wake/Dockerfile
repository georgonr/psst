# PSST verification wake-up (DECISIONS D68) — nginx mirrors m.key.verification.request here, we push via Sygnal
FROM docker.io/library/python:3.13-slim
RUN useradd -r -u 10001 -d /app psst && mkdir -p /app
WORKDIR /app
COPY app.py .
USER psst
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["python", "-u", "app.py"]
