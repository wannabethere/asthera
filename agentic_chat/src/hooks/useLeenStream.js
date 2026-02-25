import { useState, useCallback, useRef } from 'react'

function splitJsonObjects(dataStr) {
  const jsonObjects = []
  let start = -1
  let depth = 0
  let inString = false
  let escapeNext = false
  for (let i = 0; i < dataStr.length; i++) {
    const char = dataStr[i]
    if (escapeNext) { escapeNext = false; continue }
    if (char === '\\') { escapeNext = true; continue }
    if (char === '"' && !escapeNext) { inString = !inString; continue }
    if (!inString) {
      if (char === '{') {
        if (depth === 0) start = i
        depth++
      } else if (char === '}') {
        depth--
        if (depth === 0 && start !== -1) {
          jsonObjects.push(dataStr.substring(start, i + 1))
          start = -1
        }
      }
    }
  }
  return jsonObjects
}

function parseSSEChunk(buffer, currentEvent, onEvent) {
  const lines = buffer.split('\n')
  const remaining = lines.pop() || ''
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed === '') {
      if (currentEvent.data) {
        const jsonObjects = splitJsonObjects(currentEvent.data.trim())
        for (const jsonStr of jsonObjects) {
          try {
            const event = JSON.parse(jsonStr)
            onEvent(event)
          } catch (_) {}
        }
        currentEvent.data = null
      }
    } else if (trimmed.startsWith('event: ')) {
      currentEvent.type = trimmed.slice(7)
    } else if (trimmed.startsWith('data: ')) {
      currentEvent.data = currentEvent.data ? currentEvent.data + '\n' + trimmed.slice(6) : trimmed.slice(6)
    }
  }
  return { remaining, currentEvent }
}

/**
 * Hook for Leen planner streaming (VM Report / Asset Inventory).
 * Streams from /api/leen/stream and handles result, graph_completed, graph_error.
 */
export function useLeenStream() {
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const [currentStep, setCurrentStep] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const abortControllerRef = useRef(null)

  const streamLeen = useCallback(async (request, onEvent) => {
    if (isStreaming) return null
    setIsStreaming(true)
    setError(null)
    abortControllerRef.current = new AbortController()
    let resolvedSessionId = null

    try {
      const response = await fetch('/api/leen/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: abortControllerRef.current.signal
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const sessionHeader = response.headers.get('X-Session-Id')
      resolvedSessionId = sessionHeader
      if (sessionHeader) setSessionId(sessionHeader)
      console.log('[LeenStream] Started, session_id:', sessionHeader)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = {}

      while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
        const { remaining, currentEvent: next } = parseSSEChunk(buffer, currentEvent, (event) => {
          if (['result', 'graph_completed', 'graph_error', 'state_update'].includes(event.event_type)) {
            console.log('[LeenStream]', event.event_type, event)
          }
          setCurrentStep(event.node_name || event.current_step || event.event_type)
          onEvent(event)
        })
        buffer = remaining
        currentEvent = next

        if (done) {
          if (buffer.trim() || currentEvent.data) {
            const jsonObjects = splitJsonObjects((currentEvent.data || buffer).trim())
            for (const jsonStr of jsonObjects) {
              try {
                onEvent(JSON.parse(jsonStr))
              } catch (_) {}
            }
          }
          break
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message)
        throw err
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
    console.log('[LeenStream] Ended, session_id:', resolvedSessionId)
    return resolvedSessionId
  }, [isStreaming])

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setIsStreaming(false)
    }
  }, [])

  return {
    streamLeen,
    isStreaming,
    error,
    currentStep,
    sessionId,
    cancelStream
  }
}
