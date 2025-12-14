"""Situational sensor for Phase 2.

Replaces basic ContextExtractor with schema-aware, glossary-aware
extraction that produces SituationSnapshot.
"""

import json
import re
from pathlib import Path
from typing import Any

from focal.alignment.context.customer_schema_mask import (
    CustomerSchemaMask,
    CustomerSchemaMaskEntry,
)
from focal.alignment.context.models import ScenarioSignal, Sentiment, Turn, Urgency
from focal.alignment.context.situation_snapshot import (
    CandidateVariableInfo,
    SituationSnapshot,
)
from focal.alignment.context.template_loader import TemplateLoader
from focal.alignment.models.glossary import GlossaryItem
from focal.config.models.pipeline import SituationSensorConfig
from focal.customer_data.models import CustomerDataField, CustomerDataStore
from focal.observability.logging import get_logger
from focal.providers.llm.base import LLMMessage
from focal.providers.llm.executor import LLMExecutor

logger = get_logger(__name__)


class SituationSensor:
    """Schema-aware, glossary-aware situation sensor (Phase 2).

    Produces SituationSnapshot with candidate variables for
    customer data updates.
    """

    def __init__(
        self,
        llm_executor: LLMExecutor,
        config: SituationSensorConfig,
    ):
        """Initialize situation sensor.

        Args:
            llm_executor: LLM executor for sensor calls
            config: Situational sensor configuration
        """
        self._executor = llm_executor
        self._config = config

        # Load Jinja2 template
        templates_dir = Path(__file__).parent / "prompts"
        self._template_loader = TemplateLoader(templates_dir)

    async def sense(
        self,
        message: str,
        history: list[Turn],
        customer_data_store: CustomerDataStore,
        customer_data_fields: dict[str, CustomerDataField],
        glossary_items: dict[str, GlossaryItem],
        previous_intent_label: str | None = None,
    ) -> SituationSnapshot:
        """Extract situation snapshot from message.

        Args:
            message: Current user message
            history: Conversation history
            customer_data_store: Customer data runtime storage
            customer_data_fields: Field name -> CustomerDataField definition
            glossary_items: Term -> GlossaryItem
            previous_intent_label: Previous canonical intent

        Returns:
            SituationSnapshot with extracted context and candidate variables
        """
        # P2.1: Build CustomerSchemaMask
        schema_mask = self._build_schema_mask(
            customer_data_store, customer_data_fields
        ) if self._config.include_schema_mask else None

        # P2.2: Build Glossary view
        glossary_view = self._build_glossary_view(
            glossary_items
        ) if self._config.include_glossary else None

        # P2.3: Build conversation window
        conversation_window = self._build_conversation_window(history)

        # P2.4: Call Sensor LLM
        llm_output = await self._call_sensor_llm(
            message=message,
            schema_mask=schema_mask,
            glossary_view=glossary_view,
            conversation_window=conversation_window,
            previous_intent_label=previous_intent_label,
        )

        # P2.5: Parse snapshot (includes message)
        snapshot = self._parse_snapshot(llm_output, message)

        # P2.6: Validate language
        snapshot.language = self._validate_language(snapshot.language, message)

        return snapshot

    def _build_schema_mask(
        self,
        customer_data_store: CustomerDataStore,
        customer_data_fields: dict[str, CustomerDataField],
    ) -> CustomerSchemaMask:
        """Build privacy-safe schema mask (P2.1).

        Shows which fields exist and whether they have values,
        but not the actual values.

        Args:
            customer_data_store: Customer data runtime storage
            customer_data_fields: Field definitions

        Returns:
            CustomerSchemaMask for LLM prompt
        """
        variables = {}

        for field_name, field_def in customer_data_fields.items():
            variables[field_name] = CustomerSchemaMaskEntry(
                scope=field_def.scope,
                type=field_def.value_type,
                exists=field_name in customer_data_store.fields,
                display_name=field_def.display_name,
            )

        return CustomerSchemaMask(variables=variables)

    def _build_glossary_view(
        self,
        glossary_items: dict[str, GlossaryItem],
    ) -> dict[str, GlossaryItem]:
        """Build glossary view for template (P2.2).

        Args:
            glossary_items: Term -> GlossaryItem

        Returns:
            Dict of glossary items for Jinja2 template
        """
        return glossary_items

    def _build_conversation_window(
        self,
        history: list[Turn],
    ) -> list[Turn]:
        """Build conversation window (P2.3).

        Args:
            history: Full conversation history

        Returns:
            Last K turns based on config.history_turns
        """
        k = self._config.history_turns
        if k <= 0:
            return []

        return history[-k:] if len(history) > k else history

    async def _call_sensor_llm(
        self,
        message: str,
        schema_mask: CustomerSchemaMask | None,
        glossary_view: dict[str, GlossaryItem] | None,
        conversation_window: list[Turn],
        previous_intent_label: str | None,
    ) -> dict[str, Any]:
        """Call sensor LLM (P2.4).

        Args:
            message: Current user message
            schema_mask: Privacy-safe schema view
            glossary_view: Domain glossary
            conversation_window: Last K turns
            previous_intent_label: Previous canonical intent

        Returns:
            Parsed JSON output from LLM
        """
        # Render Jinja2 template
        prompt = self._template_loader.render(
            "situation_sensor.jinja2",
            message=message,
            schema_mask=schema_mask,
            glossary=glossary_view,
            conversation_window=conversation_window,
            previous_intent_label=previous_intent_label or "none",
        )

        # Call LLM
        messages = [LLMMessage(role="user", content=prompt)]

        response = await self._executor.generate(
            messages=messages,
            max_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
        )

        # Extract JSON from response
        return self._extract_json(response.content)

    def _extract_json(self, content: str) -> dict[str, Any]:
        """Extract JSON from LLM response.

        Handles markdown code blocks and raw JSON.

        Args:
            content: LLM response content

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If JSON cannot be extracted
        """
        # Try to extract from markdown code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r"(\{.*\})", content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                logger.error("no_json_found", content_length=len(content))
                raise ValueError("No JSON found in LLM response")

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("json_parse_failed", error=str(e), json_str=json_str[:200])
            raise ValueError(f"Failed to parse JSON: {e}") from e

    def _parse_snapshot(self, llm_output: dict[str, Any], message: str) -> SituationSnapshot:
        """Parse snapshot from LLM output (P2.5).

        Args:
            llm_output: Parsed JSON from LLM
            message: Original user message

        Returns:
            SituationSnapshot with all fields populated

        Raises:
            ValueError: If required fields are missing
        """
        # Parse candidate_variables
        candidate_variables = {}
        for field_name, var_info in llm_output.get("candidate_variables", {}).items():
            candidate_variables[field_name] = CandidateVariableInfo(
                value=var_info.get("value"),
                scope=var_info.get("scope", "IDENTITY"),
                is_update=var_info.get("is_update", False),
            )

        # Normalize frustration_level - LLM may return "none" string instead of null
        frustration_raw = llm_output.get("frustration_level")
        frustration_level = None
        if frustration_raw and frustration_raw.lower() in ("low", "medium", "high"):
            frustration_level = frustration_raw.lower()

        # Parse sentiment
        sentiment = Sentiment.NEUTRAL
        sentiment_raw = llm_output.get("sentiment", "neutral")
        if sentiment_raw:
            try:
                sentiment = Sentiment(sentiment_raw.lower())
            except ValueError:
                pass  # Keep default

        # Parse urgency
        urgency = Urgency.NORMAL
        urgency_raw = llm_output.get("urgency", "normal")
        if urgency_raw:
            try:
                urgency = Urgency(urgency_raw.lower())
            except ValueError:
                pass  # Keep default

        # Parse scenario_signal
        scenario_signal = ScenarioSignal.CONTINUE
        signal_raw = llm_output.get("scenario_signal", "continue")
        if signal_raw:
            try:
                scenario_signal = ScenarioSignal(signal_raw.lower())
            except ValueError:
                pass  # Keep default

        # Build snapshot
        return SituationSnapshot(
            message=message,
            language=llm_output.get("language", "en"),
            previous_intent_label=llm_output.get("previous_intent_label"),
            intent_changed=llm_output.get("intent_changed", False),
            new_intent_label=llm_output.get("new_intent_label"),
            new_intent_text=llm_output.get("new_intent_text"),
            topic=llm_output.get("topic"),
            topic_changed=llm_output.get("topic_changed", False),
            tone=llm_output.get("tone", "neutral"),
            sentiment=sentiment,
            frustration_level=frustration_level,
            urgency=urgency,
            scenario_signal=scenario_signal,
            situation_facts=llm_output.get("situation_facts", []),
            candidate_variables=candidate_variables,
        )

    def _validate_language(self, language: str, message: str) -> str:
        """Validate language code (P2.6).

        Args:
            language: ISO 639-1 language code from LLM
            message: Original user message (for fallback detection)

        Returns:
            Validated language code
        """
        # Basic validation - check if it's a 2-letter code
        if len(language) == 2 and language.isalpha():
            return language.lower()

        logger.warning(
            "invalid_language_code",
            language=language,
            defaulting_to="en",
        )
        return "en"
