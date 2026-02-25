const API_BASE = '/api/streams'

export async function fetchAssistants() {
  const response = await fetch(`${API_BASE}/assistants`)
  if (!response.ok) {
    throw new Error(`Failed to fetch assistants: ${response.statusText}`)
  }
  return response.json()
}

export async function getAssistant(assistantId) {
  const response = await fetch(`${API_BASE}/assistants/${assistantId}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch assistant: ${response.statusText}`)
  }
  return response.json()
}

export async function invokeAssistant(request) {
  const response = await fetch(`${API_BASE}/invoke`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request)
  })
  if (!response.ok) {
    throw new Error(`Failed to invoke assistant: ${response.statusText}`)
  }
  return response
}

/**
 * Start or resume Leen planner stream (VM Report / Asset Inventory).
 * Returns fetch Response with readable stream body for SSE.
 * @param {{ goal: string, session_id?: string, resume?: object }} request
 */
export async function streamLeenPlanner(request) {
  const response = await fetch('/api/leen/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request)
  })
  if (!response.ok) {
    throw new Error(`Failed to stream Leen planner: ${response.statusText}`)
  }
  return response
}

/**
 * Get current Leen planner state (e.g. interrupt payload for selection).
 * @param {string} sessionId
 */
export async function getLeenState(sessionId) {
  const response = await fetch(`/api/leen/state/${sessionId}`)
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    console.log('[API] getLeenState error:', response.status, response.statusText, data)
    throw new Error(`Failed to get Leen state: ${response.statusText}`)
  }
  console.log('[API] getLeenState ok:', data)
  return data ?? {}
}

