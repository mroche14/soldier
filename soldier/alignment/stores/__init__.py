"""Alignment stores for configuration data."""

from soldier.alignment.stores.config_store import ConfigStore
from soldier.alignment.stores.inmemory import InMemoryConfigStore

__all__ = [
    "ConfigStore",
    "InMemoryConfigStore",
]
