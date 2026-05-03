web: gunicorn setup.wsgi --bind 0.0.0.0:$PORT --log-file - --workers 2 --timeout 120
release: python manage.py collectstatic --noinput && python manage.py migrate --noinput
