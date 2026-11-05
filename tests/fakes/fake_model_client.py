from ai_shopping_agent.model_client import SchemaAwareModelClient


class FakeModelClient(SchemaAwareModelClient):
    """Deterministic model substitute suitable for offline evaluation."""

