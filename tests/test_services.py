import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from django.contrib.auth import get_user_model

from apps.ml.services import AIMatchingService
from apps.tutors.models import TutorProfile, Subject
from apps.orders.models import Order, EmbeddingCache

User = get_user_model()


@pytest.mark.django_db
class TestAIMatchingService:
    """Test AI matching service functionality."""
    
    def setup_method(self):
        """Setup test data."""
        self.service = AIMatchingService()
        
        # Create test users
        self.student = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123'
        )
        
        self.tutor_user = User.objects.create_user(
            username='tutor',
            email='tutor@test.com',
            password='testpass123'
        )
        
        self.tutor = TutorProfile.objects.create(
            user=self.tutor_user,
            bio='Experienced mathematics tutor',
            experience_years=5,
            hourly_rate=Decimal('1500'),
            city='Moscow',
            region='Moscow Region'
        )
        
        self.subject = Subject.objects.create(name='Mathematics', category='Science')
        self.subject.tutors.add(self.tutor)
        
        self.order = Order.objects.create(
            student=self.student,
            subject=self.subject,
            title='Need calculus help',
            description='I struggle with derivatives and integrals',
            budget_min=Decimal('1000'),
            budget_max=Decimal('2000'),
            format_online=True,
            city='Moscow'
        )
    
    def test_get_candidate_tutors(self):
        """Test getting candidate tutors for an order."""
        candidates = self.service._get_candidate_tutors(self.order)
        
        assert len(candidates) == 1
        assert self.tutor in candidates
    
    def test_get_candidate_tutors_location_filter(self):
        """Test location filtering in candidate selection."""
        # Create tutor in different city
        other_user = User.objects.create_user(username='other', email='other@test.com', password='pass')
        other_tutor = TutorProfile.objects.create(
            user=other_user,
            city='Saint Petersburg',  # Different city
            hourly_rate=Decimal('1600')
        )
        self.subject.tutors.add(other_tutor)
        
        # For offline orders, should prefer same city
        self.order.format_offline = True
        self.order.save()
        
        candidates = self.service._get_candidate_tutors(self.order)
        
        # Should include both but Moscow tutor should be preferred
        moscow_tutors = [t for t in candidates if t.city == 'Moscow']
        assert len(moscow_tutors) >= 1
    
    def test_calculate_location_match(self):
        """Test location matching calculation."""
        # Same city
        match_score = self.service._calculate_location_match(self.order, self.tutor)
        assert match_score == 1.0
        
        # Different city
        self.tutor.city = 'Saint Petersburg'
        match_score = self.service._calculate_location_match(self.order, self.tutor)
        assert match_score == 0.5
        
        # No city info
        self.tutor.city = ''
        match_score = self.service._calculate_location_match(self.order, self.tutor)
        assert match_score == 0.3
    
    @patch('apps.ml.services.AIMatchingService._get_embedding')
    def test_calculate_vector_similarity(self, mock_get_embedding):
        """Test vector similarity calculation."""
        # Mock embeddings
        mock_get_embedding.side_effect = [
            [0.1, 0.2, 0.3],  # Order embedding
            [0.1, 0.2, 0.3],  # Tutor embedding (identical)
        ]
        
        similarity = self.service._calculate_vector_similarity(self.order, self.tutor)
        assert similarity == 1.0  # Perfect match
        
        # Test different embeddings
        mock_get_embedding.side_effect = [
            [1.0, 0.0, 0.0],  # Order embedding
            [0.0, 1.0, 0.0],  # Tutor embedding (orthogonal)
        ]
        
        similarity = self.service._calculate_vector_similarity(self.order, self.tutor)
        assert similarity == 0.0  # No similarity
    
    @patch('openai.OpenAI')
    def test_get_embedding_caching(self, mock_openai_client):
        """Test embedding caching functionality."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_openai_client.return_value.embeddings.create.return_value = mock_response
        
        self.service.openai_client = mock_openai_client.return_value
        
        text = "Test text for embedding"
        
        # First call should hit OpenAI API
        embedding1 = self.service._get_embedding(text)
        assert embedding1 == [0.1, 0.2, 0.3]
        assert mock_openai_client.return_value.embeddings.create.call_count == 1
        
        # Second call should use cache
        embedding2 = self.service._get_embedding(text)
        assert embedding2 == [0.1, 0.2, 0.3]
        assert mock_openai_client.return_value.embeddings.create.call_count == 1  # No additional calls
        
        # Verify cache entry was created
        assert EmbeddingCache.objects.filter(text=text).exists()
    
    @patch('apps.ml.services.AIMatchingService._get_embedding')
    @patch('apps.ml.services.AIMatchingService._llm_rerank')
    def test_get_ai_matches_full_flow(self, mock_llm_rerank, mock_get_embedding):
        """Test complete AI matching flow."""
        # Mock embeddings for similarity calculation
        mock_get_embedding.return_value = [0.1, 0.2, 0.3]
        
        # Mock LLM reranking
        mock_llm_rerank.return_value = [
            {
                'tutor_id': self.tutor.id,
                'score': 0.95,
                'reasons': ['Subject expertise', 'Location match'],
                'profile': {
                    'name': self.tutor.user.get_full_name(),
                    'rating': float(self.tutor.rating),
                    'experience_years': self.tutor.experience_years
                }
            }
        ]
        
        matches = self.service.get_ai_matches(self.order, limit=3)
        
        assert len(matches) == 1
        assert matches[0]['tutor_id'] == self.tutor.id
        assert matches[0]['score'] == 0.95
        assert 'Subject expertise' in matches[0]['reasons']
    
    def test_fallback_ranking_when_no_model(self):
        """Test fallback ranking when LightGBM model is not available."""
        # Ensure no model is loaded
        self.service.model = None
        
        candidates = [self.tutor]
        
        # Should use fallback ranking
        ranked_candidates = self.service._fallback_ranking(self.order, candidates)
        
        assert len(ranked_candidates) == 1
        assert ranked_candidates[0][0] == self.tutor  # Tutor object
        assert isinstance(ranked_candidates[0][1], float)  # Score
    
    def test_get_match_reasons(self):
        """Test match reasons generation."""
        reasons = self.service._get_match_reasons(self.order, self.tutor)
        
        assert isinstance(reasons, list)
        assert len(reasons) > 0
        
        # Should include subject match since tutor teaches the subject
        subject_reasons = [r for r in reasons if 'математик' in r.lower() or 'subject' in r.lower()]
        assert len(subject_reasons) > 0
    
    @patch('openai.OpenAI')
    def test_llm_rerank_openai_integration(self, mock_openai_client):
        """Test LLM reranking with OpenAI."""
        # Mock OpenAI chat completion response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='[{"tutor_id": 1, "score": 0.95, "reasons": ["Expert in calculus"]}]'))
        ]
        mock_openai_client.return_value.chat.completions.create.return_value = mock_response
        
        self.service.openai_client = mock_openai_client.return_value
        
        candidates = [self.tutor]
        result = self.service._llm_rerank(self.order, candidates, limit=3)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]['tutor_id'] == 1
        assert result[0]['score'] == 0.95


@pytest.mark.django_db
class TestEmbeddingCache:
    """Test embedding cache functionality."""
    
    def test_create_embedding_cache(self):
        """Test creating embedding cache entry."""
        text = "Test text for caching"
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        cache_entry = EmbeddingCache.objects.create(
            text=text,
            text_hash='test_hash_123',
            vector=vector
        )
        
        assert cache_entry.text == text
        assert cache_entry.vector == vector
        assert str(cache_entry) == f"Embedding cache for: {text[:50]}"
    
    def test_embedding_cache_uniqueness(self):
        """Test that embedding cache enforces unique hashes."""
        text = "Duplicate text"
        hash_value = "duplicate_hash"
        vector = [0.1, 0.2, 0.3]
        
        # Create first entry
        EmbeddingCache.objects.create(
            text=text,
            text_hash=hash_value,
            vector=vector
        )
        
        # Attempting to create duplicate should fail
        with pytest.raises(Exception):  # IntegrityError due to unique constraint
            EmbeddingCache.objects.create(
                text=text,
                text_hash=hash_value,
                vector=vector
            )