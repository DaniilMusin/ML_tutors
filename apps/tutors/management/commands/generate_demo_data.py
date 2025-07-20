from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from decimal import Decimal
import random
from datetime import timedelta

from apps.tutors.models import TutorProfile, Subject, TutorReview
from apps.orders.models import Order
from apps.ml.services import AIMatchingService

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate demo data for tutors platform'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_service = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--tutors',
            type=int,
            default=50,
            help='Number of tutors to create'
        )
        parser.add_argument(
            '--orders', 
            type=int,
            default=30,
            help='Number of orders to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before generating new'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing demo data...')
            self.clear_demo_data()
        
        # Initialize AI service for vector generation
        try:
            self.ai_service = AIMatchingService()
            self.stdout.write('AI service initialized for vector generation')
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not initialize AI service: {e}. Vectors will not be generated.')
            )
        
        with transaction.atomic():
            self.stdout.write('Creating subjects...')
            subjects = self.create_subjects()
            
            self.stdout.write(f'Creating {options["tutors"]} tutors...')
            tutors = self.create_tutors(options['tutors'], subjects)
            
            if self.ai_service:
                self.stdout.write('Generating vector embeddings for tutors...')
                self.generate_tutor_vectors(tutors)
            
            self.stdout.write(f'Creating {options["orders"]} orders...')
            self.create_orders(options['orders'], subjects)
            
            self.stdout.write('Creating reviews...')
            self.create_reviews(tutors)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated demo data: {options["tutors"]} tutors, {options["orders"]} orders'
            )
        )

    def clear_demo_data(self):
        """Clear existing demo data."""
        TutorReview.objects.filter(tutor__user__username__startswith='demo_tutor').delete()
        Order.objects.filter(student__username__startswith='demo_student').delete()
        TutorProfile.objects.filter(user__username__startswith='demo_tutor').delete()
        User.objects.filter(username__startswith='demo_').delete()

    def create_subjects(self):
        """Create or get subjects."""
        subjects_data = [
            ('Математика', 'Точные науки', 'calculator'),
            ('Физика', 'Точные науки', 'atom'),
            ('Химия', 'Точные науки', 'flask'),
            ('Биология', 'Естественные науки', 'dna'),
            ('Английский язык', 'Иностранные языки', 'language'),
            ('Немецкий язык', 'Иностранные языки', 'language'),
            ('Русский язык', 'Гуманитарные науки', 'book'),
            ('Литература', 'Гуманитарные науки', 'book-open'),
            ('История', 'Гуманитарные науки', 'clock'),
            ('Обществознание', 'Гуманитарные науки', 'users'),
            ('География', 'Естественные науки', 'globe'),
            ('Информатика', 'Точные науки', 'computer'),
            ('Экономика', 'Социальные науки', 'trending-up'),
            ('Философия', 'Гуманитарные науки', 'brain'),
        ]
        
        subjects = []
        for name, category, icon in subjects_data:
            subject, created = Subject.objects.get_or_create(
                name=name,
                defaults={
                    'category': category,
                    'icon': icon,
                    'description': f'Преподавание предмета {name}'
                }
            )
            subjects.append(subject)
        
        return subjects

    def create_tutors(self, count, subjects):
        """Create demo tutors."""
        cities = [
            ('Москва', 'Московская область'),
            ('Санкт-Петербург', 'Ленинградская область'),
            ('Новосибирск', 'Новосибирская область'),
            ('Екатеринбург', 'Свердловская область'),
            ('Казань', 'Республика Татарстан'),
            ('Нижний Новгород', 'Нижегородская область'),
            ('Челябинск', 'Челябинская область'),
            ('Самара', 'Самарская область'),
            ('Ростов-на-Дону', 'Ростовская область'),
            ('Уфа', 'Республика Башкортостан'),
        ]
        
        first_names = [
            'Александр', 'Дмитрий', 'Максим', 'Сергей', 'Андрей', 'Алексей', 'Артём', 'Илья', 'Кирилл', 'Михаил',
            'Анна', 'Мария', 'Елена', 'Ольга', 'Екатерина', 'Татьяна', 'Наталья', 'Ирина', 'Юлия', 'Виктория'
        ]
        
        last_names = [
            'Иванов', 'Петров', 'Сидоров', 'Козлов', 'Волков', 'Смирнов', 'Попов', 'Лебедев', 'Новиков', 'Морозов',
            'Иванова', 'Петрова', 'Сидорова', 'Козлова', 'Волкова', 'Смирнова', 
            'Попова', 'Лебедева', 'Новикова', 'Морозова'
        ]
        
        tutors = []
        for i in range(count):
            # Create user
            username = f'demo_tutor_{i+1}'
            email = f'tutor{i+1}@demo.com'
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password='demo123'
            )
            
            # Create tutor profile
            city, region = random.choice(cities)
            experience = random.randint(1, 20)
            hourly_rate = Decimal(str(random.randint(800, 5000)))
            rating = round(random.uniform(3.5, 5.0), 1)
            rating_count = random.randint(5, 100)
            
            bio_templates = [
                f"Опытный преподаватель с {experience} годами стажа. Помогаю студентам достигать высоких результатов.",
                f"Кандидат наук, {experience} лет преподавательской деятельности. "
                f"Индивидуальный подход к каждому ученику.",
                f"Профессиональный репетитор. За {experience} лет работы подготовил более 200 учеников.",
                f"Преподаватель высшей категории. Специализируюсь на подготовке к экзаменам и олимпиадам.",
                f"Молодой и энергичный преподаватель с {experience} годами опыта. Современные методики обучения."
            ]
            
            tutor_profile = TutorProfile.objects.create(
                user=user,
                bio=random.choice(bio_templates),
                experience_years=experience,
                hourly_rate=hourly_rate,
                rating=rating,
                rating_count=rating_count,
                is_premium=random.choice([True, False]),
                is_verified=random.choice([True, True, True, False]),  # 75% verified
                city=city,
                region=region,
                availability={
                    'monday': ['09:00-18:00'] if random.choice([True, False]) else [],
                    'tuesday': ['09:00-18:00'] if random.choice([True, False]) else [],
                    'wednesday': ['09:00-18:00'] if random.choice([True, False]) else [],
                    'thursday': ['09:00-18:00'] if random.choice([True, False]) else [],
                    'friday': ['09:00-18:00'] if random.choice([True, False]) else [],
                    'saturday': ['10:00-16:00'] if random.choice([True, False]) else [],
                    'sunday': ['10:00-16:00'] if random.choice([True, False]) else [],
                }
            )
            
            if tutor_profile.is_premium:
                tutor_profile.premium_expires_at = timezone.now() + timedelta(days=random.randint(30, 365))
                tutor_profile.save()
            
            # Assign random subjects (1-3 per tutor)
            tutor_subjects = random.sample(subjects, random.randint(1, 3))
            tutor_profile.subjects.set(tutor_subjects)
            
            tutors.append(tutor_profile)
        
        return tutors

    def create_orders(self, count, subjects):
        """Create demo orders."""
        # Create some demo students
        students = []
        for i in range(min(count // 2, 20)):  # Max 20 students
            username = f'demo_student_{i+1}'
            email = f'student{i+1}@demo.com'
            
            student = User.objects.create_user(
                username=username,
                email=email,
                first_name=f'Студент{i+1}',
                last_name='Демо',
                password='demo123'
            )
            students.append(student)
        
        order_titles = [
            'Подготовка к ЕГЭ',
            'Подготовка к ОГЭ', 
            'Помощь с домашними заданиями',
            'Подготовка к контрольной работе',
            'Изучение основ предмета',
            'Подготовка к олимпиаде',
            'Подготовка к поступлению в вуз',
            'Повышение успеваемости',
            'Интенсивный курс',
            'Разговорная практика'
        ]
        
        descriptions = [
            'Нужна качественная подготовка с опытным преподавателем',
            'Ищу репетитора для систематических занятий',
            'Требуется помощь в освоении сложных тем',
            'Хочу повысить уровень знаний по предмету',
            'Нужна подготовка к важному экзамену'
        ]
        
        for i in range(count):
            student = random.choice(students)
            subject = random.choice(subjects)
            
            budget_min = random.randint(1000, 3000)
            budget_max = budget_min + random.randint(500, 2000)
            
            Order.objects.create(
                student=student,
                subject=subject,
                title=f"{random.choice(order_titles)} по предмету {subject.name}",
                description=random.choice(descriptions),
                goal_text=f"Достичь высоких результатов по предмету {subject.name}",
                budget_min=budget_min,
                budget_max=budget_max,
                format_online=random.choice([True, False]),
                format_offline=random.choice([True, False]),
                city=random.choice(['Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург']),
                region=random.choice(['Московская область', 'Ленинградская область']),
                status=random.choice(['active', 'active', 'active', 'completed', 'cancelled']),
                created_at=timezone.now() - timedelta(days=random.randint(0, 90))
            )

    def create_reviews(self, tutors):
        """Create demo reviews for tutors."""
        review_texts = [
            'Отличный преподаватель! Объясняет очень понятно.',
            'Благодаря этому репетитору значительно повысил свои оценки.',
            'Профессиональный подход, рекомендую всем!',
            'Очень терпеливый и внимательный преподаватель.',
            'Помог подготовиться к экзамену на отлично!',
            'Индивидуальный подход к каждому ученику.',
            'Занятия проходят интересно и продуктивно.',
            'Результат превзошел все ожидания!',
            'Лучший репетитор, с которым я занимался.',
            'Всегда готов помочь и ответить на вопросы.'
        ]
        
        # Create demo students for reviews if they don't exist
        review_students = []
        for i in range(10):
            username = f'demo_review_student_{i+1}'
            if not User.objects.filter(username=username).exists():
                student = User.objects.create_user(
                    username=username,
                    email=f'review_student{i+1}@demo.com',
                    first_name=f'Ученик{i+1}',
                    last_name='Отзыв',
                    password='demo123'
                )
                review_students.append(student)
        
        # Add reviews to random tutors
        for tutor in random.sample(tutors, min(len(tutors), 30)):
            num_reviews = random.randint(1, 5)
            for _ in range(num_reviews):
                if review_students:
                    student = random.choice(review_students)
                    try:
                        TutorReview.objects.create(
                            tutor=tutor,
                            student=student,
                            rating=random.randint(3, 5),
                            review_text=random.choice(review_texts),
                            created_at=timezone.now() - timedelta(days=random.randint(0, 365))
                        )
                    except (IntegrityError, ValidationError) as e:
                        # Skip if review already exists (unique constraint)
                        self.stdout.write(
                            self.style.WARNING(f'Skipping duplicate review for tutor {tutor.id}: {e}')
                        )
                    except Exception as e:
                        # Log unexpected errors but continue processing
                        self.stdout.write(
                            self.style.ERROR(f'Unexpected error creating review for tutor {tutor.id}: {e}')
                        )

    def generate_tutor_vectors(self, tutors):
        """Generate vector embeddings for tutors based on their bio and subjects."""
        for i, tutor in enumerate(tutors):
            try:
                # Create text representation for embedding
                subjects_text = ', '.join([s.name for s in tutor.subjects.all()])
                bio_text = tutor.bio if tutor.bio else "Репетитор без описания"
                
                # Combine bio with subjects and experience info
                full_text = (
                    f"{bio_text}. Предметы: {subjects_text}. "
                    f"Опыт: {tutor.experience_years} лет. "
                    f"Стоимость: {tutor.hourly_rate} руб/час."
                )
                
                # Get embedding
                embedding = self.ai_service._get_embedding(full_text)
                
                if embedding:
                    tutor.vector = embedding
                    tutor.save()
                    
                    if (i + 1) % 10 == 0:
                        self.stdout.write(f'Generated vectors for {i + 1}/{len(tutors)} tutors')
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Failed to generate vector for tutor {tutor.id}')
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error generating vector for tutor {tutor.id}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Vector generation completed for {len(tutors)} tutors')
        )
