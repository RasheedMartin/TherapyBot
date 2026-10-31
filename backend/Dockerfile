FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Collect admin static files at build time (SECRET_KEY is only needed to import settings)
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

# Bake the embedding model into the image so the first request doesn't download it
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/app/.fastembed_cache')"

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

ENV PORT=8000
EXPOSE 8000

# LLM calls can take a while, so use threads and a generous timeout
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py import_articles --if-empty && python manage.py build_index --if-stale && exec gunicorn djangoProject.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --threads 4 --timeout 120 --access-logfile -"]
