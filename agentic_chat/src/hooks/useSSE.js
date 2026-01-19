import { useState, useCallback, useRef } from 'react'

/**
 * Split a string containing multiple JSON objects into individual JSON strings
 * Handles cases where JSON objects are concatenated like {"a":1}{"b":2}
 */
function splitJsonObjects(dataStr) {
  const jsonObjects = []
  let start = -1
  let depth = 0
  let inString = false
  let escapeNext = false
  
  for (let i = 0; i < dataStr.length; i++) {
    const char = dataStr[i]
    
    if (escapeNext) {
      escapeNext = false
      continue
    }
    
    if (char === '\\') {
      escapeNext = true
      continue
    }
    
    if (char === '"' && !escapeNext) {
      inString = !inString
      continue
    }
    
    if (!inString) {
      if (char === '{') {
        if (depth === 0) {
          start = i
        }
        depth++
      } else if (char === '}') {
        depth--
        if (depth === 0 && start !== -1) {
          // Found a complete JSON object
          const jsonStr = dataStr.substring(start, i + 1)
          jsonObjects.push(jsonStr)
          start = -1
        }
      }
    }
  }
  
  return jsonObjects
}

export function useSSE() {
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const abortControllerRef = useRef(null)

  const streamMessage = useCallback(async (request, onEvent) => {
    console.log('[useSSE] ===== streamMessage called =====')
    console.log('[useSSE] Request:', request)
    console.log('[useSSE] isStreaming:', isStreaming)
    
    if (isStreaming) {
      console.warn('[useSSE] Already streaming, ignoring new request')
      return
    }

    console.log('[useSSE] Starting stream...')
    setIsStreaming(true)
    setError(null)

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController()

    try {
      console.log('[useSSE] Making fetch request to /api/streams/invoke')
      const response = await fetch('/api/streams/invoke', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal: abortControllerRef.current.signal
      })

      console.log('[useSSE] Response received, status:', response.status, 'ok:', response.ok)
      
      if (!response.ok) {
        console.error('[useSSE] HTTP error! status:', response.status)
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      console.log('[useSSE] Response OK, getting reader...')
      const reader = response.body.getReader()
      console.log('[useSSE] Reader obtained, starting to read stream...')
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = {}

      let eventCount = 0
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          console.log(`[useSSE] Stream ended. Total events processed: ${eventCount}`)
          // Process any remaining data in buffer
          if (buffer.trim() || currentEvent.data) {
            console.log('[useSSE] Processing remaining buffer data')
            // Try to process any remaining event
            if (currentEvent.data) {
              try {
                let dataStr = currentEvent.data.trim()
                const firstBrace = dataStr.indexOf('{')
                const lastBrace = dataStr.lastIndexOf('}')
                if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
                  dataStr = dataStr.substring(firstBrace, lastBrace + 1)
                }
                const event = JSON.parse(dataStr)
                eventCount++
                console.log(`[useSSE] Parsed final buffer event #${eventCount}: ${event.event_type || 'unknown'}`)
                onEvent(event)
              } catch (e) {
                console.warn('[useSSE] Failed to parse final buffer event:', e)
                console.warn('[useSSE] Final buffer data:', currentEvent.data?.substring(0, 500))
              }
            }
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          const trimmedLine = line.trim()
          
          if (trimmedLine === '') {
            // Empty line indicates end of SSE message
            if (currentEvent.data) {
              try {
                // Clean up the data - remove any trailing whitespace/newlines
                let dataStr = currentEvent.data.trim()
                
                // Handle case where there might be multiple JSON objects concatenated
                // Use helper function to split JSON objects
                const jsonObjects = splitJsonObjects(dataStr)
                
                // Process each JSON object separately
                if (jsonObjects.length > 0) {
                  for (const jsonStr of jsonObjects) {
                    try {
                      const event = JSON.parse(jsonStr)
                      eventCount++
                      console.log(`[useSSE] ===== Parsed event #${eventCount}: ${event.event_type || 'unknown'} =====`)
                      console.log(`[useSSE] Full event object:`, event)
                      if (event.event_type === 'result' || event.event_type === 'graph_completed') {
                        console.log(`[useSSE] ⭐ Important event ${event.event_type}:`, {
                          has_result: !!event.result,
                          result_keys: event.result ? Object.keys(event.result) : null,
                          has_final_state: !!event.final_state,
                          final_state_keys: event.final_state ? Object.keys(event.final_state) : null,
                          final_answer_in_result: event.result?.final_answer ? `YES (${event.result.final_answer.length} chars)` : 'NO',
                          final_answer_in_state: event.final_state?.final_answer ? `YES (${event.final_state.final_answer.length} chars)` : 'NO',
                          written_content_in_result: event.result?.written_content ? `YES (${event.result.written_content.length} chars)` : 'NO',
                          written_content_in_state: event.final_state?.written_content ? `YES (${event.final_state.written_content.length} chars)` : 'NO'
                        })
                      }
                      console.log(`[useSSE] Calling onEvent callback...`)
                      onEvent(event)
                      console.log(`[useSSE] onEvent callback completed`)
                    } catch (e) {
                      console.warn(`[useSSE] Failed to parse JSON object:`, e)
                      console.warn(`[useSSE] JSON string (first 200 chars):`, jsonStr.substring(0, 200))
                    }
                  }
                } else {
                  // Fallback: try to parse as single JSON object
                  const firstBrace = dataStr.indexOf('{')
                  const lastBrace = dataStr.lastIndexOf('}')
                  if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
                    const jsonStr = dataStr.substring(firstBrace, lastBrace + 1)
                    const event = JSON.parse(jsonStr)
                    eventCount++
                    console.log(`[useSSE] ===== Parsed event #${eventCount} (fallback): ${event.event_type || 'unknown'} =====`)
                    onEvent(event)
                  } else {
                    throw new Error('No valid JSON found in data')
                  }
                }
              } catch (e) {
                console.warn('[useSSE] Failed to parse SSE event data:', e)
                console.warn('[useSSE] Data that failed to parse:', currentEvent.data?.substring(0, 500))
                console.warn('[useSSE] Current event type:', currentEvent.type)
                // Try to continue - don't break the stream
              }
            }
            currentEvent = {} // Reset for next event
          } else if (trimmedLine.startsWith('event: ')) {
            currentEvent.type = trimmedLine.slice(7)
          } else if (trimmedLine.startsWith('id: ')) {
            currentEvent.id = trimmedLine.slice(4)
          } else if (trimmedLine.startsWith('data: ')) {
            const data = trimmedLine.slice(6)
            if (currentEvent.data) {
              // Multi-line data, append
              currentEvent.data += '\n' + data
            } else {
              currentEvent.data = data
            }
          }
        }
      }
      
      // Handle any remaining event in buffer
      // Combine any remaining buffer with currentEvent.data
      let remainingData = (currentEvent.data || '') + (buffer.trim() || '')
      
      if (remainingData.trim()) {
        console.log('[useSSE] Processing remaining buffer data, length:', remainingData.length)
        
        // Use the same split logic as above
        const jsonObjects = splitJsonObjects(remainingData.trim())
        
        // Process each JSON object separately
        for (const jsonStr of jsonObjects) {
          try {
            const event = JSON.parse(jsonStr)
            eventCount++
            console.log(`[useSSE] ===== Parsed final buffer event #${eventCount}: ${event.event_type || 'unknown'} =====`)
            console.log(`[useSSE] Full event object:`, event)
            if (event.event_type === 'result' || event.event_type === 'graph_completed') {
              console.log(`[useSSE] ⭐ Important event ${event.event_type}:`, {
                has_result: !!event.result,
                result_keys: event.result ? Object.keys(event.result) : null,
                has_final_state: !!event.final_state,
                final_state_keys: event.final_state ? Object.keys(event.final_state) : null,
                final_answer_in_result: event.result?.final_answer ? `YES (${event.result.final_answer.length} chars)` : 'NO',
                final_answer_in_state: event.final_state?.final_answer ? `YES (${event.final_state.final_answer.length} chars)` : 'NO',
                written_content_in_result: event.result?.written_content ? `YES (${event.result.written_content.length} chars)` : 'NO',
                written_content_in_state: event.final_state?.written_content ? `YES (${event.final_state.written_content.length} chars)` : 'NO'
              })
            }
            console.log(`[useSSE] Calling onEvent callback for final buffer event...`)
            onEvent(event)
            console.log(`[useSSE] onEvent callback completed for final buffer event`)
          } catch (e) {
            console.warn(`[useSSE] Failed to parse JSON object from final buffer:`, e)
            console.warn(`[useSSE] JSON string (first 200 chars):`, jsonStr.substring(0, 200))
          }
        }
        
        if (jsonObjects.length === 0) {
          console.warn('[useSSE] No valid JSON objects found in remaining buffer')
          console.warn('[useSSE] Remaining data (first 500 chars):', remainingData.substring(0, 500))
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted')
      } else {
        setError(err.message)
        throw err
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }, [isStreaming])

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setIsStreaming(false)
    }
  }, [])

  return {
    streamMessage,
    isStreaming,
    error,
    cancelStream
  }
}

