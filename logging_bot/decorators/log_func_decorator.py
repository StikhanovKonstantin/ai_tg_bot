from typing import Callable
import logging


logger = logging.getLogger(__name__)


def log_func_errors(logger: logging.Logger):
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                logger.debug(f'Функция `{func.__name__}` выполнена успешно.')
                return result
            except Exception as e:
                logger.error(
                    f'Ошибка в функции `{func.__name__}`: {e}.', exc_info=True
                )
        return wrapper
    return decorator


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
