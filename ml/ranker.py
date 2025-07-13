"""
ML Ranker for tutor matching using LightGBM
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import List, Tuple, Optional, Dict
import pickle
import os
from django.conf import settings
from django.db.models import Q
from apps.orders.models import Order, Booking
from apps.tutors.models import TutorProfile, Subject


class TutorRanker:
    """
    LightGBM-based ranker for matching tutors to orders
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.feature_names = [
            'tutor_rating', 'tutor_experience', 'tutor_price',
            'subject_match', 'location_match', 'format_match',
            'rating_count', 'availability_score'
        ]
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def extract_features(self, order: Order, tutor: TutorProfile) -> np.ndarray:
        """
        Extract features for order-tutor pair
        """
        features = []
        
        # Tutor features
        features.append(float(tutor.rating))
        features.append(float(tutor.experience_years))
        features.append(float(tutor.hourly_rate))
        
        # Subject match
        subject_match = 1.0 if tutor.subjects.filter(id=order.subject.id).exists() else 0.0
        features.append(subject_match)
        
        # Location match
        location_match = 1.0 if order.city and tutor.city and order.city.lower() == tutor.city.lower() else 0.0
        features.append(location_match)
        
        # Format match
        format_match = 0.0
        if order.format_online and order.format_offline:
            format_match = 1.0  # Any format is acceptable
        elif order.format_online:
            format_match = 1.0  # Online always available
        elif order.format_offline and location_match:
            format_match = 1.0  # Offline only if location matches
        features.append(format_match)
        
        # Rating count (reliability indicator)
        features.append(float(tutor.rating_count))
        
        # Availability score (simplified)
        availability_score = 1.0 if tutor.availability else 0.5
        features.append(availability_score)
        
        return np.array(features, dtype=np.float32)
    
    def prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare training data from completed bookings
        """
        bookings = Booking.objects.filter(
            status='completed'
        ).select_related(
            'application__order', 'application__tutor'
        )
        
        features_list = []
        labels_list = []
        groups_list = []
        
        current_group = 0
        current_order_id = None
        
        for booking in bookings:
            order = booking.application.order
            tutor = booking.application.tutor
            
            # Start new group for each order
            if current_order_id != order.id:
                current_order_id = order.id
                current_group += 1
                
                # Get all tutors who applied to this order
                applications = order.applications.select_related('tutor')
                
                for app in applications:
                    features = self.extract_features(order, app.tutor)
                    features_list.append(features)
                    
                    # Label: 1 if this tutor was chosen, 0 otherwise
                    label = 1 if app.is_chosen else 0
                    labels_list.append(label)
                    groups_list.append(current_group)
        
        if not features_list:
            # Return dummy data if no training data available
            return (
                np.array([[0.0] * len(self.feature_names)], dtype=np.float32),
                np.array([0], dtype=np.int32),
                np.array([1], dtype=np.int32)
            )
        
        return (
            np.array(features_list, dtype=np.float32),
            np.array(labels_list, dtype=np.int32),
            np.array(groups_list, dtype=np.int32)
        )
    
    def train(self, save_path: Optional[str] = None) -> Dict:
        """
        Train the ranking model
        """
        X, y, groups = self.prepare_training_data()
        
        if len(X) < 2:
            raise ValueError("Not enough training data available")
        
        # LightGBM ranking parameters
        params = {
            'objective': 'lambdarank',
            'metric': 'ndcg',
            'ndcg_eval_at': [1, 3, 5],
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': 0,
            'random_state': 42
        }
        
        # Create LightGBM dataset
        train_data = lgb.Dataset(
            X, label=y, group=np.bincount(groups), feature_name=self.feature_names
        )
        
        # Train model
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=100,
            valid_sets=[train_data],
            callbacks=[lgb.early_stopping(stopping_rounds=10)]
        )
        
        # Save model if path provided
        if save_path:
            self.save_model(save_path)
        
        # Return training metrics
        return {
            'num_samples': len(X),
            'num_groups': len(np.unique(groups)),
            'feature_importance': dict(zip(
                self.feature_names,
                self.model.feature_importance().tolist()
            ))
        }
    
    def predict(self, order: Order, tutors: List[TutorProfile]) -> List[Tuple[TutorProfile, float]]:
        """
        Rank tutors for a given order
        """
        if not self.model:
            # Return random order if no model available
            return [(tutor, np.random.random()) for tutor in tutors]
        
        if not tutors:
            return []
        
        # Extract features for all tutors
        features_matrix = np.array([
            self.extract_features(order, tutor) for tutor in tutors
        ], dtype=np.float32)
        
        # Predict scores
        scores = self.model.predict(features_matrix)
        
        # Sort by score (descending)
        tutor_scores = list(zip(tutors, scores))
        tutor_scores.sort(key=lambda x: x[1], reverse=True)
        
        return tutor_scores
    
    def get_top_k(self, order_id: int, k: int = 10) -> List[Dict]:
        """
        Get top K tutors for a given order
        """
        try:
            order = Order.objects.select_related('subject').get(id=order_id)
        except Order.DoesNotExist:
            return []
        
        # Get eligible tutors
        tutors = TutorProfile.objects.filter(
            subjects=order.subject
        ).select_related('user').prefetch_related('subjects')
        
        # Filter by location if offline format required
        if order.format_offline and not order.format_online and order.city:
            tutors = tutors.filter(city__iexact=order.city)
        
        tutors = list(tutors[:50])  # Limit to reasonable number
        
        if not tutors:
            return []
        
        # Rank tutors
        ranked_tutors = self.predict(order, tutors)
        
        # Return top K with details
        results = []
        for tutor, score in ranked_tutors[:k]:
            results.append({
                'tutor_id': tutor.id,
                'user_id': tutor.user.id,
                'name': f"{tutor.user.first_name} {tutor.user.last_name}",
                'rating': float(tutor.rating),
                'experience_years': tutor.experience_years,
                'hourly_rate': float(tutor.hourly_rate),
                'city': tutor.city,
                'score': float(score)
            })
        
        return results
    
    def save_model(self, path: str):
        """Save the trained model"""
        if self.model:
            self.model.save_model(path)
    
    def load_model(self, path: str):
        """Load a pre-trained model"""
        if os.path.exists(path):
            self.model = lgb.Booster(model_file=path)


# Global ranker instance
_ranker_instance = None


def get_ranker() -> TutorRanker:
    """Get the global ranker instance"""
    global _ranker_instance
    
    if _ranker_instance is None:
        model_path = os.path.join(settings.BASE_DIR, 'ml', 'models', 'tutor_ranker.txt')
        _ranker_instance = TutorRanker(model_path)
    
    return _ranker_instance