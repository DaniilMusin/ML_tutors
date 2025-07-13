# Анализ MVP платформы репетиторов - Текущее состояние

## ✅ Реализовано

### 1. База данных и модели
- ✅ Модели Django созданы и настроены:
  - `User` (пользователи)
  - `TutorProfile` (профили репетиторов)
  - `Subject` (предметы)
  - `Order` (заказы студентов)
  - `Application` (отклики репетиторов)
  - `Booking` (бронирования)
  - `TutorReview` (отзывы)
  - `EmbeddingCache` (кэш эмбеддингов)

- ✅ Миграции созданы и готовы к применению
- ✅ Поддержка pgvector для векторных операций

### 2. REST API (Django REST Framework)
- ✅ Сериализаторы созданы для всех основных моделей:
  - `OrderSerializer`, `ApplicationSerializer`, `BookingSerializer`
  - `TutorProfileSerializer`, `SubjectSerializer`, `TutorReviewSerializer`

- ✅ ViewSets реализованы с базовым CRUD функционалом:
  - `OrderViewSet` - управление заказами
  - `ApplicationViewSet` - управление откликами
  - `BookingViewSet` - управление бронированиями
  - `TutorProfileViewSet` - управление профилями репетиторов
  - `SubjectViewSet` - просмотр предметов
  - `TutorReviewViewSet` - управление отзывами

- ✅ Дополнительные эндпоинты:
  - `GET /api/orders/my_orders/` - заказы пользователя
  - `POST /api/orders/{id}/close/` - закрытие заказа
  - `GET /api/applications/my_applications/` - отклики пользователя
  - `POST /api/applications/{id}/choose/` - выбор отклика
  - `GET /api/tutors/profiles/my_profile/` - профиль репетитора
  - `POST /api/tutors/profiles/{id}/add_review/` - добавление отзыва
  - `GET /api/tutors/profiles/search/` - поиск репетиторов

### 3. ML компонент (начальная реализация)
- ✅ Базовый класс `TutorRanker` с LightGBM
- ✅ Извлечение признаков для сопоставления заказ-репетитор
- ✅ Функция `get_top_k()` для получения топ-K репетиторов
- ✅ Подготовка к обучению на исторических данных

### 4. Инфраструктура
- ✅ Настройки Django настроены для разработки и продакшена
- ✅ Поддержка PostgreSQL с pgvector
- ✅ Celery для фоновых задач
- ✅ Channels для WebSockets
- ✅ Prometheus для мониторинга
- ✅ CORS настроен
- ✅ JWT аутентификация

## ⚠️ Требует доработки для MVP

### 1. Платежная система (Stripe)
**Статус**: Не реализовано  
**Приоритет**: Высокий

Необходимо создать:
```python
# apps/payments/models.py
class StripeCheckoutSession(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    stripe_session_id = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

# apps/payments/views.py  
class StripeCheckoutSessionView(CreateAPIView):
    def post(self, request):
        # Создание Stripe checkout session
        pass

class StripeWebhookView(APIView):
    def post(self, request):
        # Обработка webhook от Stripe
        pass
```

### 2. WebSockets для real-time уведомлений
**Статус**: Частично настроено  
**Приоритет**: Средний

Создать:
```python
# tutors_platform/routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from apps.orders.consumers import OrderConsumer

application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/orders/<int:order_id>/', OrderConsumer.as_asgi()),
        ])
    ),
})

# apps/orders/consumers.py
class OrderConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        # Обработка сообщений
        pass
```

### 3. ML переобучение (Celery Task)
**Статус**: Частично реализовано  
**Приоритет**: Средний

Создать:
```python
# ml/tasks.py
from celery import shared_task
from .ranker import get_ranker

@shared_task
def retrain_ranker():
    """Переобучение ML модели еженедельно"""
    ranker = get_ranker()
    metrics = ranker.train()
    return metrics

# tutors_platform/celery.py - добавить периодическую задачу
```

### 4. OpenAI интеграция для re-ranking
**Статус**: Не реализовано  
**Приоритет**: Низкий (для MVP)

```python
# ml/openai_rerank.py
import openai
from django.conf import settings

def gpt_rerank(order_description: str, tutors: List[dict]) -> List[dict]:
    """Переранжирование с помощью GPT-4o-mini"""
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    # Реализация
    pass
```

### 5. Frontend шаблоны
**Статус**: Минимально  
**Приоритет**: Высокий для демо

Создать базовые шаблоны:
- `templates/orders/list.html` - список заказов
- `templates/orders/detail.html` - детали заказа
- `templates/tutors/list.html` - список репетиторов
- `templates/orders/ai_match_modal.html` - модал с AI подбором

### 6. Тестирование
**Статус**: Не реализовано  
**Приоритет**: Средний

```python
# tests/test_api.py
class OrderAPITestCase(APITestCase):
    def test_create_order(self):
        pass
    
    def test_ai_matching(self):
        pass
```

### 7. Фикстуры с демо-данными
**Статус**: Частично  
**Приоритет**: Высокий для демо

Создать `fixtures/demo_data.json` с:
- 50+ репетиторов разных предметов
- 20+ заказов
- Тестовые отклики и бронирования

## 🚀 Быстрый запуск MVP (1-2 спринта)

### Приоритет 1 (критически важно):
1. **Stripe интеграция** - базовая оплата
2. **Демо-данные** - фикстуры для презентации
3. **Базовые frontend шаблоны** - для демонстрации workflow

### Приоритет 2 (желательно):
4. **WebSockets** - live-уведомления о новых откликах
5. **ML переобучение** - автоматическое улучшение
6. **Базовые тесты** - API endpoints

### Приоритет 3 (можно отложить):
7. **OpenAI re-ranking** - улучшение качества подбора
8. **E2E тесты** - полный workflow
9. **PWA** - мобильная версия

## 📝 Команды для запуска

```bash
# Создание и применение миграций
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Загрузка демо-данных (когда будут созданы)
python manage.py loaddata fixtures/demo_data.json

# Запуск сервера
python manage.py runserver

# Запуск Celery (в отдельном терминале)
celery -A tutors_platform worker -l info

# Запуск Redis (в Docker)
docker run -d -p 6379:6379 redis:alpine
```

## 🔗 API Endpoints (уже работают)

### Заказы
- `GET /api/orders/orders/` - список заказов
- `POST /api/orders/orders/` - создание заказа
- `GET /api/orders/orders/my_orders/` - мои заказы
- `POST /api/orders/orders/{id}/close/` - закрытие заказа

### Репетиторы
- `GET /api/tutors/profiles/` - список репетиторов
- `POST /api/tutors/profiles/` - создание профиля
- `GET /api/tutors/profiles/search/?q=математика` - поиск
- `GET /api/tutors/subjects/` - список предметов

### Отклики
- `POST /api/orders/applications/` - отклик на заказ
- `GET /api/orders/applications/my_applications/` - мои отклики
- `POST /api/orders/applications/{id}/choose/` - выбрать отклик

## 💡 Заключение

Проект имеет **solid foundation** для MVP:
- ✅ Полная архитектура БД
- ✅ Рабочее API с основным функционалом
- ✅ Базовый ML компонент
- ✅ Настроенная инфраструктура

**Критический path для демо**: Платежи + демо-данные + простой UI = готовый MVP за 1-2 недели.

**Для production**: + WebSockets + тесты + мониторинг = запуск через месяц.