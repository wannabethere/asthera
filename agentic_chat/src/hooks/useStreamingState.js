import { useRef, useCallback } from 'react'

/**
 * Custom hook to manage streaming state using refs
 * This ensures state persists across event callbacks
 */
export function useStreamingState() {
  const stateRef = useRef({
    fullContent: '',
    markdownContent: '',
    reasoningText: '',
    finalResult: null,
    currentStep: 'Initializing...'
  })

  const updateState = useCallback((updates) => {
    stateRef.current = { ...stateRef.current, ...updates }
  }, [])

  const getState = useCallback(() => {
    return { ...stateRef.current }
  }, [])

  const resetState = useCallback(() => {
    stateRef.current = {
      fullContent: '',
      markdownContent: '',
      reasoningText: '',
      finalResult: null,
      currentStep: 'Initializing...'
    }
  }, [])

  /**
   * Extract content from various event types
   */
  const extractContent = useCallback((event) => {
    const state = getState()
    let extracted = false

    // Try to extract from result event
    if (event.event_type === 'result' && event.result) {
      const result = event.result
      if (result.final_answer) {
        updateState({ 
          fullContent: result.final_answer, 
          markdownContent: result.final_answer 
        })
        extracted = true
      } else if (result.written_content) {
        updateState({ 
          fullContent: result.written_content, 
          markdownContent: result.written_content 
        })
        extracted = true
      } else if (result.qa_answer) {
        updateState({ 
          fullContent: result.qa_answer, 
          markdownContent: result.qa_answer 
        })
        extracted = true
      } else if (result.final_output) {
        const content = typeof result.final_output === 'string' 
          ? result.final_output 
          : result.final_output.content || result.final_output.answer
        if (content) {
          updateState({ fullContent: content, markdownContent: content })
          extracted = true
        }
      }
    }

    // Try to extract from graph_completed final_state
    if (event.event_type === 'graph_completed' && event.final_state) {
      const finalState = event.final_state
      if (finalState.final_answer && !state.fullContent) {
        updateState({ 
          fullContent: finalState.final_answer, 
          markdownContent: finalState.final_answer 
        })
        extracted = true
      } else if (finalState.written_content && !state.fullContent) {
        updateState({ 
          fullContent: finalState.written_content, 
          markdownContent: finalState.written_content 
        })
        extracted = true
      } else if (finalState.qa_answer && !state.fullContent) {
        updateState({ 
          fullContent: finalState.qa_answer, 
          markdownContent: finalState.qa_answer 
        })
        extracted = true
      }
    }

    // Try to extract from state_update
    if (event.event_type === 'state_update' && event.state_snapshot) {
      const snapshot = event.state_snapshot
      const content = snapshot.final_answer || snapshot.written_content || 
                     snapshot.qa_answer || snapshot.answer || 
                     (snapshot.final_output?.content || snapshot.final_output)
      if (content && typeof content === 'string' && !state.fullContent) {
        updateState({ fullContent: content, markdownContent: content })
        extracted = true
      }
    }

    // Try to extract from node_completed output_state
    if (event.event_type === 'node_completed' && event.output_state) {
      const output = event.output_state
      const content = output.final_answer || output.qa_answer ||
                     output.answer || output.content
      if (content && typeof content === 'string' && !state.fullContent) {
        updateState({ fullContent: content, markdownContent: content })
        extracted = true
      }
    }

    // Fallback: if result has no final_answer but has structured data (e.g. recommended_features), build markdown
    const result = (event.event_type === 'result' && event.result) ? event.result
      : (event.event_type === 'graph_completed' && event.final_state) ? event.final_state
      : null
    if (result && !state.fullContent && typeof result === 'object') {
      const strContent = result.final_answer || result.written_content || result.qa_answer
      if (strContent && typeof strContent === 'string') {
        updateState({ fullContent: strContent, markdownContent: strContent })
        return true
      }
      const features = result.recommended_features || result.features
      if (Array.isArray(features) && features.length > 0) {
        const lines = ['## Recommended features\n']
        features.forEach((f, i) => {
          const name = (f.feature_name || f.name || `Feature ${i + 1}`).trim()
          const nlq = f.natural_language_question || f.nlq || ''
          const type_ = f.feature_type || f.type || ''
          let line = `- **${name}**`
          if (type_) line += ` (${type_})`
          if (nlq) line += `\n  - ${nlq}`
          lines.push(line)
        })
        const markdown = lines.join('\n')
        updateState({ fullContent: markdown, markdownContent: markdown })
        extracted = true
      }
    }

    return extracted
  }, [getState, updateState])

  return {
    stateRef,
    updateState,
    getState,
    resetState,
    extractContent
  }
}

