FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY . .
# Collect CMS assets at build time so waking the demo only starts Gunicorn.
RUN SECRET_KEY=build-only DATABASE_URL=sqlite:///:memory: TESTING=True python manage.py collectstatic --noinput
RUN useradd --create-home app && chown -R app:app /app
USER app
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --access-logfile -"]
