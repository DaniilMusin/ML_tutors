#!/usr/bin/env python3
"""
Improved Exchange Rate Checker

This module provides improved exchange rate checking functionality with proper
exception handling and error logging.
"""

import requests
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExchangeRateChecker:
    """Improved exchange rate checker with proper error handling."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.exchangerate-api.com/v4/latest"
        self.fallback_url = "https://open.er-api.com/v6/latest"
        self.cache = {}
        self.cache_duration = timedelta(minutes=5)
        
    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get exchange rate between two currencies with proper error handling.
        
        Args:
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            
        Returns:
            Exchange rate as float or None if failed
        """
        cache_key = f"{from_currency}_{to_currency}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < self.cache_duration:
                logger.debug(f"Using cached rate for {cache_key}: {cached_data['rate']}")
                return cached_data['rate']
        
        # Try primary API endpoint
        rate = self._try_primary_api(from_currency, to_currency)
        
        # If primary fails, try fallback API
        if rate is None:
            logger.warning(f"Primary API failed for {from_currency}->{to_currency}, trying fallback")
            rate = self._try_fallback_api(from_currency, to_currency)
        
        # Cache successful result
        if rate is not None:
            self.cache[cache_key] = {
                'rate': rate,
                'timestamp': datetime.now()
            }
            logger.info(f"Successfully retrieved rate for {from_currency}->{to_currency}: {rate}")
        else:
            logger.error(f"Failed to retrieve exchange rate for {from_currency}->{to_currency}")
        
        return rate
    
    def _try_primary_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Try to get rate from primary API endpoint."""
        try:
            url = f"{self.base_url}/{from_currency}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'rates' in data and to_currency in data['rates']:
                return data['rates'][to_currency]
            else:
                logger.warning(f"Currency {to_currency} not found in primary API response")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Primary API timeout for {from_currency}->{to_currency}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Primary API connection error for {from_currency}->{to_currency}: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Primary API HTTP error for {from_currency}->{to_currency}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Primary API JSON decode error for {from_currency}->{to_currency}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error with primary API for {from_currency}->{to_currency}: {e}")
            return None
    
    def _try_fallback_api(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Try to get rate from fallback API endpoint."""
        try:
            url = f"{self.fallback_url}/{from_currency}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            if 'rates' in data and to_currency in data['rates']:
                return data['rates'][to_currency]
            else:
                logger.warning(f"Currency {to_currency} not found in fallback API response")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Fallback API timeout for {from_currency}->{to_currency}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Fallback API connection error for {from_currency}->{to_currency}: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Fallback API HTTP error for {from_currency}->{to_currency}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Fallback API JSON decode error for {from_currency}->{to_currency}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error with fallback API for {from_currency}->{to_currency}: {e}")
            return None
    
    def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Convert amount between currencies.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Converted amount or None if failed
        """
        if amount <= 0:
            logger.warning(f"Invalid amount for conversion: {amount}")
            return None
            
        rate = self.get_exchange_rate(from_currency, to_currency)
        if rate is None:
            return None
            
        return amount * rate
    
    def get_supported_currencies(self) -> Optional[list]:
        """Get list of supported currencies."""
        try:
            response = requests.get(f"{self.base_url}/USD", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'rates' in data:
                return list(data['rates'].keys())
            else:
                logger.warning("No rates found in API response")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Timeout getting supported currencies")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error getting supported currencies: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting supported currencies: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error getting supported currencies: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting supported currencies: {e}")
            return None


def main():
    """Main function for testing the exchange rate checker."""
    checker = ExchangeRateChecker()
    
    # Test basic functionality
    test_cases = [
        ('USD', 'EUR'),
        ('EUR', 'USD'),
        ('USD', 'RUB'),
        ('GBP', 'JPY'),
    ]
    
    for from_curr, to_curr in test_cases:
        print(f"\nTesting {from_curr} -> {to_curr}")
        
        rate = checker.get_exchange_rate(from_curr, to_curr)
        if rate:
            print(f"Rate: {rate}")
            
            # Test conversion
            converted = checker.convert_amount(100, from_curr, to_curr)
            if converted:
                print(f"100 {from_curr} = {converted:.2f} {to_curr}")
        else:
            print("Failed to get rate")
    
    # Test supported currencies
    print("\nGetting supported currencies...")
    currencies = checker.get_supported_currencies()
    if currencies:
        print(f"Found {len(currencies)} supported currencies")
        print("Sample currencies:", currencies[:10])
    else:
        print("Failed to get supported currencies")


if __name__ == "__main__":
    main()