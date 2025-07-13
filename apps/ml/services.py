import hashlib
import json
import numpy as np
import openai
from django.conf import settings
from django.db.models import Q
from typing import List, Dict, Optional
import lightgbm as lgb
import pickle
import os
from datetime import datetime

from apps.tutors.models import TutorProfile
from apps.orders.models import Order, EmbeddingCache


class AIMatchingService:
    """
    AI-powered tutor matching service using LightGBM and OpenAI.
    """
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_path = os.path.join(settings.BASE_DIR, 'ml', 'models', 'ranker.pkl')
        self.model = self._load_model()
    
    def _load_model(self) -> Optional[lgb.LGBMRanker]:
        """Load trained LightGBM model."""
        if os.path.exists(self.model_path):
            with open(self.model_path, 'rb') as f:
                return pickle.load(f)
        return None
    
    def get_ai_matches(self, order: Order, limit: int = 3) -> List[Dict]:
        """
        Get AI-powered tutor matches for an order.
        
        Args:
            order: Order object
            limit: Number of matches to return
            
        Returns:
            List of tutor matches with scores
        """
        # Step 1: Get candidate tutors
        candidates = self._get_candidate_tutors(order)
        
        if not candidates:
            return []
        
        # Step 2: Generate features for ranking
        features = self._generate_features(order, candidates)
        
        # Step 3: Rank using LightGBM (if model available)
        if self.model:
            scores = self._rank_with_lightgbm(features)
            # Sort by score (descending)
            ranked_candidates = sorted(
                zip(candidates, scores), 
                key=lambda x: x[1], 
                reverse=True
            )
        else:
            # Fallback to simple scoring
            ranked_candidates = self._fallback_ranking(order, candidates)
        
        # Step 4: Optional LLM reranking for top candidates
        top_candidates = [c[0] for c in ranked_candidates[:limit * 2]]
        
        if len(top_candidates) > limit:
            reranked = self._llm_rerank(order, top_candidates, limit)
            if reranked:
                return reranked
        
        # Return top candidates
        return [
            {
                'tutor': candidate,
                'score': score,
                'match_reasons': self._get_match_reasons(order, candidate)
            }
            for candidate, score in ranked_candidates[:limit]
        ]
    
    def _get_candidate_tutors(self, order: Order) -> List[TutorProfile]:
        """Get candidate tutors for an order."""
        # Basic filtering
        candidates = TutorProfile.objects.filter(
            is_verified=True,
            user__is_active=True,
            subjects__in=[order.subject]
        ).distinct()
        
        # Filter by budget
        if order.budget_max > 0:
            candidates = candidates.filter(
                hourly_rate__lte=order.budget_max * 1.1  # 10% tolerance
            )
        
        # Filter by location (if offline required)
        if order.format_offline and order.city:
            candidates = candidates.filter(
                Q(city__icontains=order.city) |
                Q(region__icontains=order.region)
            )
        
        return list(candidates[:200])  # Limit to 200 candidates
    
    def _generate_features(self, order: Order, candidates: List[TutorProfile]) -> np.ndarray:
        """Generate features for ranking."""
        features = []
        
        for tutor in candidates:
            feature_vector = [
                # Price features
                float(tutor.hourly_rate),
                float(tutor.hourly_rate / max(order.budget_max, 1)),
                1 if tutor.hourly_rate <= order.budget_max else 0,
                
                # Quality features
                float(tutor.rating),
                float(tutor.rating_count),
                float(tutor.experience_years),
                
                # Availability overlap (simplified)
                self._calculate_availability_overlap(order, tutor),
                
                # Location match
                self._calculate_location_match(order, tutor),
                
                # Vector similarity (if available)
                self._calculate_vector_similarity(order, tutor),
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def _calculate_availability_overlap(self, order: Order, tutor: TutorProfile) -> float:
        """Calculate availability overlap between order and tutor."""
        # Simplified calculation - in real implementation, parse JSON schedules
        if not tutor.availability or not order.schedule_json:
            return 0.5
        
        # Mock calculation - should implement proper schedule overlap
        return 0.8
    
    def _calculate_location_match(self, order: Order, tutor: TutorProfile) -> float:
        """Calculate location match score."""
        if not order.format_offline:
            return 1.0  # Online format - location doesn't matter
        
        if order.city and tutor.city:
            if order.city.lower() in tutor.city.lower():
                return 1.0
            elif order.region and tutor.region:
                if order.region.lower() in tutor.region.lower():
                    return 0.7
        
        return 0.3
    
    def _calculate_vector_similarity(self, order: Order, tutor: TutorProfile) -> float:
        """Calculate vector similarity between order and tutor."""
        if not tutor.vector:
            return 0.5
        
        # Get order embedding
        order_text = f"{order.title} {order.description} {order.goal_text}"
        order_embedding = self._get_embedding(order_text)
        
        if not order_embedding:
            return 0.5
        
        # Calculate cosine similarity
        tutor_vector = np.array(tutor.vector)
        order_vector = np.array(order_embedding)
        
        # Normalize vectors
        tutor_norm = np.linalg.norm(tutor_vector)
        order_norm = np.linalg.norm(order_vector)
        
        if tutor_norm == 0 or order_norm == 0:
            return 0.5
        
        similarity = np.dot(tutor_vector, order_vector) / (tutor_norm * order_norm)
        return float(similarity)
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text, with caching."""
        if not text.strip():
            return None
        
        # Create hash for caching
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Check cache
        cache_entry = EmbeddingCache.objects.filter(text_hash=text_hash).first()
        if cache_entry:
            return cache_entry.vector
        
        try:
            # Get embedding from OpenAI
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # Cache the result
            EmbeddingCache.objects.create(
                text=text[:1000],  # Limit text length
                text_hash=text_hash,
                vector=embedding
            )
            
            return embedding
            
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None
    
    def _rank_with_lightgbm(self, features: np.ndarray) -> List[float]:
        """Rank candidates using LightGBM."""
        if not self.model:
            return [0.5] * len(features)
        
        try:
            scores = self.model.predict(features)
            return scores.tolist()
        except Exception as e:
            print(f"Error ranking with LightGBM: {e}")
            return [0.5] * len(features)
    
    def _fallback_ranking(self, order: Order, candidates: List[TutorProfile]) -> List[tuple]:
        """Fallback ranking without ML model."""
        scored_candidates = []
        
        for tutor in candidates:
            score = 0.0
            
            # Rating score (0-1)
            score += float(tutor.rating) / 5.0 * 0.3
            
            # Price score (closer to budget max = better)
            if order.budget_max > 0:
                price_score = 1.0 - abs(tutor.hourly_rate - order.budget_max) / order.budget_max
                score += max(0, price_score) * 0.2
            
            # Experience score
            score += min(float(tutor.experience_years) / 10.0, 1.0) * 0.2
            
            # Review count score
            score += min(float(tutor.rating_count) / 100.0, 1.0) * 0.1
            
            # Location score
            score += self._calculate_location_match(order, tutor) * 0.1
            
            # Vector similarity score
            score += self._calculate_vector_similarity(order, tutor) * 0.1
            
            scored_candidates.append((tutor, score))
        
        return sorted(scored_candidates, key=lambda x: x[1], reverse=True)
    
    def _llm_rerank(self, order: Order, candidates: List[TutorProfile], limit: int) -> Optional[List[Dict]]:
        """Use LLM to rerank top candidates."""
        try:
            # Prepare data for LLM
            order_data = {
                'title': order.title,
                'description': order.description,
                'goal': order.goal_text,
                'budget': f"{order.budget_min}-{order.budget_max}",
                'subject': order.subject.name,
                'format': 'online' if order.format_online else 'offline',
                'location': f"{order.city}, {order.region}" if order.city else None
            }
            
            candidates_data = []
            for tutor in candidates:
                candidates_data.append({
                    'id': tutor.id,
                    'name': tutor.user.get_full_name() or tutor.user.username,
                    'bio': tutor.bio[:200],
                    'experience': tutor.experience_years,
                    'rate': float(tutor.hourly_rate),
                    'rating': float(tutor.rating),
                    'subjects': tutor.subjects_display,
                    'city': tutor.city
                })
            
            # Create prompt
            prompt = json.dumps({
                'task': 'rank_tutors',
                'student_order': order_data,
                'candidates': candidates_data,
                'limit': limit
            })
            
            system_prompt = """You are an AI assistant that helps match students with tutors. 
            Given a student's order and a list of tutor candidates, rank the top tutors that best match the student's needs.
            
            Consider:
            - Subject expertise and experience
            - Budget compatibility
            - Location (if offline lessons)
            - Teaching style fit based on bio
            - Overall quality (rating, reviews)
            
            Return a JSON array with tutor IDs in ranked order (best first).
            Example: [{"id": 1, "reason": "Perfect subject match and budget"}, {"id": 3, "reason": "High rating and experience"}]
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                timeout=1.0
            )
            
            # Parse response
            result = json.loads(response.choices[0].message.content)
            
            # Convert to expected format
            reranked = []
            for item in result:
                tutor_id = item['id']
                reason = item.get('reason', '')
                
                tutor = next((t for t in candidates if t.id == tutor_id), None)
                if tutor:
                    reranked.append({
                        'tutor': tutor,
                        'score': 0.9,  # High score for LLM-selected
                        'match_reasons': [reason]
                    })
            
            return reranked[:limit]
            
        except Exception as e:
            print(f"Error in LLM reranking: {e}")
            return None
    
    def _get_match_reasons(self, order: Order, tutor: TutorProfile) -> List[str]:
        """Generate match reasons for a tutor."""
        reasons = []
        
        # Subject match
        if tutor.subjects.filter(id=order.subject.id).exists():
            reasons.append(f"Специализируется на {order.subject.name}")
        
        # Budget match
        if order.budget_min <= tutor.hourly_rate <= order.budget_max:
            reasons.append("Цена в вашем бюджете")
        
        # High rating
        if tutor.rating >= 4.5:
            reasons.append(f"Высокий рейтинг ({tutor.rating}/5)")
        
        # Experience
        if tutor.experience_years >= 5:
            reasons.append(f"Опыт работы {tutor.experience_years} лет")
        
        # Location match
        if order.format_offline and tutor.city and order.city:
            if order.city.lower() in tutor.city.lower():
                reasons.append("Находится в вашем городе")
        
        return reasons