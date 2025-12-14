"""Tests for CustomerSchemaMask model."""

import pytest

from ruche.alignment.context.customer_schema_mask import (
    CustomerSchemaMask,
    CustomerSchemaMaskEntry,
)


class TestCustomerSchemaMaskEntry:
    """Test suite for CustomerSchemaMaskEntry model."""

    def test_create_entry(self):
        """Test creating a schema mask entry."""
        entry = CustomerSchemaMaskEntry(
            scope="IDENTITY",
            type="string",
            exists=True,
            display_name="Email Address",
        )

        assert entry.scope == "IDENTITY"
        assert entry.type == "string"
        assert entry.exists is True
        assert entry.display_name == "Email Address"

    def test_create_without_display_name(self):
        """Test creating entry without display name."""
        entry = CustomerSchemaMaskEntry(
            scope="SESSION",
            type="number",
            exists=False,
        )

        assert entry.scope == "SESSION"
        assert entry.exists is False
        assert entry.display_name is None


class TestCustomerSchemaMask:
    """Test suite for CustomerSchemaMask model."""

    def test_create_empty_mask(self):
        """Test creating empty schema mask."""
        mask = CustomerSchemaMask(variables={})
        assert len(mask.variables) == 0

    def test_create_with_variables(self):
        """Test creating schema mask with variables."""
        mask = CustomerSchemaMask(
            variables={
                "email": CustomerSchemaMaskEntry(
                    scope="IDENTITY",
                    type="email",
                    exists=True,
                    display_name="Email",
                ),
                "order_id": CustomerSchemaMaskEntry(
                    scope="CASE",
                    type="string",
                    exists=False,
                    display_name="Order ID",
                ),
            }
        )

        assert len(mask.variables) == 2
        assert "email" in mask.variables
        assert "order_id" in mask.variables
        assert mask.variables["email"].exists is True
        assert mask.variables["order_id"].exists is False
