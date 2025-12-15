"""PostgreSQL implementation of InterlocutorDataStoreInterface.

Enhanced with:
- Status-aware queries
- Lineage traversal (recursive CTE)
- Schema management
- Field history
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from ruche.conversation.models import Channel
from ruche.db.errors import ConnectionError
from ruche.db.pool import PostgresPool
from ruche.observability.logging import get_logger
from ruche.interlocutor_data.enums import (
    FallbackAction,
    ItemStatus,
    VariableSource,
    RequiredLevel,
    SourceType,
    ValidationMode,
    VerificationLevel,
)
from ruche.interlocutor_data.models import (
    ChannelIdentity,
    InterlocutorDataStore,
    ProfileAsset,
    VariableEntry,
    InterlocutorDataField,
    ScenarioFieldRequirement,
)
from ruche.interlocutor_data.store import InterlocutorDataStoreInterface

logger = get_logger(__name__)


class PostgresInterlocutorDataStore(InterlocutorDataStoreInterface):
    """PostgreSQL implementation of InterlocutorDataStoreInterface.

    Enhanced with:
    - Status-aware queries
    - Lineage traversal (recursive CTE)
    - Schema management
    - Field history
    """

    def __init__(self, pool: PostgresPool) -> None:
        """Initialize with connection pool."""
        self._pool = pool

    # =========================================================================
    # PROFILE CRUD
    # =========================================================================

    async def get_by_interlocutor_id(
        self,
        tenant_id: UUID,
        interlocutor_id: UUID,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by customer ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, tenant_id, external_id, created_at, updated_at, merged_into_id
                    FROM customer_profiles
                    WHERE tenant_id = $1 AND id = $2 AND merged_into_id IS NULL
                    """,
                    tenant_id,
                    interlocutor_id,
                )
                if row:
                    return await self._load_full_profile(conn, row, include_history)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_by_interlocutor_id_error",
                interlocutor_id=str(interlocutor_id),
                error=str(e),
            )
            raise ConnectionError(f"Failed to get profile: {e}", cause=e) from e

    async def get_by_id(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by profile ID."""
        return await self.get_by_interlocutor_id(tenant_id, profile_id, include_history=include_history)

    async def get_by_channel_identity(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
        *,
        include_history: bool = False,
    ) -> InterlocutorDataStore | None:
        """Get profile by channel identity."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT p.id, p.tenant_id, p.external_id, p.created_at, p.updated_at, p.merged_into_id
                    FROM customer_profiles p
                    JOIN channel_identities c ON p.id = c.profile_id
                    WHERE p.tenant_id = $1 AND c.channel = $2 AND c.channel_user_id = $3
                      AND p.merged_into_id IS NULL
                    """,
                    tenant_id,
                    channel.value,
                    channel_user_id,
                )
                if row:
                    return await self._load_full_profile(conn, row, include_history)
                return None
        except Exception as e:
            logger.error(
                "postgres_get_by_channel_identity_error",
                channel=channel.value,
                error=str(e),
            )
            raise ConnectionError(f"Failed to get profile: {e}", cause=e) from e

    async def get_or_create(
        self,
        tenant_id: UUID,
        channel: Channel,
        channel_user_id: str,
    ) -> InterlocutorDataStore:
        """Get existing profile or create new one for channel identity."""
        existing = await self.get_by_channel_identity(tenant_id, channel, channel_user_id)
        if existing:
            return existing

        profile = InterlocutorDataStore(
            id=uuid4(),
            tenant_id=tenant_id,
            interlocutor_id=uuid4(),
            channel_identities=[
                ChannelIdentity(
                    channel=channel,
                    channel_user_id=channel_user_id,
                    verified=False,
                    primary=True,
                )
            ],
        )

        await self.save(profile)
        return profile

    async def save(self, profile: InterlocutorDataStore) -> UUID:
        """Save a profile."""
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO customer_profiles (
                            id, tenant_id, external_id, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (id) DO UPDATE SET
                            external_id = EXCLUDED.external_id,
                            updated_at = NOW()
                        """,
                        profile.id,
                        profile.tenant_id,
                        None,
                        profile.created_at,
                        datetime.now(UTC),
                    )

                    for identity in profile.channel_identities:
                        await conn.execute(
                            """
                            INSERT INTO channel_identities (
                                id, tenant_id, profile_id, channel, channel_user_id, verified, created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (tenant_id, channel, channel_user_id) DO UPDATE SET
                                verified = EXCLUDED.verified
                            """,
                            uuid4(),
                            profile.tenant_id,
                            profile.id,
                            identity.channel.value,
                            identity.channel_user_id,
                            identity.verified,
                            datetime.now(UTC),
                        )

                    return profile.id
        except Exception as e:
            logger.error("postgres_save_profile_error", error=str(e))
            raise ConnectionError(f"Failed to save profile: {e}", cause=e) from e

    async def delete(self, tenant_id: UUID, profile_id: UUID) -> bool:
        """Soft-delete a profile."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE customer_profiles
                    SET merged_into_id = '00000000-0000-0000-0000-000000000000', updated_at = NOW()
                    WHERE tenant_id = $1 AND id = $2 AND merged_into_id IS NULL
                    """,
                    tenant_id,
                    profile_id,
                )
                return "UPDATE 1" in result
        except Exception as e:
            logger.error("postgres_delete_profile_error", error=str(e))
            raise ConnectionError(f"Failed to delete profile: {e}", cause=e) from e

    # =========================================================================
    # FIELD OPERATIONS (Enhanced with Status)
    # =========================================================================

    async def update_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field: VariableEntry,
        *,
        supersede_existing: bool = True,
    ) -> UUID:
        """Update a profile field with supersession support."""
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    # Mark existing active field as superseded
                    if supersede_existing:
                        await conn.execute(
                            """
                            UPDATE profile_fields
                            SET status = 'superseded',
                                superseded_by_id = $1,
                                superseded_at = NOW()
                            WHERE tenant_id = $2 AND profile_id = $3
                              AND field_name = $4 AND status = 'active'
                            """,
                            field.id,
                            tenant_id,
                            profile_id,
                            field.name,
                        )

                    # Insert new field
                    source_str = field.source.value if hasattr(field.source, 'value') else str(field.source)
                    source_item_type_str = field.source_item_type.value if field.source_item_type else None

                    await conn.execute(
                        """
                        INSERT INTO profile_fields (
                            id, tenant_id, profile_id, field_name, field_value,
                            source, confidence, verified, valid_from, status,
                            source_item_id, source_item_type, source_metadata,
                            field_definition_id, expires_at
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, 'active',
                            $10, $11, $12, $13, $14
                        )
                        """,
                        field.id,
                        tenant_id,
                        profile_id,
                        field.name,
                        json.dumps(field.value) if not isinstance(field.value, str) else field.value,
                        source_str,
                        field.confidence,
                        field.verified,
                        field.collected_at,
                        field.source_item_id,
                        source_item_type_str,
                        json.dumps(field.source_metadata),
                        field.field_definition_id,
                        field.expires_at,
                    )

                    return field.id
        except Exception as e:
            logger.error("postgres_update_field_error", error=str(e))
            raise ConnectionError(f"Failed to update field: {e}", cause=e) from e

    async def get_field(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> VariableEntry | None:
        """Get a specific field by name."""
        try:
            async with self._pool.acquire() as conn:
                if status:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM profile_fields
                        WHERE tenant_id = $1 AND profile_id = $2
                          AND field_name = $3 AND status = $4
                        ORDER BY valid_from DESC LIMIT 1
                        """,
                        tenant_id,
                        profile_id,
                        field_name,
                        status.value,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM profile_fields
                        WHERE tenant_id = $1 AND profile_id = $2 AND field_name = $3
                        ORDER BY valid_from DESC LIMIT 1
                        """,
                        tenant_id,
                        profile_id,
                        field_name,
                    )

                if row:
                    return self._row_to_field(row)
                return None
        except Exception as e:
            logger.error("postgres_get_field_error", error=str(e))
            raise ConnectionError(f"Failed to get field: {e}", cause=e) from e

    async def get_field_history(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        field_name: str,
    ) -> list[VariableEntry]:
        """Get all versions of a field."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM profile_fields
                    WHERE tenant_id = $1 AND profile_id = $2 AND field_name = $3
                    ORDER BY valid_from DESC
                    """,
                    tenant_id,
                    profile_id,
                    field_name,
                )
                return [self._row_to_field(row) for row in rows]
        except Exception as e:
            logger.error("postgres_get_field_history_error", error=str(e))
            raise ConnectionError(f"Failed to get field history: {e}", cause=e) from e

    async def expire_stale_fields(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark fields past expires_at as expired."""
        try:
            async with self._pool.acquire() as conn:
                if profile_id:
                    result = await conn.execute(
                        """
                        UPDATE profile_fields
                        SET status = 'expired'
                        WHERE tenant_id = $1 AND profile_id = $2
                          AND status = 'active' AND expires_at < NOW()
                        """,
                        tenant_id,
                        profile_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE profile_fields
                        SET status = 'expired'
                        WHERE tenant_id = $1 AND status = 'active' AND expires_at < NOW()
                        """,
                        tenant_id,
                    )
                # Parse "UPDATE N" to get count
                count = int(result.split()[-1]) if result.startswith("UPDATE") else 0
                return count
        except Exception as e:
            logger.error("postgres_expire_stale_fields_error", error=str(e))
            raise ConnectionError(f"Failed to expire stale fields: {e}", cause=e) from e

    async def mark_orphaned_items(
        self,
        tenant_id: UUID,
        profile_id: UUID | None = None,
    ) -> int:
        """Mark items whose source was deleted as orphaned."""
        try:
            async with self._pool.acquire() as conn:
                count = 0

                # Mark orphaned fields
                if profile_id:
                    result = await conn.execute(
                        """
                        UPDATE profile_fields f
                        SET status = 'orphaned'
                        WHERE f.tenant_id = $1 AND f.profile_id = $2
                          AND f.status = 'active'
                          AND f.source_item_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_fields s
                              WHERE s.id = f.source_item_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_assets s
                              WHERE s.id = f.source_item_id
                          )
                        """,
                        tenant_id,
                        profile_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE profile_fields f
                        SET status = 'orphaned'
                        WHERE f.tenant_id = $1 AND f.status = 'active'
                          AND f.source_item_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_fields s
                              WHERE s.id = f.source_item_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_assets s
                              WHERE s.id = f.source_item_id
                          )
                        """,
                        tenant_id,
                    )

                count += int(result.split()[-1]) if result.startswith("UPDATE") else 0

                # Mark orphaned assets (similar logic)
                if profile_id:
                    result = await conn.execute(
                        """
                        UPDATE profile_assets a
                        SET status = 'orphaned'
                        WHERE a.tenant_id = $1 AND a.profile_id = $2
                          AND a.status = 'active'
                          AND a.source_item_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_fields s
                              WHERE s.id = a.source_item_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_assets s
                              WHERE s.id = a.source_item_id
                          )
                        """,
                        tenant_id,
                        profile_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE profile_assets a
                        SET status = 'orphaned'
                        WHERE a.tenant_id = $1 AND a.status = 'active'
                          AND a.source_item_id IS NOT NULL
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_fields s
                              WHERE s.id = a.source_item_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM profile_assets s
                              WHERE s.id = a.source_item_id
                          )
                        """,
                        tenant_id,
                    )

                count += int(result.split()[-1]) if result.startswith("UPDATE") else 0
                return count
        except Exception as e:
            logger.error("postgres_mark_orphaned_items_error", error=str(e))
            raise ConnectionError(f"Failed to mark orphaned items: {e}", cause=e) from e

    # =========================================================================
    # ASSET OPERATIONS
    # =========================================================================

    async def add_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset: ProfileAsset,
        *,
        supersede_existing: bool = False,
    ) -> UUID:
        """Add an asset to profile."""
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    if supersede_existing:
                        await conn.execute(
                            """
                            UPDATE profile_assets
                            SET status = 'superseded',
                                superseded_by_id = $1,
                                superseded_at = NOW()
                            WHERE tenant_id = $2 AND profile_id = $3
                              AND asset_type = $4 AND status = 'active'
                            """,
                            asset.id,
                            tenant_id,
                            profile_id,
                            asset.asset_type,
                        )

                    source_item_type_str = asset.source_item_type.value if asset.source_item_type else None

                    await conn.execute(
                        """
                        INSERT INTO profile_assets (
                            id, tenant_id, profile_id, asset_type, asset_reference,
                            metadata, created_at, status, source_item_id, source_item_type,
                            derived_from_tool, analysis_field_ids
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, 'active', $8, $9, $10, $11
                        )
                        """,
                        asset.id,
                        tenant_id,
                        profile_id,
                        asset.asset_type,
                        asset.storage_path,
                        json.dumps({
                            "name": asset.name,
                            "storage_provider": asset.storage_provider,
                            "mime_type": asset.mime_type,
                            "size_bytes": asset.size_bytes,
                            "checksum": asset.checksum,
                        }),
                        asset.uploaded_at,
                        asset.source_item_id,
                        source_item_type_str,
                        asset.derived_from_tool,
                        list(asset.analysis_field_ids) if asset.analysis_field_ids else [],
                    )

                    return asset.id
        except Exception as e:
            logger.error("postgres_add_asset_error", error=str(e))
            raise ConnectionError(f"Failed to add asset: {e}", cause=e) from e

    async def get_asset(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_id: UUID,
    ) -> ProfileAsset | None:
        """Get a specific asset by ID."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM profile_assets
                    WHERE tenant_id = $1 AND profile_id = $2 AND id = $3
                    """,
                    tenant_id,
                    profile_id,
                    asset_id,
                )
                if row:
                    return self._row_to_asset(row)
                return None
        except Exception as e:
            logger.error("postgres_get_asset_error", error=str(e))
            raise ConnectionError(f"Failed to get asset: {e}", cause=e) from e

    async def get_asset_by_name(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        asset_name: str,
        *,
        status: ItemStatus | None = ItemStatus.ACTIVE,
    ) -> ProfileAsset | None:
        """Get asset by name with optional status filter."""
        try:
            async with self._pool.acquire() as conn:
                if status:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM profile_assets
                        WHERE tenant_id = $1 AND profile_id = $2 AND status = $3
                          AND metadata->>'name' = $4
                        ORDER BY created_at DESC LIMIT 1
                        """,
                        tenant_id,
                        profile_id,
                        status.value,
                        asset_name,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM profile_assets
                        WHERE tenant_id = $1 AND profile_id = $2
                          AND metadata->>'name' = $3
                        ORDER BY created_at DESC LIMIT 1
                        """,
                        tenant_id,
                        profile_id,
                        asset_name,
                    )
                if row:
                    return self._row_to_asset(row)
                return None
        except Exception as e:
            logger.error("postgres_get_asset_by_name_error", error=str(e))
            raise ConnectionError(f"Failed to get asset: {e}", cause=e) from e

    # =========================================================================
    # LINEAGE OPERATIONS (Using Recursive CTE)
    # =========================================================================

    async def get_derivation_chain(
        self,
        tenant_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> list[dict[str, Any]]:
        """Get full derivation chain using recursive CTE."""
        try:
            async with self._pool.acquire() as conn:
                # Use recursive CTE to traverse lineage
                rows = await conn.fetch(
                    """
                    WITH RECURSIVE lineage AS (
                        -- Base case: start with the item
                        SELECT
                            id, 'profile_field' as type, field_name as name,
                            source_metadata, source_item_id, source_item_type, 0 as depth
                        FROM profile_fields
                        WHERE tenant_id = $1 AND id = $2 AND $3 = 'profile_field'

                        UNION ALL

                        SELECT
                            id, 'profile_asset' as type, metadata->>'name' as name,
                            '{}'::jsonb as source_metadata, source_item_id, source_item_type, 0 as depth
                        FROM profile_assets
                        WHERE tenant_id = $1 AND id = $2 AND $3 = 'profile_asset'

                        UNION ALL

                        -- Recursive case: follow source_item_id links
                        SELECT
                            f.id, 'profile_field', f.field_name,
                            f.source_metadata, f.source_item_id, f.source_item_type, l.depth + 1
                        FROM profile_fields f
                        JOIN lineage l ON f.id = l.source_item_id AND l.source_item_type = 'profile_field'
                        WHERE f.tenant_id = $1 AND l.depth < 10

                        UNION ALL

                        SELECT
                            a.id, 'profile_asset', a.metadata->>'name',
                            '{}'::jsonb, a.source_item_id, a.source_item_type, l.depth + 1
                        FROM profile_assets a
                        JOIN lineage l ON a.id = l.source_item_id AND l.source_item_type = 'profile_asset'
                        WHERE a.tenant_id = $1 AND l.depth < 10
                    )
                    SELECT * FROM lineage ORDER BY depth DESC
                    """,
                    tenant_id,
                    item_id,
                    item_type,
                )

                return [
                    {
                        "id": str(row["id"]),
                        "type": row["type"],
                        "name": row["name"],
                        "source_metadata": json.loads(row["source_metadata"])
                        if isinstance(row["source_metadata"], str)
                        else row["source_metadata"] or {},
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error("postgres_get_derivation_chain_error", error=str(e))
            raise ConnectionError(f"Failed to get derivation chain: {e}", cause=e) from e

    async def get_derived_items(
        self,
        tenant_id: UUID,
        source_item_id: UUID,
    ) -> dict[str, list[Any]]:
        """Get all items derived from a source."""
        try:
            async with self._pool.acquire() as conn:
                field_rows = await conn.fetch(
                    """
                    SELECT * FROM profile_fields
                    WHERE tenant_id = $1 AND source_item_id = $2
                    """,
                    tenant_id,
                    source_item_id,
                )

                asset_rows = await conn.fetch(
                    """
                    SELECT * FROM profile_assets
                    WHERE tenant_id = $1 AND source_item_id = $2
                    """,
                    tenant_id,
                    source_item_id,
                )

                return {
                    "fields": [self._row_to_field(row) for row in field_rows],
                    "assets": [self._row_to_asset(row) for row in asset_rows],
                }
        except Exception as e:
            logger.error("postgres_get_derived_items_error", error=str(e))
            raise ConnectionError(f"Failed to get derived items: {e}", cause=e) from e

    async def check_has_dependents(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Check if an item has dependent derived items."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM profile_fields WHERE tenant_id = $1 AND source_item_id = $2
                        UNION ALL
                        SELECT 1 FROM profile_assets WHERE tenant_id = $1 AND source_item_id = $2
                    ) as has_dependents
                    """,
                    tenant_id,
                    item_id,
                )
                return row["has_dependents"] if row else False
        except Exception as e:
            logger.error("postgres_check_has_dependents_error", error=str(e))
            raise ConnectionError(f"Failed to check dependents: {e}", cause=e) from e

    # =========================================================================
    # CHANNEL OPERATIONS
    # =========================================================================

    async def link_channel(
        self,
        tenant_id: UUID,
        profile_id: UUID,
        identity: ChannelIdentity,
    ) -> bool:
        """Link a new channel identity to profile."""
        try:
            async with self._pool.acquire() as conn:
                # Check if already linked to another profile
                existing = await conn.fetchrow(
                    """
                    SELECT profile_id FROM channel_identities
                    WHERE tenant_id = $1 AND channel = $2 AND channel_user_id = $3
                    """,
                    tenant_id,
                    identity.channel.value,
                    identity.channel_user_id,
                )

                if existing and existing["profile_id"] != profile_id:
                    return False

                await conn.execute(
                    """
                    INSERT INTO channel_identities (
                        id, tenant_id, profile_id, channel, channel_user_id, verified, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (tenant_id, channel, channel_user_id) DO UPDATE SET
                        profile_id = EXCLUDED.profile_id,
                        verified = EXCLUDED.verified
                    """,
                    uuid4(),
                    tenant_id,
                    profile_id,
                    identity.channel.value,
                    identity.channel_user_id,
                    identity.verified,
                    datetime.now(UTC),
                )
                return True
        except Exception as e:
            logger.error("postgres_link_channel_error", error=str(e))
            raise ConnectionError(f"Failed to link channel: {e}", cause=e) from e

    async def merge_profiles(
        self,
        tenant_id: UUID,
        source_profile_id: UUID,
        target_profile_id: UUID,
    ) -> bool:
        """Merge source profile into target profile."""
        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    # Move channel identities
                    await conn.execute(
                        """
                        UPDATE channel_identities
                        SET profile_id = $1
                        WHERE tenant_id = $2 AND profile_id = $3
                        """,
                        target_profile_id,
                        tenant_id,
                        source_profile_id,
                    )

                    # Move profile fields
                    await conn.execute(
                        """
                        UPDATE profile_fields
                        SET profile_id = $1
                        WHERE tenant_id = $2 AND profile_id = $3
                        """,
                        target_profile_id,
                        tenant_id,
                        source_profile_id,
                    )

                    # Move assets
                    await conn.execute(
                        """
                        UPDATE profile_assets
                        SET profile_id = $1
                        WHERE tenant_id = $2 AND profile_id = $3
                        """,
                        target_profile_id,
                        tenant_id,
                        source_profile_id,
                    )

                    # Mark source as merged
                    await conn.execute(
                        """
                        UPDATE customer_profiles
                        SET merged_into_id = $1, updated_at = NOW()
                        WHERE tenant_id = $2 AND id = $3
                        """,
                        target_profile_id,
                        tenant_id,
                        source_profile_id,
                    )

                    return True
        except Exception as e:
            logger.error("postgres_merge_profiles_error", error=str(e))
            raise ConnectionError(f"Failed to merge profiles: {e}", cause=e) from e

    # =========================================================================
    # SCHEMA OPERATIONS
    # =========================================================================

    async def get_field_definitions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        enabled_only: bool = True,
    ) -> list[InterlocutorDataField]:
        """Get all field definitions for an agent."""
        try:
            async with self._pool.acquire() as conn:
                if enabled_only:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM profile_field_definitions
                        WHERE tenant_id = $1 AND agent_id = $2 AND enabled = true
                        """,
                        tenant_id,
                        agent_id,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM profile_field_definitions
                        WHERE tenant_id = $1 AND agent_id = $2
                        """,
                        tenant_id,
                        agent_id,
                    )

                return [self._row_to_field_definition(row) for row in rows]
        except Exception as e:
            logger.error("postgres_get_field_definitions_error", error=str(e))
            raise ConnectionError(f"Failed to get field definitions: {e}", cause=e) from e

    async def get_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> InterlocutorDataField | None:
        """Get a specific field definition by name."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM profile_field_definitions
                    WHERE tenant_id = $1 AND agent_id = $2 AND name = $3
                    """,
                    tenant_id,
                    agent_id,
                    field_name,
                )
                if row:
                    return self._row_to_field_definition(row)
                return None
        except Exception as e:
            logger.error("postgres_get_field_definition_error", error=str(e))
            raise ConnectionError(f"Failed to get field definition: {e}", cause=e) from e

    async def save_field_definition(
        self,
        definition: InterlocutorDataField,
    ) -> UUID:
        """Save a field definition."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO profile_field_definitions (
                        id, tenant_id, agent_id, name, display_name, description,
                        value_type, validation_regex, validation_tool_id, allowed_values,
                        validation_mode, required_verification, verification_methods,
                        collection_prompt, extraction_examples, extraction_prompt_hint,
                        is_pii, encryption_required, retention_days, freshness_seconds,
                        enabled, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                    )
                    ON CONFLICT (tenant_id, agent_id, name) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        description = EXCLUDED.description,
                        value_type = EXCLUDED.value_type,
                        validation_regex = EXCLUDED.validation_regex,
                        validation_tool_id = EXCLUDED.validation_tool_id,
                        allowed_values = EXCLUDED.allowed_values,
                        validation_mode = EXCLUDED.validation_mode,
                        required_verification = EXCLUDED.required_verification,
                        verification_methods = EXCLUDED.verification_methods,
                        collection_prompt = EXCLUDED.collection_prompt,
                        extraction_examples = EXCLUDED.extraction_examples,
                        extraction_prompt_hint = EXCLUDED.extraction_prompt_hint,
                        is_pii = EXCLUDED.is_pii,
                        encryption_required = EXCLUDED.encryption_required,
                        retention_days = EXCLUDED.retention_days,
                        freshness_seconds = EXCLUDED.freshness_seconds,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    definition.id,
                    definition.tenant_id,
                    definition.agent_id,
                    definition.name,
                    definition.display_name,
                    definition.description,
                    definition.value_type,
                    definition.validation_regex,
                    definition.validation_tool_id,
                    list(definition.allowed_values) if definition.allowed_values else None,
                    definition.validation_mode.value,
                    definition.required_verification,
                    list(definition.verification_methods),
                    definition.collection_prompt,
                    list(definition.extraction_examples),
                    definition.extraction_prompt_hint,
                    definition.is_pii,
                    definition.encryption_required,
                    definition.retention_days,
                    definition.freshness_seconds,
                    definition.enabled,
                    datetime.now(UTC),
                    datetime.now(UTC),
                )
                return definition.id
        except Exception as e:
            logger.error("postgres_save_field_definition_error", error=str(e))
            raise ConnectionError(f"Failed to save field definition: {e}", cause=e) from e

    async def delete_field_definition(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        field_name: str,
    ) -> bool:
        """Delete a field definition."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM profile_field_definitions
                    WHERE tenant_id = $1 AND agent_id = $2 AND name = $3
                    """,
                    tenant_id,
                    agent_id,
                    field_name,
                )
                return "DELETE 1" in result
        except Exception as e:
            logger.error("postgres_delete_field_definition_error", error=str(e))
            raise ConnectionError(f"Failed to delete field definition: {e}", cause=e) from e

    # =========================================================================
    # SCENARIO REQUIREMENTS
    # =========================================================================

    async def get_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> list[ScenarioFieldRequirement]:
        """Get field requirements for a scenario/step."""
        try:
            async with self._pool.acquire() as conn:
                if step_id:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM scenario_field_requirements
                        WHERE tenant_id = $1 AND scenario_id = $2 AND step_id = $3
                        ORDER BY collection_order
                        """,
                        tenant_id,
                        scenario_id,
                        step_id,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM scenario_field_requirements
                        WHERE tenant_id = $1 AND scenario_id = $2
                        ORDER BY collection_order
                        """,
                        tenant_id,
                        scenario_id,
                    )

                return [self._row_to_scenario_requirement(row) for row in rows]
        except Exception as e:
            logger.error("postgres_get_scenario_requirements_error", error=str(e))
            raise ConnectionError(f"Failed to get scenario requirements: {e}", cause=e) from e

    async def save_scenario_requirement(
        self,
        requirement: ScenarioFieldRequirement,
    ) -> UUID:
        """Save a scenario field requirement."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO scenario_field_requirements (
                        id, tenant_id, agent_id, scenario_id, step_id, field_name,
                        required_level, fallback_action, collection_order,
                        condition_expression, requires_human_review, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        field_name = EXCLUDED.field_name,
                        required_level = EXCLUDED.required_level,
                        fallback_action = EXCLUDED.fallback_action,
                        collection_order = EXCLUDED.collection_order,
                        condition_expression = EXCLUDED.condition_expression,
                        requires_human_review = EXCLUDED.requires_human_review,
                        updated_at = NOW()
                    """,
                    requirement.id,
                    requirement.tenant_id,
                    requirement.agent_id,
                    requirement.scenario_id,
                    requirement.step_id,
                    requirement.field_name,
                    requirement.required_level.value,
                    requirement.fallback_action.value,
                    requirement.collection_order,
                    requirement.condition_expression,
                    requirement.requires_human_review,
                    datetime.now(UTC),
                    datetime.now(UTC),
                )
                return requirement.id
        except Exception as e:
            logger.error("postgres_save_scenario_requirement_error", error=str(e))
            raise ConnectionError(f"Failed to save scenario requirement: {e}", cause=e) from e

    async def delete_scenario_requirements(
        self,
        tenant_id: UUID,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
    ) -> int:
        """Delete requirements for a scenario/step."""
        try:
            async with self._pool.acquire() as conn:
                if step_id:
                    result = await conn.execute(
                        """
                        DELETE FROM scenario_field_requirements
                        WHERE tenant_id = $1 AND scenario_id = $2 AND step_id = $3
                        """,
                        tenant_id,
                        scenario_id,
                        step_id,
                    )
                else:
                    result = await conn.execute(
                        """
                        DELETE FROM scenario_field_requirements
                        WHERE tenant_id = $1 AND scenario_id = $2
                        """,
                        tenant_id,
                        scenario_id,
                    )

                return int(result.split()[-1]) if result.startswith("DELETE") else 0
        except Exception as e:
            logger.error("postgres_delete_scenario_requirements_error", error=str(e))
            raise ConnectionError(f"Failed to delete scenario requirements: {e}", cause=e) from e

    async def get_missing_fields(
        self,
        tenant_id: UUID,
        profile: InterlocutorDataStore,
        scenario_id: UUID,
        *,
        step_id: UUID | None = None,
        required_level: str | None = "hard",
    ) -> list[ScenarioFieldRequirement]:
        """Get requirements not satisfied by the profile."""
        requirements = await self.get_scenario_requirements(
            tenant_id, scenario_id, step_id=step_id
        )

        missing = []
        for req in requirements:
            if required_level and req.required_level.value != required_level:
                continue

            field = profile.fields.get(req.field_name)
            if not field or field.status != ItemStatus.ACTIVE:
                missing.append(req)
                continue

            # Check freshness
            definition = await self.get_field_definition(
                tenant_id, profile.tenant_id, req.field_name
            )
            if definition and definition.freshness_seconds:
                age = (datetime.now(UTC) - field.collected_at).total_seconds()
                if age > definition.freshness_seconds:
                    missing.append(req)
                    continue

            # Check verification
            if definition and definition.required_verification and not field.verified:
                missing.append(req)

        return missing

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _row_to_field(self, row) -> VariableEntry:
        """Convert database row to VariableEntry."""
        source_map = {
            "USER_PROVIDED": VariableSource.USER_PROVIDED,
            "user_provided": VariableSource.USER_PROVIDED,
            "EXTRACTED": VariableSource.LLM_EXTRACTED,
            "llm_extracted": VariableSource.LLM_EXTRACTED,
            "tool_result": VariableSource.TOOL_RESULT,
            "document_extracted": VariableSource.DOCUMENT_EXTRACTED,
            "human_entered": VariableSource.HUMAN_ENTERED,
            "INFERRED": VariableSource.SYSTEM_INFERRED,
            "system_inferred": VariableSource.SYSTEM_INFERRED,
            "SYSTEM": VariableSource.SYSTEM_INFERRED,
        }

        status_map = {
            "active": ItemStatus.ACTIVE,
            "superseded": ItemStatus.SUPERSEDED,
            "expired": ItemStatus.EXPIRED,
            "orphaned": ItemStatus.ORPHANED,
        }

        source_type_map = {
            "profile_field": SourceType.PROFILE_FIELD,
            "profile_asset": SourceType.PROFILE_ASSET,
            "session": SourceType.SESSION,
            "tool": SourceType.TOOL,
            "external": SourceType.EXTERNAL,
        }

        return VariableEntry(
            id=row["id"],
            name=row["field_name"],
            value=row["field_value"],
            value_type="string",
            source=source_map.get(row["source"], VariableSource.LLM_EXTRACTED),
            confidence=row.get("confidence", 1.0) or 1.0,
            verified=row.get("verified", False) or False,
            collected_at=row["valid_from"],
            updated_at=row["valid_from"],
            status=status_map.get(row.get("status", "active"), ItemStatus.ACTIVE),
            source_item_id=row.get("source_item_id"),
            source_item_type=source_type_map.get(row.get("source_item_type"))
            if row.get("source_item_type")
            else None,
            source_metadata=json.loads(row.get("source_metadata", "{}"))
            if isinstance(row.get("source_metadata"), str)
            else row.get("source_metadata", {}),
            superseded_by_id=row.get("superseded_by_id"),
            superseded_at=row.get("superseded_at"),
            field_definition_id=row.get("field_definition_id"),
            expires_at=row.get("expires_at"),
        )

    def _row_to_asset(self, row) -> ProfileAsset:
        """Convert database row to ProfileAsset."""
        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}

        status_map = {
            "active": ItemStatus.ACTIVE,
            "superseded": ItemStatus.SUPERSEDED,
            "expired": ItemStatus.EXPIRED,
            "orphaned": ItemStatus.ORPHANED,
        }

        source_type_map = {
            "profile_field": SourceType.PROFILE_FIELD,
            "profile_asset": SourceType.PROFILE_ASSET,
            "session": SourceType.SESSION,
            "tool": SourceType.TOOL,
            "external": SourceType.EXTERNAL,
        }

        return ProfileAsset(
            id=row["id"],
            name=metadata.get("name", ""),
            asset_type=row["asset_type"],
            storage_provider=metadata.get("storage_provider", ""),
            storage_path=row["asset_reference"],
            mime_type=metadata.get("mime_type", ""),
            size_bytes=metadata.get("size_bytes", 0),
            checksum=metadata.get("checksum", ""),
            uploaded_at=row["created_at"],
            status=status_map.get(row.get("status", "active"), ItemStatus.ACTIVE),
            source_item_id=row.get("source_item_id"),
            source_item_type=source_type_map.get(row.get("source_item_type"))
            if row.get("source_item_type")
            else None,
            derived_from_tool=row.get("derived_from_tool"),
            analysis_field_ids=list(row.get("analysis_field_ids", [])),
            superseded_by_id=row.get("superseded_by_id"),
            superseded_at=row.get("superseded_at"),
        )

    def _row_to_field_definition(self, row) -> InterlocutorDataField:
        """Convert database row to InterlocutorDataField."""
        validation_mode_map = {
            "strict": ValidationMode.STRICT,
            "warn": ValidationMode.WARN,
            "disabled": ValidationMode.DISABLED,
        }

        return InterlocutorDataField(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            display_name=row["display_name"],
            description=row.get("description"),
            value_type=row["value_type"],
            validation_regex=row.get("validation_regex"),
            validation_tool_id=row.get("validation_tool_id"),
            allowed_values=list(row["allowed_values"]) if row.get("allowed_values") else None,
            validation_mode=validation_mode_map.get(
                row.get("validation_mode", "strict"), ValidationMode.STRICT
            ),
            required_verification=row.get("required_verification", False),
            verification_methods=list(row.get("verification_methods", [])),
            collection_prompt=row.get("collection_prompt"),
            extraction_examples=list(row.get("extraction_examples", [])),
            extraction_prompt_hint=row.get("extraction_prompt_hint"),
            is_pii=row.get("is_pii", False),
            encryption_required=row.get("encryption_required", False),
            retention_days=row.get("retention_days"),
            freshness_seconds=row.get("freshness_seconds"),
            enabled=row.get("enabled", True),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _row_to_scenario_requirement(self, row) -> ScenarioFieldRequirement:
        """Convert database row to ScenarioFieldRequirement."""
        required_level_map = {
            "hard": RequiredLevel.HARD,
            "soft": RequiredLevel.SOFT,
        }

        fallback_action_map = {
            "ask": FallbackAction.ASK,
            "skip": FallbackAction.SKIP,
            "block": FallbackAction.BLOCK,
            "extract": FallbackAction.EXTRACT,
        }

        return ScenarioFieldRequirement(
            id=row["id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            scenario_id=row["scenario_id"],
            step_id=row.get("step_id"),
            field_name=row["field_name"],
            required_level=required_level_map.get(
                row.get("required_level", "hard"), RequiredLevel.HARD
            ),
            fallback_action=fallback_action_map.get(
                row.get("fallback_action", "ask"), FallbackAction.ASK
            ),
            collection_order=row.get("collection_order", 0),
            condition_expression=row.get("condition_expression"),
            requires_human_review=row.get("requires_human_review", False),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    async def _load_full_profile(
        self, conn, profile_row, include_history: bool = False
    ) -> InterlocutorDataStore:
        """Load full profile with all related data."""
        profile_id = profile_row["id"]
        tenant_id = profile_row["tenant_id"]

        # Load channel identities
        identity_rows = await conn.fetch(
            """
            SELECT channel, channel_user_id, verified, created_at
            FROM channel_identities
            WHERE tenant_id = $1 AND profile_id = $2
            """,
            tenant_id,
            profile_id,
        )
        channel_identities = [
            ChannelIdentity(
                channel=Channel(row["channel"]),
                channel_user_id=row["channel_user_id"],
                verified=row["verified"],
                primary=False,
            )
            for row in identity_rows
        ]
        if channel_identities:
            channel_identities[0].primary = True

        # Load active profile fields
        field_rows = await conn.fetch(
            """
            SELECT * FROM profile_fields
            WHERE tenant_id = $1 AND profile_id = $2 AND status = 'active'
            ORDER BY valid_from DESC
            """,
            tenant_id,
            profile_id,
        )

        fields = {}
        for row in field_rows:
            field_name = row["field_name"]
            if field_name not in fields:
                fields[field_name] = self._row_to_field(row)

        # Load active assets
        asset_rows = await conn.fetch(
            """
            SELECT * FROM profile_assets
            WHERE tenant_id = $1 AND profile_id = $2 AND status = 'active'
            """,
            tenant_id,
            profile_id,
        )
        assets = [self._row_to_asset(row) for row in asset_rows]

        return InterlocutorDataStore(
            id=profile_id,
            tenant_id=tenant_id,
            interlocutor_id=profile_id,
            channel_identities=channel_identities,
            fields=fields,
            assets=assets,
            verification_level=VerificationLevel.UNVERIFIED,
            consents=[],
            created_at=profile_row["created_at"],
            updated_at=profile_row["updated_at"],
        )
