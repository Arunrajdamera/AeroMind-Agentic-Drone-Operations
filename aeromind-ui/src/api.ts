const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

export type SimulationEventResponse = {
  simulation_only: boolean;
  event_id: string;
};

export type AgentRunResponse = {
  run_id: string;
  decision?: {
    decision?: string;
    confidence?: number;
    requires_human_approval?: boolean;
    reason?: string;
    decision_factors?: {
      risk_level?: string;
      risk_score?: number;
      perception_confidence?: number;
      restricted_zone?: boolean;
      requires_investigation?: boolean;
      knowledge_relevant?: boolean;
      knowledge_confidence?: number;
      evidence_strength?: number;
      conflicting_evidence?: boolean;
      human_approval_required?: boolean;
      recommended_action_source?: string;
    };
  };
  risk_assessment?: {
    risk_level?: string;
    risk_score?: number;
    recommended_action?: string;
    requires_human_approval?: boolean;
  };
  perception?: {
    event_type?: string;
    confidence?: number;
    severity?: string;
    restricted_zone?: boolean;
    requires_investigation?: boolean;
  };
  knowledge?: {
    relevant?: boolean;
    confidence?: number;
  };
  memory_context?: unknown;
  memory_count?: number;
  execution_status?: string;
  tool_results?: Array<{
    tool_name?: string;
    status?: string;
  }>;
};

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `API request failed (${response.status})`;

    try {
      const body = await response.json();
      if (body?.message) {
        message = body.message;
      }
    } catch {
      // Keep the generic message when the response is not JSON.
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function createSimulationEvent(
  scenario: string,
  droneId: string,
): Promise<SimulationEventResponse> {
  return request<SimulationEventResponse>("/simulation/event", {
    method: "POST",
    body: JSON.stringify({
      scenario,
      drone_id: droneId,
    }),
  });
}

export async function runAgent(
  eventId: string,
  droneId: string,
): Promise<AgentRunResponse> {
  return request<AgentRunResponse>("/agent/run", {
    method: "POST",
    body: JSON.stringify({
      event_id: eventId,
      drone_id: droneId,
      execute_tools: true,
    }),
  });
}
