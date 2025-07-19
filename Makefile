.PHONY: help install install-dev test lint format clean migrate makemigrations runserver shell collectstatic

help: ## Показать справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
	pip install -r requirements.txt

install-dev: ## Установить зависимости для разработки
	pip install -r requirements-dev.txt

test: ## Запустить тесты
	python manage.py test

test-coverage: ## Запустить тесты с покрытием
	pytest --cov=apps --cov-report=html --cov-report=term-missing

lint: ## Проверить код линтерами
	flake8 apps tutors_platform
	pylint apps tutors_platform
	bandit -r apps tutors_platform

format: ## Отформатировать код
	black apps tutors_platform
	isort apps tutors_platform

format-check: ## Проверить форматирование кода
	black --check apps tutors_platform
	isort --check-only apps tutors_platform

clean: ## Очистить кэш и временные файлы
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov .pytest_cache

migrate: ## Применить миграции
	python manage.py migrate

makemigrations: ## Создать миграции
	python manage.py makemigrations

runserver: ## Запустить сервер разработки
	python manage.py runserver

shell: ## Запустить Django shell
	python manage.py shell

collectstatic: ## Собрать статические файлы
	python manage.py collectstatic --noinput

superuser: ## Создать суперпользователя
	python manage.py createsuperuser

demo-data: ## Создать демо данные
	python manage.py generate_demo_data

train-model: ## Обучить ML модель
	python manage.py train_ranker

celery-worker: ## Запустить Celery worker
	celery -A tutors_platform worker -l info

celery-beat: ## Запустить Celery beat
	celery -A tutors_platform beat -l info

check: ## Проверить проект Django
	python manage.py check

security-check: ## Проверить безопасность
	safety check
	bandit -r apps tutors_platform

docker-build: ## Собрать Docker образ
	docker build -t tutors-platform .

docker-run: ## Запустить с Docker Compose
	docker-compose up -d

docker-stop: ## Остановить Docker Compose
	docker-compose down

docker-logs: ## Показать логи Docker
	docker-compose logs -f

fix-style: ## Исправить стилистические ошибки
	python fix_code_style.py

pre-commit: ## Запустить pre-commit hooks
	pre-commit run --all-files

setup-dev: install-dev ## Настройка окружения для разработки
	pre-commit install
	python manage.py migrate
	python manage.py collectstatic --noinput

production-check: ## Проверка готовности к продакшену
	python manage.py check --deploy
	python manage.py test
	flake8 apps tutors_platform
	bandit -r apps tutors_platform
	safety check