# --- frontend (React/Vite) ---
FROM node:22-alpine AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# --- panel (Flask) ---
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY --from=frontend /fe/dist app/static/spa
COPY migrations migrations
ENV PYTHONUNBUFFERED=1 FLASK_APP=app
