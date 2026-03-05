"""
Rate limiting service for external API calls

Ensures we respect API rate limits and don't overload services.
Implements token bucket pattern for fair request distribution.
"""

import time
import threading
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter
    
    Allows a maximum number of calls per time period.
    Supports thread-safe rate limiting across multiple threads.
    """
    
    def __init__(self, calls_per_second: float, name: str = "RateLimiter"):
        """
        Initialize rate limiter
        
        Args:
            calls_per_second: Maximum calls allowed per second
            name: Name for logging purposes
        """
        self.calls_per_second = calls_per_second
        self.name = name
        self.min_interval = 1.0 / calls_per_second
        self.last_call_time = 0
        self.lock = threading.RLock()
        self.stats = {
            'total_calls': 0,
            'total_waits': 0,
            'total_wait_time': 0,
        }
    
    def wait_if_needed(self) -> float:
        """
        Block if needed to maintain rate limit
        
        Returns:
            Actual time slept (seconds)
        """
        with self.lock:
            elapsed = time.time() - self.last_call_time
            sleep_time = max(0, self.min_interval - elapsed)
            
            if sleep_time > 0:
                logger.debug(
                    f"{self.name}: Rate limit sleep for {sleep_time:.3f}s"
                )
                time.sleep(sleep_time)
                self.stats['total_waits'] += 1
                self.stats['total_wait_time'] += sleep_time
            
            self.last_call_time = time.time()
            self.stats['total_calls'] += 1
            
            return sleep_time
    
    def reset(self):
        """Reset rate limiter"""
        with self.lock:
            self.last_call_time = 0
            self.stats = {
                'total_calls': 0,
                'total_waits': 0,
                'total_wait_time': 0,
            }
    
    def get_stats(self) -> dict:
        """Get statistics about rate limiting"""
        with self.lock:
            return {
                **self.stats,
                'calls_per_second': self.calls_per_second,
                'average_wait_per_call': (
                    self.stats['total_wait_time'] / max(1, self.stats['total_calls'])
                ),
            }


class CircuitBreaker:
    """
    Circuit breaker pattern for handling service failures
    
    Prevents cascading failures by stopping requests to a failing service
    and attempting recovery after a timeout.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Service failing, stop requests
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "CircuitBreaker"
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.lock = threading.RLock()
    
    def is_available(self) -> bool:
        """Check if service is available (circuit is not OPEN)"""
        with self.lock:
            if self.state == self.CLOSED:
                return True
            
            if self.state == self.OPEN:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = self.HALF_OPEN
                    self.failure_count = 0
                    logger.info(f"{self.name}: Circuit entering HALF_OPEN state")
                    return True
                return False
            
            # HALF_OPEN: allow one request to test
            return True
    
    def record_success(self):
        """Record a successful call"""
        with self.lock:
            self.failure_count = 0
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                logger.info(f"{self.name}: Circuit recovered to CLOSED state")
    
    def record_failure(self):
        """Record a failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                if self.state != self.OPEN:
                    logger.warning(
                        f"{self.name}: Circuit opened after "
                        f"{self.failure_count} failures"
                    )
                self.state = self.OPEN
    
    def reset(self):
        """Reset circuit breaker to CLOSED state"""
        with self.lock:
            self.state = self.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                'state': self.state,
                'failure_count': self.failure_count,
                'last_failure_time': self.last_failure_time,
            }


# Global rate limiters for each service
SCRYFALL_LIMITER = RateLimiter(
    calls_per_second=10,
    name="Scryfall"
)

TCGPLAYER_LIMITER = RateLimiter(
    calls_per_second=16.67,  # 1000 per minute
    name="TCGPlayer"
)

EBAY_LIMITER = RateLimiter(
    calls_per_second=100,
    name="eBay"
)

# Global circuit breakers
SCRYFALL_BREAKER = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    name="ScryfallBreaker"
)

TCGPLAYER_BREAKER = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120,
    name="TCGPlayerBreaker"
)

EBAY_BREAKER = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120,
    name="eBayBreaker"
)


def apply_rate_limit(limiter: RateLimiter, breaker: CircuitBreaker):
    """
    Decorator to apply rate limiting and circuit breaking to a function
    
    Usage:
        @apply_rate_limit(SCRYFALL_LIMITER, SCRYFALL_BREAKER)
        def get_card_data():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not breaker.is_available():
                raise RuntimeError(
                    f"Service circuit breaker is {breaker.state}"
                )
            
            limiter.wait_if_needed()
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
        
        return wrapper
    return decorator
