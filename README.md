# Платформа подбора репетиторов

Современная платформа для подбора репетиторов с использованием искусственного интеллекта.

## Технологии

- **Backend**: Django 5.0 + Django REST Framework
- **WebSocket**: Django Channels 4
- **AI/ML**: LightGBM, OpenAI API, pgvector
- **Очереди**: Celery + Redis
- **База данных**: PostgreSQL 15 + pgvector
- **Frontend**: Django Templates + HTMX + Alpine.js
- **Платежи**: Stripe
- **Контейнеризация**: Docker + Docker Compose

## Функциональность

### Основные возможности
- ✅ Регистрация и авторизация пользователей (студенты и репетиторы)
- ✅ Создание заказов на поиск репетитора
- ✅ Система откликов репетиторов
- ✅ AI-подбор репетиторов с использованием ML
- ✅ Система бронирования и оплаты
- ✅ Рейтинги и отзывы
- ✅ Админ-панель для модерации
- ✅ PWA поддержка

### AI-подбор репетиторов
- Векторный поиск с использованием pgvector
- Ранжирование с помощью LightGBM
- Финальное переранжирование через OpenAI GPT
- Кэширование эмбеддингов

## Установка и запуск

### Требования
- Docker и Docker Compose
- Git

### Быстрый старт

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd tutors-platform
```

2. Создайте `.env` файл:
```bash
cp .env.example .env
```

3. Отредактируйте `.env` файл и добавьте необходимые ключи:
```
OPENAI_API_KEY=your-openai-key
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
```

4. Запустите проект:
```bash
docker-compose up --build
```

5. Выполните миграции:
```bash
docker-compose exec web python manage.py migrate
```

6. Создайте суперпользователя:
```bash
docker-compose exec web python manage.py createsuperuser
```

7. Загрузите тестовые данные:
```bash
docker-compose exec web python manage.py loaddata fixtures/initial_data.json
```

### Доступ к приложению
- Веб-приложение: http://localhost:8000
- API документация: http://localhost:8000/api/docs/
- Админ-панель: http://localhost:8000/admin/

## Архитектура

```
┌─────────────── Browser / PWA ───────────────┐
│  HTML + HTMX  ←── WebSocket ─┐               │
└──────────────────────────────┴───────────────┘
                    │ REST / WS
┌──────────── Django DRF (API) ────────────────┐
│  • /api/orders/         • /api/tutors/      │
│  • /api/ai-match/       • /api/payments/    │
│  • JWT auth             • WebSocket         │
└──────────────────────────────────────────────┘
         │ ORM
┌────────▼────────┐   Celery   ┌───────────────┐
│  PostgreSQL     │◀──────────▶│   Redis       │
│  pgvector       │            │ (broker + KV) │
└────────┬────────┘            └───────────────┘
         │ SQL + Vector Search
┌────────▼────────┐
│  AI Service     │   LightGBM + OpenAI
│  (Django app)   │   Vector embeddings
└─────────────────┘
```

## API Эндпоинты

### Аутентификация
- `POST /api/auth/register/` - Регистрация
- `POST /api/auth/login/` - Вход
- `POST /api/auth/logout/` - Выход
- `GET /api/auth/profile/` - Профиль пользователя

### Заказы
- `GET /api/orders/` - Список заказов
- `POST /api/orders/` - Создание заказа
- `GET /api/orders/{id}/` - Детали заказа
- `POST /api/orders/{id}/applications/` - Подача отклика

### Репетиторы
- `GET /api/tutors/` - Список репетиторов
- `GET /api/tutors/{id}/` - Профиль репетитора
- `PUT /api/tutors/profile/` - Обновление профиля

### AI-подбор
- `POST /api/ml/match/` - Поиск подходящих репетиторов
- `GET /api/ml/suggestions/{order_id}/` - Рекомендации для заказа

### Платежи
- `POST /api/payments/create-session/` - Создание сессии оплаты
- `POST /api/payments/webhook/` - Webhook от Stripe

## Разработка

### Структура проекта
```
├── apps/
│   ├── users/          # Пользователи и аутентификация
│   ├── tutors/         # Репетиторы и профили
│   ├── orders/         # Заказы и отклики
│   ├── ml/             # AI-подбор и ML модели
│   ├── payments/       # Интеграция с платежами
│   └── frontend/       # Веб-интерфейс
├── ml/
│   ├── models/         # Обученные ML модели
│   ├── notebooks/      # Jupyter notebooks
│   └── scripts/        # Скрипты обучения
├── templates/          # HTML шаблоны
├── static/            # Статические файлы
└── tutors_platform/   # Настройки Django
```

### Полезные команды

```bash
# Создание новой миграции
docker-compose exec web python manage.py makemigrations

# Применение миграций
docker-compose exec web python manage.py migrate

# Создание суперпользователя
docker-compose exec web python manage.py createsuperuser

# Сбор статики
docker-compose exec web python manage.py collectstatic

# Запуск тестов
docker-compose exec web python manage.py test

# Загрузка данных
docker-compose exec web python manage.py loaddata fixtures/subjects.json

# Обучение ML модели
docker-compose exec web python manage.py train_ranker
```

## Тестирование

Запуск тестов:
```bash
docker-compose exec web python -m pytest
```

Запуск с покрытием:
```bash
docker-compose exec web python -m pytest --cov=apps
```

## Мониторинг

- Логи: `docker-compose logs -f web`
- Метрики: http://localhost:8000/api/metrics/
- Celery мониторинг: `docker-compose exec celery celery -A tutors_platform flower`

## Развёртывание

### Production

1. Настройте переменные окружения для production
2. Используйте внешний PostgreSQL и Redis
3. Настройте SSL сертификаты
4. Используйте nginx как reverse proxy

### Railway / Fly.io

Проект готов для развёртывания на Railway или Fly.io - добавьте соответствующие конфигурационные файлы.

## Лицензия

MIT License