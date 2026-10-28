FROM node:22-alpine AS frontend-build
WORKDIR /frontend
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
ENV VITE_API_URL=/api/v1
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY backend ./backend
COPY generator ./generator
COPY --from=frontend-build /frontend/dist ./frontend_dist
RUN pip install --no-cache-dir .
EXPOSE 10000
CMD ["sh", "-c", "alembic upgrade head && python -m generator.generate --profile starter --seed 20261022 && python -m backend.seed --with-starter-data && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
