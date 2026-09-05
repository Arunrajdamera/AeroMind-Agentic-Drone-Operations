import { useState } from 'react'
import './App.css'
import { createSimulationEvent, runAgent, type AgentRunResponse } from './api'

type StageStatus = 'complete' | 'active' | 'pending'

const defaultStages = [
  { name: 'Perception', detail: 'Event interpreted', status: 'complete' as StageStatus },
  { name: 'Risk Assessment', detail: 'HIGH - 74.1', status: 'complete' as StageStatus },
  { name: 'Knowledge', detail: 'Policy evidence found', status: 'complete' as StageStatus },
  { name: 'Memory', detail: '3 memories recorded', status: 'complete' as StageStatus },
  { name: 'Evidence', detail: 'Strong supporting evidence', status: 'complete' as StageStatus },
  { name: 'Decision', detail: 'RAISE_ALERT', status: 'active' as StageStatus },
  { name: 'Safety Gate', detail: 'Policy check passed', status: 'active' as StageStatus },
  { name: 'Tool Execution', detail: '2 tools completed', status: 'complete' as StageStatus },
]

const drones = [
  { id: 'DR-01', status: 'Investigating', battery: 87 },
  { id: 'DR-02', status: 'Available', battery: 94 },
  { id: 'DR-03', status: 'Available', battery: 76 },
  { id: 'DR-04', status: 'Standby', battery: 91 },
]

function App() {
  const [running, setRunning] = useState(false)
  const [eventType, setEventType] = useState('INTRUSION')
  const [selectedDrone, setSelectedDrone] = useState('DR-01')
  const [result, setResult] = useState<AgentRunResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const displayStages = result
    ? defaultStages.map((stage) => {
        if (stage.name === 'Risk Assessment') {
          const level = result.risk_assessment?.risk_level ?? 'N/A'
          const score = result.risk_assessment?.risk_score
          return {
            ...stage,
            detail: `${level} - ${score != null ? score.toFixed(1) : 'N/A'}`,
          }
        }

        if (stage.name === 'Memory') {
          return {
            ...stage,
            detail: `${result.memory_count ?? 0} memories recorded`,
          }
        }

        if (stage.name === 'Decision') {
          return {
            ...stage,
            detail: result.decision?.decision ?? 'N/A',
          }
        }

        if (stage.name === 'Tool Execution') {
          const count = result.tool_results?.length ?? 0
          return {
            ...stage,
            detail: `${count} tools completed`,
          }
        }

        return stage
      })
    : defaultStages

  const handleRun = async () => {
    setRunning(true)
    setError(null)

    try {
      const event = await createSimulationEvent(eventType, selectedDrone)
      const agentResult = await runAgent(event.event_id, selectedDrone)
      setResult(agentResult)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Agent request failed')
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">&#10022;</div>
          <div>
            <div className="brand-name">AeroMind</div>
            <div className="brand-subtitle">Autonomous Mission Operations</div>
          </div>
        </div>

        <div className="simulation-badge">
          <span className="status-dot" />
          SIMULATION MODE
        </div>

        <div className="system-status">
          <span className="status-dot" />
          SYSTEM OPERATIONAL
        </div>
      </header>

      <section className="hero-section">
        <div>
          <p className="eyebrow">AGENTIC AI CONTROL CENTER</p>
          <h1>Mission Control</h1>
          <p className="hero-copy">
            Observe, evaluate and safely execute autonomous drone mission decisions.
          </p>
        </div>

        <div className="hero-metrics">
          <div className="metric">
            <span>FLEET</span>
            <strong>04</strong>
          </div>
          <div className="metric">
            <span>AGENT RUNS</span>
            <strong>128</strong>
          </div>
          <div className="metric">
            <span>EVALUATION</span>
            <strong>6/6</strong>
          </div>
        </div>
      </section>

      <section className="control-grid">
        <div className="panel event-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">01 - SIMULATED EVENT</span>
              <h2>Mission Event</h2>
            </div>
            <span className="panel-tag">LIVE</span>
          </div>

          <div className="form-grid">
            <label>
              <span>Event type</span>
              <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
                <option>INTRUSION</option>
                <option>THERMAL_ANOMALY</option>
                <option>BATTERY_WARNING</option>
              </select>
            </label>

            <label>
              <span>Drone</span>
              <select value={selectedDrone} onChange={(e) => setSelectedDrone(e.target.value)}>
                {drones.map((drone) => (
                  <option key={drone.id}>{drone.id}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="event-preview">
            <div className="event-icon">&#9888;</div>
            <div>
              <strong>{eventType}</strong>
              <p>Simulated event detected by {selectedDrone}</p>
            </div>
            <span className="severity high">HIGH</span>
          </div>

          <button className="primary-button" onClick={handleRun} disabled={running}>
            {running ? 'Running Agent Pipeline...' : 'Run Agent Analysis'}
            <span>&rarr;</span>
          </button>
        </div>

        <div className="panel fleet-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">02 - FLEET</span>
              <h2>Drone Status</h2>
            </div>
            <span className="fleet-count">4 ACTIVE</span>
          </div>

          <div className="drone-list">
            {drones.map((drone) => (
              <div className="drone-row" key={drone.id}>
                <div className="drone-avatar">&#9670;</div>
                <div className="drone-info">
                  <strong>{drone.id}</strong>
                  <span>{drone.status}</span>
                </div>
                <div className="battery">
                  <span>{drone.battery}%</span>
                  <div className="battery-track">
                    <div style={{ width: `${drone.battery}%` }} />
                  </div>
                </div>
                <span className={`drone-state ${drone.status === 'Investigating' ? 'busy' : ''}`} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {error && (
        <section className="panel live-result-panel error-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">LIVE API ERROR</span>
              <h2>Agent Request Failed</h2>
            </div>
            <span className="decision-badge">ERROR</span>
          </div>
          <p className="live-result-message">{error}</p>
        </section>
      )}

      {result && (
        <section className="panel live-result-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">LIVE AGENT RESULT</span>
              <h2>Backend Decision</h2>
            </div>
            <span className="safe-badge">{result.execution_status ?? 'COMPLETED'}</span>
          </div>

          <div className="live-result-grid">
            <div>
              <span>RUN ID</span>
              <strong>{result.run_id}</strong>
            </div>
            <div>
              <span>DECISION</span>
              <strong>{result.decision?.decision ?? 'N/A'}</strong>
            </div>
            <div>
              <span>RISK</span>
              <strong>{result.risk_assessment?.risk_level ?? 'N/A'}</strong>
            </div>
            <div>
              <span>RISK SCORE</span>
              <strong>{result.risk_assessment?.risk_score != null ? result.risk_assessment.risk_score.toFixed(1) : 'N/A'}</strong>
            </div>
            <div>
              <span>CONFIDENCE</span>
              <strong>
                {result.decision?.confidence != null
                  ? `${Math.round(result.decision.confidence * 100)}%`
                  : 'N/A'}
              </strong>
            </div>
            <div>
              <span>HUMAN APPROVAL</span>
              <strong>
                {result.decision?.requires_human_approval ? 'REQUIRED' : 'NOT REQUIRED'}
              </strong>
            </div>
          </div>
        </section>
      )}

      <section className="pipeline-section">
        <div className="section-heading">
          <div>
            <span className="panel-kicker">03 - AGENT PIPELINE</span>
            <h2>Decision Trace</h2>
          </div>
          <span className="run-id">RUN - {result ? `${result.run_id.slice(0, 8)}...` : "NO ACTIVE RUN"}</span>
        </div>

        <div className="pipeline">
          {displayStages.map((stage, index) => (
            <div className="stage-wrapper" key={stage.name}>
              <div className={`stage ${stage.status}`}>
                <div className="stage-indicator">
                  {stage.status === 'complete' ? 'OK' : stage.status === 'active' ? 'ON' : '--'}
                </div>
                <div className="stage-content">
                  <strong>{stage.name}</strong>
                  <span>{stage.detail}</span>
                </div>
              </div>
              {index < displayStages.length - 1 && <div className="stage-arrow">&rarr;</div>}
            </div>
          ))}
        </div>
      </section>

      <section className="results-grid">
        <div className="panel decision-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">04 - DECISION</span>
              <h2>Agent Decision</h2>
            </div>
            <span className="decision-badge">{result?.decision?.decision?.replaceAll("_", " ") ?? "RAISE ALERT"}</span>
          </div>

          <div className="decision-main">
            <div className="decision-score">
              <strong>{result?.risk_assessment?.risk_level ?? "HIGH"}</strong>
              <span>{result?.risk_assessment?.risk_score != null ? `${result.risk_assessment.risk_score.toFixed(1)} risk score` : "74.1 risk score"}</span>
            </div>
            <div className="confidence">
              <span>CONFIDENCE</span>
              <strong>{result?.decision?.confidence != null ? `${Math.round(result.decision.confidence * 100)}%` : "95%"}</strong>
            </div>
          </div>

          <div className="factor-list">
            <div>
              <span>Restricted zone</span>
              <strong>{result?.decision?.decision_factors?.restricted_zone ? 'YES' : 'NO'}</strong>
            </div>
            <div>
              <span>Investigation required</span>
              <strong>{result?.decision?.decision_factors?.requires_investigation ? 'YES' : 'NO'}</strong>
            </div>
            <div>
              <span>Knowledge relevant</span>
              <strong>{result?.decision?.decision_factors?.knowledge_relevant ? 'YES' : 'NO'}</strong>
            </div>
            <div>
              <span>Human approval</span>
              <strong>{result?.decision?.decision_factors?.human_approval_required ? 'YES' : 'NO'}</strong>
            </div>
          </div>
        </div>

        <div className="panel safety-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">05 - SAFETY</span>
              <h2>Safety Gate</h2>
            </div>
            <span className="safe-badge">
  {result
    ? result.decision?.requires_human_approval
      ? 'APPROVAL REQUIRED'
      : result.execution_status === 'COMPLETED'
        ? 'PASSED'
        : 'PENDING'
    : 'READY'}
</span>
          </div>

          <div className="safety-visual">
            <div className="shield">&#10003;</div>
            <div>
              <strong>Policy enforcement active</strong>
              <p>Only registered tools may execute simulated actions.</p>
            </div>
          </div>

          <div className="tool-result">
            <span>TOOLS EXECUTED</span>
            {result?.tool_results?.length ? (
              result.tool_results.map((tool) => (
                <div key={tool.tool_name}>
                  <code>{tool.tool_name ?? 'unknown_tool'}</code>
                  <b>{tool.status ?? 'UNKNOWN'}</b>
                </div>
              ))
            ) : (
              <div>
                <code>No tools executed</code>
                <b>{result ? 'NONE' : '--'}</b>
              </div>
            )}
          </div>
        </div>
      </section>

      <footer>
        <span>AeroMind v0.1.0</span>
        <span>All drone operations are simulated - No physical flight control</span>
        <span>Agent Safety Architecture</span>
      </footer>
    </main>
  )
}

export default App
