import asyncio
import logging
import traceback

logger = logging.getLogger(__name__)


def async_retry(
    retries: int = 1, parallel_executions: int = 1, catch_exceptions=(Exception,)
):
    """Async retry decorator.

    Examples:
        .. code-block:: python

            @async_retry(retries=3, parallel_executions=2)
            async def my_func():
                # Some code that may raise exceptions
                pass

    Args:
        retries (int): Number of retries.
        parallel_executions (int): Number of parallel executions.
        catch_exceptions (tuple): Tuple of exceptions to catch.
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                tasks = [func(*args, **kwargs) for _ in range(parallel_executions)]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if not isinstance(result, Exception):
                        return result
                    if isinstance(result, catch_exceptions):
                        last_exception = result
                        logger.error(
                            f"Attempt {attempt + 1} of {retries} failed with error: "
                            f"{type(result).__name__}, {str(result)}"
                        )
                        logger.debug(traceback.format_exc())

                logger.info(f"Retrying... (Attempt {attempt + 1} of {retries})")

            raise last_exception  # After all retries, raise the last caught exception

        return wrapper

    return decorator
