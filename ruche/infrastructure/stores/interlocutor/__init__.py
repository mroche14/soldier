"""InterlocutorDataStore for managing customer/user data.

Manages customer profiles, fields, assets, channel identities, and schema definitions.
Formerly known as InterlocutorDataStore.
"""

from ruche.infrastructure.stores.interlocutor.cached import InterlocutorDataStoreCacheLayer
from ruche.infrastructure.stores.interlocutor.inmemory import InMemoryInterlocutorDataStore
from ruche.infrastructure.stores.interlocutor.interface import InterlocutorDataStore
from ruche.infrastructure.stores.interlocutor.postgres import PostgresInterlocutorDataStore

__all__ = [
    "InterlocutorDataStore",
    "InMemoryInterlocutorDataStore",
    "PostgresInterlocutorDataStore",
    "InterlocutorDataStoreCacheLayer",
]
