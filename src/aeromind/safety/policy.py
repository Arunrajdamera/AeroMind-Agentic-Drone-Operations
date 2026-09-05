from aeromind.tools.definitions import ToolRisk


class ToolSafetyPolicy:
    def check(self, tool_name: str, risk: ToolRisk) -> tuple[bool, bool, str]:
        if risk == ToolRisk.HIGH:
            return False, True, "High-risk simulated action requires approval"
        return True, False, "Allowed by basic deterministic policy"
