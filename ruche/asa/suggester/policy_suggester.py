"""Policy suggestion for tool definitions.

This module suggests appropriate side-effect policies for tools based on their
names and descriptions. Used primarily by alignment-based mechanics that use
the Side-Effect Policy system.
"""

from ruche.asa.models import PolicySuggestion, SideEffectPolicy


class PolicySuggester:
    """Suggest side-effect policies for tools based on semantic analysis."""

    # Keyword mappings for each policy type
    POLICY_KEYWORDS = {
        SideEffectPolicy.IRREVERSIBLE: [
            "send",
            "email",
            "sms",
            "notification",
            "notify",
            "refund",
            "payment",
            "charge",
            "bill",
            "delete",
            "remove",
            "cancel",
            "submit",
            "finalize",
            "complete",
            "transfer",
            "withdraw",
            "publish",
            "post",
            "broadcast",
        ],
        SideEffectPolicy.COMPENSATABLE: [
            "add",
            "create",
            "reserve",
            "book",
            "update",
            "modify",
            "change",
            "enable",
            "disable",
            "lock",
            "unlock",
            "archive",
        ],
        SideEffectPolicy.IDEMPOTENT: [
            "set",
            "assign",
            "configure",
            "sync",
            "refresh",
            "reset",
            "initialize",
        ],
        SideEffectPolicy.PURE: [
            "get",
            "fetch",
            "read",
            "list",
            "search",
            "find",
            "lookup",
            "validate",
            "check",
            "verify",
            "calculate",
            "compute",
            "query",
            "view",
            "show",
            "display",
        ],
    }

    def suggest_policy(
        self,
        tool_name: str,
        description: str | None = None,
    ) -> PolicySuggestion:
        """Suggest appropriate side-effect policy for a tool.

        Analyzes the tool name and description to determine the most likely
        side-effect policy based on keyword matching.

        Args:
            tool_name: Name of the tool
            description: Optional description of what the tool does

        Returns:
            PolicySuggestion with recommended policy and reasoning
        """
        name_lower = tool_name.lower()
        desc_lower = (description or "").lower()
        combined = f"{name_lower} {desc_lower}"

        # Score each policy based on keyword matches
        scores = {policy: 0 for policy in SideEffectPolicy}

        for policy, keywords in self.POLICY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in combined:
                    scores[policy] += 1
                    # Extra weight for name matches (name is more reliable than description)
                    if keyword in name_lower:
                        scores[policy] += 2

        # Get best match
        best_policy = max(scores, key=lambda k: scores[k])
        confidence = scores[best_policy] / (sum(scores.values()) + 1)

        # Default to PURE if no matches (conservative assumption for reads)
        if scores[best_policy] == 0:
            best_policy = SideEffectPolicy.PURE
            confidence = 0.3

        return PolicySuggestion(
            suggested_policy=best_policy,
            confidence=confidence,
            reasoning=self._build_reasoning(tool_name, description, best_policy, scores),
            alternatives=[
                p for p in SideEffectPolicy if p != best_policy and scores[p] > 0
            ],
        )

    def _build_reasoning(
        self,
        tool_name: str,
        description: str | None,
        policy: SideEffectPolicy,
        scores: dict,
    ) -> str:
        """Build human-readable reasoning for the suggestion.

        Args:
            tool_name: Name of the tool
            description: Description of the tool
            policy: Suggested policy
            scores: Scores for each policy

        Returns:
            Human-readable reasoning string
        """
        name_lower = tool_name.lower()
        desc_lower = (description or "").lower()

        # Find matched keywords in name
        matched_in_name = [
            kw
            for kw in self.POLICY_KEYWORDS.get(policy, [])
            if kw in name_lower
        ]

        # Find matched keywords in description
        matched_in_desc = [
            kw
            for kw in self.POLICY_KEYWORDS.get(policy, [])
            if kw in desc_lower and kw not in matched_in_name
        ]

        if matched_in_name:
            return f"Tool name contains '{', '.join(matched_in_name)}' suggesting {policy.value} behavior"
        elif matched_in_desc:
            return f"Tool description contains '{', '.join(matched_in_desc)}' suggesting {policy.value} behavior"
        else:
            return f"Default suggestion based on conservative analysis (verify manually)"
