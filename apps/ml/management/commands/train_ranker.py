from django.core.management.base import BaseCommand
from django.conf import settings
from apps.ml.services import AIMatchingService
from apps.orders.models import Order
from apps.tutors.models import TutorProfile
import os


class Command(BaseCommand):
    help = 'Обучает модель ранжирования репетиторов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-data',
            action='store_true',
            help='Проверить доступность данных для обучения'
        )

    def handle(self, *args, **options):
        if options['check_data']:
            self.check_training_data()
        else:
            self.train_model()

    def check_training_data(self):
        """Проверяет доступность данных для обучения."""
        self.stdout.write("Проверка данных для обучения...")
        
        # Проверяем количество заказов
        orders_count = Order.objects.count()
        self.stdout.write(f"Всего заказов: {orders_count}")
        
        # Проверяем количество откликов
        orders_with_apps = Order.objects.filter(applications__isnull=False).count()
        self.stdout.write(f"Заказов с откликами: {orders_with_apps}")
        
        # Проверяем количество репетиторов
        tutors_count = TutorProfile.objects.count()
        self.stdout.write(f"Всего репетиторов: {tutors_count}")
        
        # Проверяем количество выбранных откликов
        chosen_apps = Order.objects.filter(applications__is_chosen=True).count()
        self.stdout.write(f"Выбранных откликов: {chosen_apps}")
        
        if orders_with_apps == 0:
            self.stdout.write(
                self.style.WARNING(
                    "Нет данных для обучения! Создайте тестовые данные с помощью команды create_test_data."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Данных достаточно для обучения модели."
                )
            )

    def train_model(self):
        """Обучает модель ранжирования."""
        self.stdout.write("Начинаем обучение модели...")
        
        try:
            # Создаем сервис AI
            ai_service = AIMatchingService()
            
            # Проверяем наличие данных
            orders_count = Order.objects.filter(applications__isnull=False).count()
            if orders_count == 0:
                self.stdout.write(
                    self.style.ERROR(
                        "Нет данных для обучения! Запустите команду с флагом --check-data."
                    )
                )
                return
            
            # Здесь должна быть логика обучения модели
            # Пока что просто выводим сообщение
            self.stdout.write(
                self.style.SUCCESS(
                    "Модель обучена успешно! (заглушка - полная реализация в ml/scripts/train_ranker.py)"
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Ошибка при обучении модели: {e}")
            )