#!/usr/bin/env python
"""
Скрипт для обучения модели ранжирования репетиторов.
"""

import os
import sys
import django
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import ndcg_score
import pickle
import json

# Настраиваем Django
sys.path.append('../../')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tutors_platform.settings')
django.setup()

from apps.tutors.models import TutorProfile
from apps.orders.models import Order, Application, Booking


def calculate_location_match(order, tutor):
    """Рассчитывает совпадение локации."""
    if not order.format_offline:
        return 1.0
    
    if order.city and tutor.city:
        if order.city.lower() in tutor.city.lower():
            return 1.0
        elif order.region and tutor.region:
            if order.region.lower() in tutor.region.lower():
                return 0.7
    
    return 0.3


def load_training_data():
    """
    Загружает данные для обучения модели ранжирования.
    """
    # Загружаем все заказы с откликами
    orders = Order.objects.filter(
        applications__isnull=False
    ).prefetch_related('applications__tutor', 'applications__booking')
    
    training_data = []
    
    for order in orders:
        # Для каждого заказа создаем фичи для всех откликнувшихся репетиторов
        applications = order.applications.all()
        
        for app in applications:
            tutor = app.tutor
            
            # Создаем фичи
            features = {
                'order_id': order.id,
                'tutor_id': tutor.id,
                
                # Цена
                'tutor_price': float(tutor.hourly_rate),
                'price_ratio': float(tutor.hourly_rate / max(order.budget_max, 1)),
                'in_budget': 1 if tutor.hourly_rate <= order.budget_max else 0,
                
                # Качество репетитора
                'tutor_rating': float(tutor.rating),
                'tutor_reviews': float(tutor.rating_count),
                'tutor_experience': float(tutor.experience_years),
                
                # Совпадение локации
                'location_match': calculate_location_match(order, tutor),
                
                # Целевая переменная - был ли выбран репетитор
                'was_chosen': 1 if app.is_chosen else 0,
                
                # Дополнительная метрика - была ли завершена сделка
                'was_booked': 1 if hasattr(app, 'booking') and app.booking.status == 'completed' else 0
            }
            
            training_data.append(features)
    
    return pd.DataFrame(training_data)


def train_ranker():
    """
    Обучает модель ранжирования репетиторов.
    """
    print("Загрузка данных...")
    df = load_training_data()
    
    if len(df) == 0:
        print("Нет данных для обучения!")
        return
    
    print(f"Загружено {len(df)} записей")
    print(f"Положительных примеров: {df['was_chosen'].sum()}")
    print(f"Уникальных заказов: {df['order_id'].nunique()}")
    print(f"Уникальных репетиторов: {df['tutor_id'].nunique()}")
    
    # Определяем фичи для модели
    feature_columns = [
        'tutor_price', 'price_ratio', 'in_budget',
        'tutor_rating', 'tutor_reviews', 'tutor_experience',
        'location_match'
    ]
    
    # Подготавливаем данные для LightGBM
    X = df[feature_columns].values
    y = df['was_chosen'].values
    
    # Группы для ранжирования (по заказам)
    groups = df.groupby('order_id').size().values
    
    print(f"Форма X: {X.shape}")
    print(f"Форма y: {y.shape}")
    print(f"Количество групп: {len(groups)}")
    
    # Разделяем по заказам, чтобы избежать data leakage
    unique_orders = df['order_id'].unique()
    train_orders, test_orders = train_test_split(unique_orders, test_size=0.2, random_state=42)
    
    train_mask = df['order_id'].isin(train_orders)
    test_mask = df['order_id'].isin(test_orders)
    
    X_train = X[train_mask]
    y_train = y[train_mask]
    groups_train = df[train_mask].groupby('order_id').size().values
    
    X_test = X[test_mask]
    y_test = y[test_mask]
    groups_test = df[test_mask].groupby('order_id').size().values
    
    print(f"Train: {X_train.shape[0]} samples, {len(groups_train)} groups")
    print(f"Test: {X_test.shape[0]} samples, {len(groups_test)} groups")
    
    # Создаем датасеты LightGBM
    train_data = lgb.Dataset(
        X_train, 
        label=y_train, 
        group=groups_train,
        feature_name=feature_columns
    )
    
    test_data = lgb.Dataset(
        X_test, 
        label=y_test, 
        group=groups_test,
        feature_name=feature_columns,
        reference=train_data
    )
    
    # Параметры модели
    params = {
        'objective': 'lambdarank',
        'metric': 'ndcg',
        'ndcg_eval_at': [1, 3, 5],
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': 1
    }
    
    print("Обучение модели...")
    # Обучаем модель
    model = lgb.train(
        params,
        train_data,
        valid_sets=[train_data, test_data],
        valid_names=['train', 'test'],
        num_boost_round=1000,
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)]
    )
    
    print("Обучение завершено!")
    
    # Предсказания на тестовом наборе
    y_pred = model.predict(X_test)
    
    # Группируем предсказания по заказам для расчета NDCG
    test_df = df[test_mask].copy()
    test_df['prediction'] = y_pred
    
    # Рассчитываем NDCG для каждого заказа
    ndcg_scores = []
    for order_id in test_df['order_id'].unique():
        order_data = test_df[test_df['order_id'] == order_id]
        
        if len(order_data) > 1:  # Нужно минимум 2 кандидата для ранжирования
            y_true = order_data['was_chosen'].values.reshape(1, -1)
            y_score = order_data['prediction'].values.reshape(1, -1)
            
            try:
                ndcg = ndcg_score(y_true, y_score, k=3)
                ndcg_scores.append(ndcg)
            except:
                pass
    
    if ndcg_scores:
        print(f"NDCG@3 на тестовом наборе: {np.mean(ndcg_scores):.4f} ± {np.std(ndcg_scores):.4f}")
    else:
        print("Не удалось рассчитать NDCG")
    
    # Важность фичей
    feature_importance = model.feature_importance(importance_type='gain')
    importance_df = pd.DataFrame({
        'feature': feature_columns,
        'importance': feature_importance
    }).sort_values('importance', ascending=False)
    
    print("\nВажность фичей:")
    print(importance_df)
    
    # Сохраняем модель
    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'ranker.pkl')
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"Модель сохранена в {model_path}")
    
    # Также сохраняем список фичей
    feature_info = {
        'feature_columns': feature_columns,
        'feature_importance': importance_df.to_dict('records'),
        'model_metrics': {
            'ndcg_mean': np.mean(ndcg_scores) if ndcg_scores else 0,
            'ndcg_std': np.std(ndcg_scores) if ndcg_scores else 0,
            'training_samples': len(df),
            'positive_samples': int(df['was_chosen'].sum())
        }
    }
    
    feature_info_path = os.path.join(os.path.dirname(model_path), 'feature_info.json')
    with open(feature_info_path, 'w') as f:
        json.dump(feature_info, f, indent=2)
    
    print("Информация о фичах сохранена")
    
    # Тестируем модель
    print("\nТестирование модели...")
    test_features = np.array([
        [1000, 0.8, 1, 4.5, 20, 3, 1.0],  # Хороший кандидат
        [2000, 1.6, 0, 3.0, 5, 1, 0.5],   # Дорогой кандидат
        [800, 0.6, 1, 4.8, 50, 5, 1.0],   # Очень хороший кандидат
    ])
    
    predictions = model.predict(test_features)
    print("Тестовые предсказания:")
    for i, pred in enumerate(predictions):
        print(f"Кандидат {i+1}: {pred:.4f}")
    
    # Ранжируем кандидатов
    ranked_indices = np.argsort(predictions)[::-1]
    print("\nРанжированные кандидаты (лучший первый):")
    for i, idx in enumerate(ranked_indices):
        print(f"{i+1}. Кандидат {idx+1} (score: {predictions[idx]:.4f})")


if __name__ == '__main__':
    try:
        train_ranker()
    except Exception as e:
        print(f"Ошибка при обучении модели: {e}")
        import traceback
        traceback.print_exc()