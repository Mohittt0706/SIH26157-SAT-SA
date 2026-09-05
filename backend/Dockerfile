# SAT-SA backend — FastAPI + SQLite, fully offline at runtime.
# Build needs network access (pip install); the running container needs none.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# database.py resolves the SQLite path to <backend root>/data/satsa.db —
# i.e. /app/data/satsa.db here. Create it so the named volume below has
# somewhere to mount even before the app writes to it.
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
