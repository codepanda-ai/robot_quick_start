from abc import ABC, abstractmethod


class ITool(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def parameters_schema(self) -> dict:
        """Return JSON Schema for tool arguments."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> dict:
        """Execute the tool and return a result dict."""
        pass

    def to_llm_schema(self) -> dict:
        """Convert to LLM function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self.description(),
                "parameters": self.parameters_schema(),
            },
        }
