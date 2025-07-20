#!/usr/bin/env python3
"""
Final Exchange Rate Checker

This module provides the final version of exchange rate checking functionality
with comprehensive error handling and multiple fallback strategies.
"""

import requests
import json
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """Enumeration of available API providers."""
    EXCHANGE_RATE_API = "exchangerate-api"
    OPEN_ER_API = "open-er-api"
    FIXER_IO = "fixer-io"
    CURRENCY_LAYER = "currency-layer"


@dataclass
class ExchangeRate:
    """Data class for exchange rate information."""
    from_currency: str
    to_currency: str
    rate: float
    timestamp: datetime
    provider: APIProvider
    source_url: str


class ExchangeRateService:
    """Service for fetching exchange rates from multiple providers."""
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        self.api_keys = api_keys or {}
        self.cache = {}
        self.cache_duration = timedelta(minutes=5)
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # API endpoints configuration
        self.endpoints = {
            APIProvider.EXCHANGE_RATE_API: {
                'url': "https://api.exchangerate-api.com/v4/latest/{base}",
                'timeout': 10,
                'requires_key': False
            },
            APIProvider.OPEN_ER_API: {
                'url': "https://open.er-api.com/v6/latest/{base}",
                'timeout': 15,
                'requires_key': False
            },
            APIProvider.FIXER_IO: {
                'url': "http://data.fixer.io/api/latest?access_key={key}&base={base}",
                'timeout': 10,
                'requires_key': True
            },
            APIProvider.CURRENCY_LAYER: {
                'url': "http://api.currencylayer.com/live?access_key={key}&currencies={target}",
                'timeout': 10,
                'requires_key': True
            }
        }
    
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[ExchangeRate]:
        """
        Get exchange rate with comprehensive error handling and fallback strategies.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            ExchangeRate object or None if all providers fail
        """
        # Check cache first
        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in self.cache:
            cached_rate = self.cache[cache_key]
            if datetime.now() - cached_rate.timestamp < self.cache_duration:
                logger.debug(f"Using cached rate for {cache_key}: {cached_rate.rate}")
                return cached_rate
        
        # Try each provider in order
        providers = [
            APIProvider.EXCHANGE_RATE_API,
            APIProvider.OPEN_ER_API,
            APIProvider.FIXER_IO,
            APIProvider.CURRENCY_LAYER
        ]
        
        for provider in providers:
            rate = self._try_provider(provider, from_currency, to_currency)
            if rate is not None:
                # Cache successful result
                self.cache[cache_key] = rate
                logger.info(f"Successfully retrieved rate from {provider.value}: {rate.rate}")
                return rate
        
        logger.error(f"All providers failed for {from_currency}->{to_currency}")
        return None
    
    def _try_provider(self, provider: APIProvider, from_currency: str, to_currency: str) -> Optional[ExchangeRate]:
        """Try to get rate from a specific provider with retry logic."""
        endpoint_config = self.endpoints[provider]
        
        for attempt in range(self.max_retries):
            try:
                rate = self._fetch_from_provider(provider, endpoint_config, from_currency, to_currency)
                if rate is not None:
                    return rate
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Provider {provider.value} timeout (attempt {attempt + 1}/{self.max_retries})")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Provider {provider.value} connection error (attempt {attempt + 1}/{self.max_retries}): {e}")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"Provider {provider.value} HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
            except json.JSONDecodeError as e:
                logger.warning(f"Provider {provider.value} JSON decode error (attempt {attempt + 1}/{self.max_retries}): {e}")
            except Exception as e:
                logger.warning(f"Provider {provider.value} unexpected error (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))
        
        logger.error(f"Provider {provider.value} failed after {self.max_retries} attempts")
        return None
    
    def _fetch_from_provider(self, provider: APIProvider, config: Dict, from_currency: str, to_currency: str) -> Optional[ExchangeRate]:
        """Fetch rate from a specific provider."""
        url = config['url']
        timeout = config['timeout']
        
        # Format URL with parameters
        if provider == APIProvider.FIXER_IO:
            api_key = self.api_keys.get('fixer_io')
            if not api_key:
                logger.warning("Fixer.io API key not provided, skipping")
                return None
            url = url.format(key=api_key, base=from_currency)
        elif provider == APIProvider.CURRENCY_LAYER:
            api_key = self.api_keys.get('currency_layer')
            if not api_key:
                logger.warning("Currency Layer API key not provided, skipping")
                return None
            url = url.format(key=api_key, target=to_currency)
        else:
            url = url.format(base=from_currency)
        
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        rate = self._parse_provider_response(provider, data, from_currency, to_currency)
        
        if rate is not None:
            return ExchangeRate(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                timestamp=datetime.now(),
                provider=provider,
                source_url=url
            )
        
        return None
    
    def _parse_provider_response(self, provider: APIProvider, data: Dict, from_currency: str, to_currency: str) -> Optional[float]:
        """Parse response from different providers."""
        try:
            if provider == APIProvider.EXCHANGE_RATE_API:
                if 'rates' in data and to_currency in data['rates']:
                    return data['rates'][to_currency]
                    
            elif provider == APIProvider.OPEN_ER_API:
                if 'rates' in data and to_currency in data['rates']:
                    return data['rates'][to_currency]
                    
            elif provider == APIProvider.FIXER_IO:
                if data.get('success') and 'rates' in data and to_currency in data['rates']:
                    return data['rates'][to_currency]
                else:
                    logger.warning(f"Fixer.io API error: {data.get('error', {}).get('info', 'Unknown error')}")
                    
            elif provider == APIProvider.CURRENCY_LAYER:
                if data.get('success') and 'quotes' in data:
                    quote_key = f"{from_currency}{to_currency}"
                    if quote_key in data['quotes']:
                        return data['quotes'][quote_key]
                else:
                    logger.warning(f"Currency Layer API error: {data.get('error', {}).get('info', 'Unknown error')}")
            
            logger.warning(f"Could not parse response from {provider.value}")
            return None
            
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Error parsing {provider.value} response: {e}")
            return None
    
    def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert amount between currencies."""
        if amount <= 0:
            logger.warning(f"Invalid amount for conversion: {amount}")
            return None
        
        rate_info = self.get_exchange_rate(from_currency, to_currency)
        if rate_info is None:
            return None
        
        return amount * rate_info.rate
    
    def get_supported_currencies(self) -> Optional[List[str]]:
        """Get list of supported currencies from the most reliable provider."""
        providers = [APIProvider.EXCHANGE_RATE_API, APIProvider.OPEN_ER_API]
        
        for provider in providers:
            try:
                currencies = self._get_currencies_from_provider(provider)
                if currencies:
                    logger.info(f"Retrieved {len(currencies)} currencies from {provider.value}")
                    return currencies
            except Exception as e:
                logger.warning(f"Failed to get currencies from {provider.value}: {e}")
        
        logger.error("All providers failed to return supported currencies")
        return None
    
    def _get_currencies_from_provider(self, provider: APIProvider) -> Optional[List[str]]:
        """Get supported currencies from a specific provider."""
        config = self.endpoints[provider]
        url = config['url'].format(base='USD')
        
        response = requests.get(url, timeout=config['timeout'])
        response.raise_for_status()
        
        data = response.json()
        if 'rates' in data:
            return list(data['rates'].keys())
        
        return None
    
    def clear_cache(self):
        """Clear the exchange rate cache."""
        self.cache.clear()
        logger.info("Exchange rate cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cache_size': len(self.cache),
            'cache_keys': list(self.cache.keys()),
            'oldest_entry': min(self.cache.values(), key=lambda x: x.timestamp).timestamp if self.cache else None,
            'newest_entry': max(self.cache.values(), key=lambda x: x.timestamp).timestamp if self.cache else None
        }


class ExchangeRateManager:
    """High-level manager for exchange rate operations."""
    
    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        self.service = ExchangeRateService(api_keys)
        self.last_error = None
        self.error_count = 0
        self.success_count = 0
    
    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate with error tracking."""
        try:
            rate_info = self.service.get_exchange_rate(from_currency, to_currency)
            if rate_info:
                self.success_count += 1
                self.last_error = None
                return rate_info.rate
            else:
                self.error_count += 1
                self.last_error = f"Failed to get rate for {from_currency}->{to_currency}"
                return None
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"Unexpected error in get_rate: {e}")
            return None
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """Convert amount with error tracking."""
        try:
            result = self.service.convert_amount(amount, from_currency, to_currency)
            if result is not None:
                self.success_count += 1
                self.last_error = None
            else:
                self.error_count += 1
                self.last_error = f"Failed to convert {amount} {from_currency} to {to_currency}"
            return result
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"Unexpected error in convert: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operation statistics."""
        total_operations = self.success_count + self.error_count
        success_rate = (self.success_count / total_operations * 100) if total_operations > 0 else 0
        
        return {
            'success_count': self.success_count,
            'error_count': self.error_count,
            'total_operations': total_operations,
            'success_rate': success_rate,
            'last_error': self.last_error,
            'cache_stats': self.service.get_cache_stats()
        }


def main():
    """Main function for testing the exchange rate service."""
    # Initialize with optional API keys
    api_keys = {
        'fixer_io': 'your_fixer_io_key_here',
        'currency_layer': 'your_currency_layer_key_here'
    }
    
    manager = ExchangeRateManager(api_keys)
    
    # Test basic functionality
    test_cases = [
        ('USD', 'EUR'),
        ('EUR', 'USD'),
        ('USD', 'RUB'),
        ('GBP', 'JPY'),
        ('CAD', 'AUD'),
    ]
    
    print("Testing Exchange Rate Service")
    print("=" * 40)
    
    for from_curr, to_curr in test_cases:
        print(f"\nTesting {from_curr} -> {to_curr}")
        
        rate = manager.get_rate(from_curr, to_curr)
        if rate:
            print(f"Rate: {rate:.6f}")
            
            # Test conversion
            converted = manager.convert(100, from_curr, to_curr)
            if converted:
                print(f"100 {from_curr} = {converted:.2f} {to_curr}")
        else:
            print("Failed to get rate")
    
    # Test supported currencies
    print("\nGetting supported currencies...")
    currencies = manager.service.get_supported_currencies()
    if currencies:
        print(f"Found {len(currencies)} supported currencies")
        print("Sample currencies:", currencies[:10])
    else:
        print("Failed to get supported currencies")
    
    # Print statistics
    print("\nService Statistics")
    print("=" * 40)
    stats = manager.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()