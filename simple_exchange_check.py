#!/usr/bin/env python3
"""
Simple Exchange Rate Checker

A simple exchange rate checker with basic error handling and logging.
"""

import requests
import json
import logging
from typing import Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleExchangeChecker:
    """Simple exchange rate checker with basic functionality."""
    
    def __init__(self):
        self.base_url = "https://api.exchangerate-api.com/v4/latest"
        self.last_request_time = None
        self.request_interval = 1.0  # Minimum seconds between requests
        
    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get exchange rate between two currencies.
        
        Args:
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            
        Returns:
            Exchange rate as float or None if failed
        """
        # Validate input
        if not from_currency or not to_currency:
            logger.error("Invalid currency codes provided")
            return None
        
        if from_currency == to_currency:
            return 1.0
        
        # Rate limiting
        if self.last_request_time:
            time_since_last = (datetime.now() - self.last_request_time).total_seconds()
            if time_since_last < self.request_interval:
                logger.warning(f"Rate limiting: waiting {self.request_interval - time_since_last:.2f} seconds")
                return None
        
        try:
            url = f"{self.base_url}/{from_currency}"
            logger.info(f"Requesting exchange rate from {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.last_request_time = datetime.now()
            
            if 'rates' in data and to_currency in data['rates']:
                rate = data['rates'][to_currency]
                logger.info(f"Successfully retrieved rate: {from_currency}->{to_currency} = {rate}")
                return rate
            else:
                logger.error(f"Currency {to_currency} not found in API response")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {from_currency}->{to_currency}")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {from_currency}->{to_currency}: {e}")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {from_currency}->{to_currency}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {from_currency}->{to_currency}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {from_currency}->{to_currency}: {e}")
            return None
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
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
        
        rate = self.get_rate(from_currency, to_currency)
        if rate is None:
            return None
        
        result = amount * rate
        logger.info(f"Converted {amount} {from_currency} to {result:.2f} {to_currency}")
        return result
    
    def get_supported_currencies(self) -> Optional[list]:
        """Get list of supported currencies."""
        try:
            response = requests.get(f"{self.base_url}/USD", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'rates' in data:
                currencies = list(data['rates'].keys())
                logger.info(f"Retrieved {len(currencies)} supported currencies")
                return currencies
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
    
    def test_connection(self) -> bool:
        """Test if the API is accessible."""
        try:
            response = requests.get(f"{self.base_url}/USD", timeout=5)
            response.raise_for_status()
            logger.info("API connection test successful")
            return True
        except requests.exceptions.Timeout:
            logger.error("API connection test failed: timeout")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API connection test failed: {e}")
            return False
        except requests.exceptions.HTTPError as e:
            logger.error(f"API connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False


def main():
    """Main function for testing the simple exchange checker."""
    checker = SimpleExchangeChecker()
    
    # Test connection first
    print("Testing API connection...")
    if not checker.test_connection():
        print("API connection failed. Exiting.")
        return
    
    # Test basic functionality
    test_cases = [
        ('USD', 'EUR'),
        ('EUR', 'USD'),
        ('USD', 'RUB'),
        ('GBP', 'JPY'),
    ]
    
    print("\nTesting Exchange Rates")
    print("=" * 30)
    
    for from_curr, to_curr in test_cases:
        print(f"\n{from_curr} -> {to_curr}")
        
        rate = checker.get_rate(from_curr, to_curr)
        if rate:
            print(f"Rate: {rate:.6f}")
            
            # Test conversion
            converted = checker.convert(100, from_curr, to_curr)
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
    
    # Test error cases
    print("\nTesting Error Cases")
    print("=" * 30)
    
    # Test invalid currency
    invalid_rate = checker.get_rate("INVALID", "USD")
    print(f"Invalid currency test: {invalid_rate}")
    
    # Test invalid amount
    invalid_conversion = checker.convert(-100, "USD", "EUR")
    print(f"Invalid amount test: {invalid_conversion}")
    
    # Test same currency
    same_currency = checker.get_rate("USD", "USD")
    print(f"Same currency test: {same_currency}")


if __name__ == "__main__":
    main()