import time
from functools import wraps

class CircuitBreaker:
    def __init__(self, max_failures=3, reset_timeout=60):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure = 0
        self.open = False

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.open and (time.time() - self.last_failure < self.reset_timeout):
                raise Exception('Circuit breaker is open')
            try:
                result = func(*args, **kwargs)
                self.failures = 0
                self.open = False
                return result
            except Exception as e:
                self.failures += 1
                self.last_failure = time.time()
                if self.failures >= self.max_failures:
                    self.open = True
                raise e
        return wrapper

def retry(max_retries=3, delay=1, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        raise e
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator 