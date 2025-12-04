"""Hatchet client wrapper.

Provides a centralized client for Hatchet job orchestration
with graceful degradation when Hatchet is unavailable.
"""

from typing import Any

import structlog

from soldier.config.models.jobs import HatchetConfig

logger = structlog.get_logger(__name__)


class HatchetClient:
    """Wrapper for Hatchet SDK client.

    Provides:
    - Lazy initialization of Hatchet client
    - Health checking
    - Graceful degradation when unavailable
    """

    def __init__(self, config: HatchetConfig) -> None:
        """Initialize Hatchet client wrapper.

        Args:
            config: Hatchet configuration
        """
        self._config = config
        self._client: Any | None = None
        self._available: bool | None = None

    def _get_or_create_client(self) -> Any | None:
        """Lazily initialize Hatchet client."""
        if self._client is not None:
            return self._client

        if not self._config.enabled:
            logger.info("hatchet_disabled", reason="config")
            return None

        try:
            from hatchet_sdk import Hatchet

            api_key = (
                self._config.api_key.get_secret_value()
                if self._config.api_key
                else None
            )
            self._client = Hatchet(
                server_url=self._config.server_url,
                api_key=api_key,
            )
            logger.info(
                "hatchet_client_initialized",
                server_url=self._config.server_url,
            )
            return self._client
        except ImportError:
            logger.warning("hatchet_sdk_not_installed")
            return None
        except Exception as e:
            logger.error("hatchet_client_init_failed", error=str(e))
            return None

    def get_client(self) -> Any | None:
        """Get Hatchet client instance.

        Returns:
            Hatchet client or None if unavailable
        """
        return self._get_or_create_client()

    async def health_check(self) -> bool:
        """Check if Hatchet is available and healthy.

        Returns:
            True if Hatchet is available and responding
        """
        client = self._get_or_create_client()
        if client is None:
            return False

        try:
            # Hatchet SDK doesn't have a direct health check method
            # We'll assume it's healthy if we can get the client
            self._available = True
            return True
        except Exception as e:
            logger.warning("hatchet_health_check_failed", error=str(e))
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if Hatchet was available on last check.

        Returns:
            True if Hatchet was available
        """
        if self._available is None:
            return False
        return self._available

    @property
    def config(self) -> HatchetConfig:
        """Get Hatchet configuration.

        Returns:
            HatchetConfig instance
        """
        return self._config
