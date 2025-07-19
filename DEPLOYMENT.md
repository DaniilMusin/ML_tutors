# Инструкции по развертыванию в продакшен

## Подготовка к продакшену

### 1. Переменные окружения

Создайте файл `.env` с следующими переменными:

```bash
# Django
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# База данных
DATABASE_URL=postgresql://user:password@host:port/database

# Redis
REDIS_URL=redis://localhost:6379/0

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OpenAI
OPENAI_API_KEY=sk-...

# CORS
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Sentry (опционально)
SENTRY_DSN=https://...
```

### 2. Настройки безопасности

Используйте файл `tutors_platform/settings_production.py` для продакшена:

```bash
export DJANGO_SETTINGS_MODULE=tutors_platform.settings_production
```

### 3. База данных

```bash
# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser
```

### 4. Статические файлы

```bash
# Сбор статических файлов
python manage.py collectstatic --noinput

# Сжатие статических файлов
python manage.py compress
```

### 5. ML модели

```bash
# Обучение модели ранжирования
python manage.py train_ranker

# Генерация демо данных (опционально)
python manage.py generate_demo_data
```

## Развертывание с Docker

### 1. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копирование кода
COPY . .

# Сбор статических файлов
RUN python manage.py collectstatic --noinput

# Создание пользователя
RUN useradd -m -u 1000 django
RUN chown -R django:django /app
USER django

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "tutors_platform.wsgi:application"]
```

### 2. docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=tutors_platform.settings_production
    env_file:
      - .env
    depends_on:
      - db
      - redis
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=tutors_platform
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  celery:
    build: .
    command: celery -A tutors_platform worker -l info
    environment:
      - DJANGO_SETTINGS_MODULE=tutors_platform.settings_production
    env_file:
      - .env
    depends_on:
      - db
      - redis

  celery-beat:
    build: .
    command: celery -A tutors_platform beat -l info
    environment:
      - DJANGO_SETTINGS_MODULE=tutors_platform.settings_production
    env_file:
      - .env
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

## Развертывание с Nginx

### 1. Nginx конфигурация

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Статические файлы
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    # Django приложение
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Мониторинг и логирование

### 1. Sentry

Настройте Sentry для отслеживания ошибок:

```python
# В settings_production.py
if os.getenv('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
    )
```

### 2. Prometheus метрики

Используйте django-prometheus для метрик:

```bash
# Установка
pip install django-prometheus

# В settings.py
INSTALLED_APPS += ['django_prometheus']
MIDDLEWARE = ['django_prometheus.middleware.PrometheusBeforeMiddleware'] + MIDDLEWARE + ['django_prometheus.middleware.PrometheusAfterMiddleware']
```

### 3. Логирование

Настройте ротацию логов:

```bash
# Создание директории для логов
sudo mkdir -p /var/log/django
sudo chown django:django /var/log/django
```

## Безопасность

### 1. Firewall

```bash
# Настройка UFW
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 2. SSL сертификаты

Используйте Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 3. Регулярные обновления

```bash
# Автоматические обновления безопасности
sudo apt update && sudo apt upgrade -y
```

## Резервное копирование

### 1. База данных

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > backup_$DATE.sql
gzip backup_$DATE.sql
```

### 2. Медиа файлы

```bash
#!/bin/bash
# backup_media.sh
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf media_backup_$DATE.tar.gz media/
```

## Проверка работоспособности

### 1. Health check

```python
# В urls.py
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK")

urlpatterns += [
    path('health/', health_check, name='health_check'),
]
```

### 2. Мониторинг сервисов

```bash
# Проверка статуса сервисов
sudo systemctl status nginx
sudo systemctl status gunicorn
sudo systemctl status celery
sudo systemctl status redis
sudo systemctl status postgresql
```

## Масштабирование

### 1. Горизонтальное масштабирование

```yaml
# docker-compose.yml
services:
  web:
    deploy:
      replicas: 3
  celery:
    deploy:
      replicas: 2
```

### 2. Load balancer

Используйте Nginx как load balancer:

```nginx
upstream django {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    location / {
        proxy_pass http://django;
    }
}
```