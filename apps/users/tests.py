from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class UserModelTest(TestCase):
    """Тесты для модели User."""

    def setUp(self):
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'role': 'student'
        }

    def test_create_user(self):
        """Тест создания пользователя."""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.role, 'student')
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_tutor)
        self.assertFalse(user.is_verified)

    def test_create_tutor(self):
        """Тест создания репетитора."""
        tutor_data = self.user_data.copy()
        tutor_data['role'] = 'tutor'
        
        user = User.objects.create_user(**tutor_data)
        
        self.assertEqual(user.role, 'tutor')
        self.assertTrue(user.is_tutor)
        self.assertFalse(user.is_student)

    def test_user_str_representation(self):
        """Тест строкового представления пользователя."""
        user = User.objects.create_user(**self.user_data)
        expected_str = f"{user.username} ({user.role})"
        
        self.assertEqual(str(user), expected_str)


class UserAPITest(APITestCase):
    """Тесты для API пользователей."""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.profile_url = reverse('profile')

    def test_user_registration(self):
        """Тест регистрации пользователя."""
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'role': 'student',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # Проверяем, что пользователь создался в базе
        user = User.objects.get(username='newuser')
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.role, 'student')

    def test_user_registration_password_mismatch(self):
        """Тест регистрации с несовпадающими паролями."""
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'password_confirm': 'different123',
            'role': 'student'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login(self):
        """Тест входа пользователя."""
        # Создаем пользователя
        user = User.objects.create_user(
            username='loginuser',
            email='login@example.com',
            password='loginpass123',
            role='student'
        )
        
        # Пытаемся войти
        data = {
            'username': 'loginuser',
            'password': 'loginpass123'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_user_profile_authenticated(self):
        """Тест получения профиля авторизованного пользователя."""
        # Создаем пользователя
        user = User.objects.create_user(
            username='profileuser',
            email='profile@example.com',
            password='profilepass123',
            role='student'
        )
        
        # Авторизуемся
        self.client.force_authenticate(user=user)
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'profileuser')
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertEqual(response.data['role'], 'student')

    def test_user_profile_unauthenticated(self):
        """Тест получения профиля неавторизованного пользователя."""
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_profile_update(self):
        """Тест обновления профиля пользователя."""
        # Создаем пользователя
        user = User.objects.create_user(
            username='updateuser',
            email='update@example.com',
            password='updatepass123',
            role='student'
        )
        
        # Авторизуемся
        self.client.force_authenticate(user=user)
        
        # Обновляем профиль
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '+7999123456'
        }
        
        response = self.client.patch(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')
        
        # Проверяем, что данные сохранились в базе
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Updated')
        self.assertEqual(user.last_name, 'Name')
        self.assertEqual(user.phone, '+7999123456')