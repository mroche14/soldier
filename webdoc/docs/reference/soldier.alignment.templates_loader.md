<a id="soldier.alignment.templates_loader"></a>

# soldier.alignment.templates\_loader

Helpers for loading templates for matched rules.

<a id="soldier.alignment.templates_loader.load_templates_for_rules"></a>

#### load\_templates\_for\_rules

```python
async def load_templates_for_rules(
        config_store: ConfigStore, tenant_id: UUID,
        matched_rules: list[MatchedRule]) -> list[Template]
```

Load templates referenced by matched rules.

