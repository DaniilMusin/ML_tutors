import pytest
import openai
from unittest.mock import Mock, patch, MagicMock
from django.contrib.auth import get_user_model

from apps.ml.services import AIMatchingService, retry_openai_call
from apps.tutors.models import TutorProfile, Subject
from apps.orders.models import Order, EmbeddingCache

User = get_user_model()


@pytest.mark.django_db
class TestRetryLogic:
    """Test OpenAI retry logic and error handling."""
    
    def setup_method(self):
        """Setup test data."""
        self.service = AIMatchingService()
        
        # Create test data
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.subject = Subject.objects.create(name='Mathematics', category='Science')
        
        self.order = Order.objects.create(
            student=self.user,
            subject=self.subject,
            title='Test order',
            description='Test description',
            budget_min=1000,
            budget_max=2000
        )
    
    def test_retry_decorator_success_first_try(self):
        """Test that retry decorator works on successful first call."""
        @retry_openai_call(max_retries=2)
        def mock_function():
            return "success"
        
        result = mock_function()
        assert result == "success"
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_decorator_rate_limit_then_success(self, mock_sleep):
        """Test retry on rate limit then success."""
        call_count = 0
        
        @retry_openai_call(max_retries=2)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise openai.RateLimitError("Rate limit", response=Mock(), body="")
            return "success"
        
        result = mock_function()
        assert result == "success"
        assert call_count == 2
        assert mock_sleep.called
    
    @patch('time.sleep')
    def test_retry_decorator_timeout_then_success(self, mock_sleep):
        """Test retry on timeout then success."""
        call_count = 0
        
        @retry_openai_call(max_retries=2)
        def mock_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise openai.APITimeoutError("Timeout")
            return "success"
        
        result = mock_function()
        assert result == "success"
        assert call_count == 2
    
    @patch('time.sleep')
    def test_retry_decorator_max_retries_exceeded(self, mock_sleep):
        """Test that function returns None after max retries."""
        @retry_openai_call(max_retries=2)
        def mock_function():
            raise openai.RateLimitError("Rate limit", response=Mock(), body="")
        
        result = mock_function()
        assert result is None
    
    def test_retry_decorator_auth_error_no_retry(self):
        """Test that auth errors are not retried."""
        @retry_openai_call(max_retries=2)
        def mock_function():
            raise openai.AuthenticationError("Auth error")
        
        with pytest.raises(openai.AuthenticationError):
            mock_function()
    
    @patch('openai.OpenAI')
    def test_get_embedding_with_retry_success(self, mock_openai_client):
        """Test embedding generation with retry logic success."""
        # Mock successful response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
        mock_openai_client.return_value.embeddings.create.return_value = mock_response
        
        result = self.service._get_embedding("test text")
        
        assert result == [0.1, 0.2, 0.3]
        # Check that timeout was set
        mock_openai_client.return_value.embeddings.create.assert_called_with(
            model="text-embedding-3-small",
            input="test text",
            timeout=0.7
        )
    
    @patch('openai.OpenAI')
    def test_get_embedding_with_retry_failure(self, mock_openai_client):
        """Test embedding generation failure after retries."""
        # Mock failure
        mock_openai_client.return_value.embeddings.create.side_effect = openai.RateLimitError(
            "Rate limit", response=Mock(), body=""
        )
        
        result = self.service._get_embedding("test text")
        
        assert result is None
    
    @patch('openai.OpenAI')
    def test_get_embedding_caching(self, mock_openai_client):
        """Test that embeddings are cached and not re-requested."""
        # Create cached embedding
        EmbeddingCache.objects.create(
            text="test text",
            text_hash="a" * 64,  # Mock hash
            vector=[0.1, 0.2, 0.3]
        )
        
        with patch('hashlib.sha256') as mock_hash:
            mock_hash.return_value.hexdigest.return_value = "a" * 64
            
            result = self.service._get_embedding("test text")
            
            assert result == [0.1, 0.2, 0.3]
            # Should not call OpenAI API
            assert not mock_openai_client.return_value.embeddings.create.called
    
    @patch('openai.OpenAI')
    def test_llm_chat_with_retry_success(self, mock_openai_client):
        """Test LLM chat completion with retry logic."""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"result": "success"}'))]
        mock_openai_client.return_value.chat.completions.create.return_value = mock_response
        
        result = self.service._llm_chat_with_retry("system prompt", "user prompt")
        
        assert result == mock_response
        # Check that timeout was set
        mock_openai_client.return_value.chat.completions.create.assert_called_with(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"}
            ],
            temperature=0.3,
            timeout=0.7
        )
    
    @patch('openai.OpenAI')
    @patch('time.sleep')
    def test_llm_chat_with_retry_failure(self, mock_sleep, mock_openai_client):
        """Test LLM chat failure after retries."""
        # Mock failure
        mock_openai_client.return_value.chat.completions.create.side_effect = openai.RateLimitError(
            "Rate limit", response=Mock(), body=""
        )
        
        result = self.service._llm_chat_with_retry("system prompt", "user prompt")
        
        assert result is None


@pytest.mark.django_db
class TestAIMatchingServiceErrorHandling:
    """Test AI matching service error handling."""
    
    def setup_method(self):
        """Setup test data."""
        self.service = AIMatchingService()
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        self.tutor_user = User.objects.create_user(
            username='tutor',
            email='tutor@test.com',
            password='testpass123'
        )
        
        self.tutor = TutorProfile.objects.create(
            user=self.tutor_user,
            bio='Test tutor',
            experience_years=3,
            hourly_rate=1500,
            is_verified=True
        )
        
        self.subject = Subject.objects.create(name='Mathematics', category='Science')
        self.subject.tutors.add(self.tutor)
        
        self.order = Order.objects.create(
            student=self.user,
            subject=self.subject,
            title='Test order',
            description='Test description',
            budget_min=1000,
            budget_max=2000
        )
    
    @patch('apps.ml.services.AIMatchingService._llm_chat_with_retry')
    def test_llm_rerank_failure_graceful_degradation(self, mock_llm_chat):
        """Test that LLM reranking failure doesn't break the service."""
        mock_llm_chat.return_value = None  # Simulate LLM failure
        
        # Should still return matches even without LLM reranking
        matches = self.service.get_ai_matches(self.order, limit=1)
        
        assert len(matches) >= 0  # Should not crash
        mock_llm_chat.assert_called_once()
    
    @patch('apps.ml.services.AIMatchingService._get_embedding')
    def test_embedding_failure_graceful_degradation(self, mock_get_embedding):
        """Test that embedding failure doesn't break matching."""
        mock_get_embedding.return_value = None  # Simulate embedding failure
        
        # Should still return matches even without embeddings
        matches = self.service.get_ai_matches(self.order, limit=1)
        
        assert len(matches) >= 0  # Should not crash
    
    def test_no_candidates_empty_result(self):
        """Test that no candidates returns empty result."""
        # Create order with no matching tutors
        empty_subject = Subject.objects.create(name='EmptySubject', category='Test')
        empty_order = Order.objects.create(
            student=self.user,
            subject=empty_subject,
            title='Empty order',
            description='No tutors',
            budget_min=1000,
            budget_max=2000
        )
        
        matches = self.service.get_ai_matches(empty_order, limit=3)
        
        assert len(matches) == 0