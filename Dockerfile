# Single-container FraudLens demo: bank simulator + API (127.0.0.1 only) and
# the Next.js console on $PORT (7860 for Hugging Face Spaces).
FROM node:24-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_PUBLIC_API_BASE=/backend NEXT_PUBLIC_DEMO_MODE=1 NEXT_TELEMETRY_DISABLED=1
RUN npm run build \
 && cp -r public .next/standalone/public \
 && cp -r .next/static .next/standalone/.next/static

FROM python:3.12-slim
COPY --from=node:24-slim /usr/local/bin/node /usr/local/bin/node
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --chown=app:app fraudlens/ fraudlens/
COPY --chown=app:app scripts/ scripts/
COPY --chown=app:app --from=frontend /build/frontend/.next/standalone frontend/.next/standalone
# CF-Connecting-IP keys per-visitor limits on Render (behind Cloudflare). On a host
# without Cloudflare, clear it: visitors could otherwise set the header themselves.
ENV PORT=7860 PYTHONUNBUFFERED=1 FRAUDLENS_PUBLIC_DEMO=1 FRAUDLENS_CLIENT_IP_HEADER=cf-connecting-ip
USER app
EXPOSE 7860
CMD ["python", "scripts/serve.py"]
