# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS editor-build
WORKDIR /build/editor
COPY editor/package.json editor/package-lock.json ./
RUN npm ci
COPY editor/ ./
RUN npm test && npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production \
    PHOENIX_ENABLED=false \
    HOST=0.0.0.0 \
    PORT=8000

RUN addgroup --system storypointer && adduser --system --ingroup storypointer storypointer
WORKDIR /app

COPY pyproject.toml README.md requirements.txt ./
COPY story_pointer/ ./story_pointer/
COPY static/ ./static/
COPY dsl/ ./dsl/
COPY run.py ./
COPY --from=editor-build /build/editor/dist/ ./editor/dist/

RUN python -m pip install --no-cache-dir . && chown -R storypointer:storypointer /app/dsl

USER storypointer
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]
