const API_BASE = '/api/streams'

export async function fetchAssistants() {
  try {
    console.log(`[API] Fetching assistants from ${API_BASE}/assistants`)
    const response = await fetch(`${API_BASE}/assistants`)
    console.log(`[API] Response status: ${response.status} ${response.statusText}`)
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error(`[API] Error response:`, errorText)
      throw new Error(`Failed to fetch assistants: ${response.status} ${response.statusText}`)
    }
    
    const data = await response.json()
    console.log(`[API] Received data:`, data)
    console.log(`[API] Assistants count:`, data.assistants?.length || 0)
    
    return data
  } catch (error) {
    console.error(`[API] Fetch error:`, error)
    throw error
  }
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

