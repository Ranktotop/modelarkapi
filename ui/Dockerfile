FROM node:22-alpine AS frontend

WORKDIR /build
COPY ui/frontend/package.json ui/frontend/package-lock.json ./
RUN npm ci
COPY ui/frontend ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
COPY ui/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ui/backend/server.py ./server.py
COPY --from=frontend /build/dist ./static

RUN useradd --create-home --uid 10002 studio \
    && mkdir -p /app/data \
    && chown -R studio:studio /app
USER studio

EXPOSE 3000
CMD ["uvicorn", "server:create_app", "--factory", "--host", "0.0.0.0", "--port", "3000", "--proxy-headers"]
