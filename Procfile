web: gunicorn setup.wsgi --log-file - --workers 2 --timeout 60
release: python manage.py migrate --noinput
