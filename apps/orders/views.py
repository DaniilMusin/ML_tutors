from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Order, Application, Booking
from .serializers import (
    OrderSerializer, ApplicationSerializer, BookingSerializer
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления заказами.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Optimize with select_related for foreign keys
        queryset = Order.objects.select_related(
            'student',
            'subject'
        ).prefetch_related(
            'applications',
            'applications__tutor',
            'applications__tutor__user'
        ).all()

        # Фильтрация по параметрам
        status_filter = self.request.query_params.get('status', None)
        subject_id = self.request.query_params.get('subject', None)
        city = self.request.query_params.get('city', None)
        format_type = self.request.query_params.get('format', None)

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if city:
            queryset = queryset.filter(city__icontains=city)
        if format_type == 'online':
            queryset = queryset.filter(format_online=True)
        elif format_type == 'offline':
            queryset = queryset.filter(format_offline=True)

        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Получить заказы текущего пользователя"""
        orders = Order.objects.filter(student=request.user).select_related('subject')
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Закрыть заказ"""
        order = self.get_object()
        if order.student != request.user:
            return Response(
                {'error': 'Только автор заказа может его закрыть'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        order.status = 'completed'
        order.save()
        return Response({'status': 'Заказ закрыт'})


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления откликами на заказы.
    """
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Application.objects.select_related(
            'order', 'tutor__user', 'order__student'
        ).all()

    def perform_create(self, serializer):
        # Проверяем, что пользователь не откликается на свой же заказ
        order = serializer.validated_data['order']
        if order.student == self.request.user:
            raise serializers.ValidationError(
                "Нельзя откликаться на собственный заказ"
            )
        serializer.save()

    @action(detail=False, methods=['get'])
    def my_applications(self, request):
        """Получить отклики текущего пользователя"""
        applications = Application.objects.filter(
            tutor__user=request.user
        ).select_related('order', 'order__student')
        serializer = self.get_serializer(applications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def for_my_orders(self, request):
        """Получить отклики на заказы текущего пользователя"""
        applications = Application.objects.filter(
            order__student=request.user
        ).select_related('tutor__user', 'order')
        serializer = self.get_serializer(applications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def choose(self, request, pk=None):
        """Выбрать отклик (только автор заказа)"""
        from decimal import Decimal
        from django.db import transaction

        application = self.get_object()
        order = application.order

        if order.student != request.user:
            return Response(
                {'error': 'Только автор заказа может выбирать отклики'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate order status
        if order.status not in ['open']:
            return Response(
                {'error': 'Заказ уже закрыт или в обработке'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate application price
        if application.price <= 0:
            return Response(
                {'error': 'Некорректная цена отклика'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Lock order for update
            order = Order.objects.select_for_update().get(pk=order.pk)

            # Check if booking already exists
            if Booking.objects.filter(application__order=order).exists():
                return Response(
                    {'error': 'Для этого заказа уже создано бронирование'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Снимаем выбор с других откликов
            Application.objects.filter(order=order).update(is_chosen=False)

            # Выбираем текущий отклик
            application.is_chosen = True
            application.save(update_fields=['is_chosen'])

            # Constants for commission calculation
            PLATFORM_COMMISSION_RATE = Decimal('0.10')  # 10%

            # Calculate amounts with proper decimal precision
            platform_fee = application.price * PLATFORM_COMMISSION_RATE
            tutor_amount = application.price - platform_fee

            # Создаем бронирование
            booking = Booking.objects.create(
                application=application,
                total_amount=application.price,
                platform_fee=platform_fee,
                tutor_amount=tutor_amount,
                status='pending'
            )

            # Update order status
            order.status = 'in_progress'
            order.save(update_fields=['status'])

        return Response({
            'status': 'Отклик выбран',
            'booking_id': booking.id,
            'total_amount': str(booking.total_amount),
            'platform_fee': str(booking.platform_fee),
            'tutor_amount': str(booking.tutor_amount)
        })


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления бронированиями.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(
            Q(application__order__student=user) | Q(application__tutor__user=user)
        ).select_related('application__order__student', 'application__tutor__user')

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """Подтвердить оплату (для интеграции со Stripe)"""
        booking = self.get_object()
        
        # Здесь будет логика работы со Stripe
        booking.status = 'confirmed'
        booking.save()
        
        return Response({'status': 'Оплата подтверждена'})

    @action(detail=True, methods=['post'])
    def complete_session(self, request, pk=None):
        """Завершить сессию"""
        booking = self.get_object()
        session_notes = request.data.get('session_notes', '')
        
        booking.status = 'completed'
        booking.session_notes = session_notes
        booking.save()
        
        return Response({'status': 'Сессия завершена'})