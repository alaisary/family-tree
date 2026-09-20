# ---- Build stage: compile Tailwind CSS ----
FROM node:20-alpine AS css-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tailwind.config.js ./
COPY tree/static/tree/css/input.css ./tree/static/tree/css/input.css
COPY tree/templates/ ./tree/templates/
RUN npm run build:css

# ---- Runtime stage: Django + Gunicorn ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built CSS from build stage
COPY --from=css-build /app/tree/static/tree/css/app.css ./tree/static/tree/css/app.css

# Collect static files
RUN SECRET_KEY=build-time-placeholder DEBUG=False ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "familytree_project.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
