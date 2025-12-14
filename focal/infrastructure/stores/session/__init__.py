"""SessionStore for managing conversational session state.

Manages session state with support for channel-based lookup and status filtering.
"""

from focal.infrastructure.stores.session.interface import SessionStore
from focal.infrastructure.stores.session.inmemory import InMemorySessionStore
from focal.infrastructure.stores.session.redis import RedisSessionStore

__all__ = [
    "SessionStore",
    "InMemorySessionStore",
    "RedisSessionStore",
]
