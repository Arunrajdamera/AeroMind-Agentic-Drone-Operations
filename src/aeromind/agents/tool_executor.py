from sqlalchemy.orm import Session

from aeromind.tools.executor import ToolExecutor


class GraphToolExecutor:
    def __init__(self, session: Session) -> None:
        self.executor = ToolExecutor(session)

    def run(self, state: dict) -> dict:
        if not state.get("execute_tools"):
            return {"tool_results": [], "execution_status": "PLANNED"}
        results = [
            self.executor.execute(call, state.get("run_id"))
            for call in state.get("tool_requests", [])
        ]
        status = (
            "REQUIRES_APPROVAL"
            if any(result.status.value == "REQUIRES_APPROVAL" for result in results)
            else "COMPLETED"
        )
        return {"tool_results": results, "execution_status": status}
