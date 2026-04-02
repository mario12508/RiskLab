FROM python:3.10-slim

WORKDIR /usr/src/app

COPY ./requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/usr/src/app/web

RUN sh -c "\
  cd web && python manage.py collectstatic --noinput && cd .. \
"

CMD ["sh", "-c", "\
  python web/manage.py migrate --noinput && \
  python web/manage.py loaddata web/fixtures/*.json 2>/dev/null && \
  python web/manage.py fill_history --days 81 2>/dev/null && \
  echo \"from django.contrib.auth import get_user_model; U = get_user_model(); \
  U.objects.create_superuser('admin', 'admin@example.com', 'ChangeMe123!') \
  if not U.objects.filter(username='admin').exists() else None\" \
  | python web/manage.py shell && \
  gunicorn web.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --max-requests 200 \
    --max-requests-jitter 50 \
    --graceful-timeout 30 \
    --preload \
    --log-level info \
    --access-logfile - \
"]