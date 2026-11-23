FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# --proxy-headers: trust X-Forwarded-For only from FORWARDED_ALLOW_IPS (uvicorn reads that variable;
#   default 127.0.0.1,::1). Set it to the hosting proxy's address or network. Never "*":
#   then uvicorn uses the left-most X-Forwarded-For entry, which clients can forge.
# --no-server-header: don't announce the server software (OWASP HTTP Headers Cheat Sheet).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --no-server-header"]
