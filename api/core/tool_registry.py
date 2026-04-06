import logging

from interfaces.tool import ITool


logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools. Each agent gets its own ToolRegistry with only the tools it needs."""

    def __init__(self):
        self._tools: dict[str, ITool] = {}

    def register(self, tool: ITool) -> None:
        self._tools[tool.name()] = tool

    def get(self, name: str) -> ITool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool not found: {name}")
        return tool

    def get_schemas(self) -> list[dict]:
        return [tool.to_llm_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> dict:
        tool = self.get(name)
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            logger.warning("Tool %s execution error: %s", name, e)
            return {"error": str(e)}
