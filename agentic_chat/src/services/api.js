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

