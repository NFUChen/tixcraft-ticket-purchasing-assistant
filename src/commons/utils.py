import functools
import time

from loguru import logger


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Executed {func.__name__} in {execution_time:.4f} seconds")
        return result
    return wrapper