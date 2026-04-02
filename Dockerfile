FROM python:3.10-slim

WORKDIR /usr/src/app

COPY ./requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/usr/src/app/web

CMD ["sh", "-c", "\
  python web/manage.py collectstatic --noinput && \
  python web/manage.py migrate --noinput && \
  python web/manage.py loaddata web/fixtures/*.json && \
  python web/manage.py fill_history && \
  echo \"from django.contrib.auth import get_user_model; U = get_user_model(); \
  U.objects.create_superuser('admin', 'admin@example.com', 'admin123') \
  if not U.objects.filter(username='admin').exists() else None\" \
  | python web/manage.py shell && \
  gunicorn web.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --preload \
    --log-level info \
    --access-logfile - \
"]