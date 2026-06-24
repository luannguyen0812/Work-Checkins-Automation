from functools import lru_cache
from datastore.models import Config
from datastore.sheets import get_config as _get_config


@lru_cache(maxsize=1)
def load_config() -> Config:
    return _get_config()


def refresh_config() -> Config:
    load_config.cache_clear()
    return load_config()
