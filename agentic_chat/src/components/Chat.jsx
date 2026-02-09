import { useState, useEffect, useRef } from 'react'
import { useSSE } from '../hooks/useSSE'
import { useStreamingState } from '../hooks/useStreamingState'
import { fetchAssistants } from '../services/api'
import TopNav from './TopNav'
import ChatInterface from './ChatInterface'
import OutcomesPanel from './OutcomesPanel'
import SplitScreenLayout from './SplitScreenLayout'
import datasetsData from '../data/datasets.json'
import '../App.css'

function Chat() {
  const [assistants, setAssistants] = useState([])
  const [selectedAssistant, setSelectedAssistant] = useState(null)
  const [datasets] = useState(datasetsData)
  // Default to Snyk if available
  const [selectedDataset, setSelectedDataset] = useState(() => {
    const snykDataset = datasetsData.find(d => d.project_id === 'Snyk')
    return snykDataset || null
  })
  const [messages, setMessages] = useState([])
  const [outcomesContent, setOutcomesContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const hasLoadedRef = useRef(false)
  const isLoadingRef = useRef(false)

  const { streamMessage, isStreaming, error: streamError } = useSSE()
  const streamingState = useStreamingState()

  useEffect(() => {
    // Prevent multiple simultaneous loads
    if (hasLoadedRef.current || isLoadingRef.current) {
      return
    }
    
    loadAssistants()
  }, [])

  const loadAssistants = async () => {
    // Prevent duplicate requests
    if (isLoadingRef.current || hasLoadedRef.current) {
      return
    }
    
    try {
      isLoadingRef.current = true
      setLoading(true)
      setError(null) // Clear previous errors
      console.log('[Chat] Loading assistants...')
      const data = await fetchAssistants()
      console.log('[Chat] Received assistants data:', data)
      console.log('[Chat] Assistants array:', data.assistants)
      
      const assistantsList = data.assistants || []
      setAssistants(assistantsList)
      console.log(`[Chat] Set ${assistantsList.length} assistants`)
      
      if (assistantsList.length > 0 && !selectedAssistant) {
        console.log('[Chat] Setting first assistant as selected:', assistantsList[0])
        setSelectedAssistant(assistantsList[0])
      } else if (assistantsList.length === 0) {
        console.warn('[Chat] No assistants found in response')
        setError('No assistants available. Please check if the backend is running and assistants are registered.')
      }
      hasLoadedRef.current = true
    } catch (err) {
      const errorMessage = `Failed to load assistants: ${err.message}`
      console.error('[Chat] Error loading assistants:', err)
      setError(errorMessage)
      // Still set empty array so UI doesn't stay in loading state
      setAssistants([])
    } finally {
      setLoading(false)
      isLoadingRef.current = false
    }
  }

  const handleSendMessage = async (query) => {
    console.log('[App] ===== handleSendMessage called =====')
    console.log('[App] Query:', query)
    console.log('[App] Selected assistant:', selectedAssistant?.assistant_id)
    console.log('[App] Selected dataset:', selectedDataset?.project_id)
    
    if (!selectedAssistant || !query.trim()) {
      console.warn('[App] Missing assistant or query')
      return
    }
    if (!selectedDataset) {
      console.warn('[App] Missing dataset')
      setError('Please select a dataset before sending a message')
      return
    }

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setError(null)
    setOutcomesContent('') // Clear previous outcomes

    // Create assistant message placeholder
    const assistantMessageId = Date.now() + 1
    const assistantMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      console.log('[App] Starting streamMessage...')
      // Reset streaming state for new message
      streamingState.resetState()
      console.log('[App] Streaming state reset')

      console.log('[App] Calling streamMessage with request:', {
        assistant_id: selectedAssistant.assistant_id,
        query: query,
        project_id: selectedDataset.project_id
      })
      
      await streamMessage(
        {
          assistant_id: selectedAssistant.assistant_id,
          query: query,
          session_id: `session_${Date.now()}`,
          input_data: {
            query: query,
            project_id: selectedDataset.project_id,
            user_context: {
              project_id: selectedDataset.project_id
            }
          }
        },
        (event) => {
          // Debug: log all events - ALWAYS log first thing
          console.log('[App] ===== SSE Event received =====')
          console.log('[App] Event type:', event?.event_type)
          console.log('[App] Full event:', event)
          
          if (!event || !event.event_type) {
            console.error('[App] Invalid event received:', event)
            return
          }

          // Get current state
          const currentState = streamingState.getState()
          
          // Try to extract content from event (centralized logic)
          const contentExtracted = streamingState.extractContent(event)
          if (contentExtracted) {
            const newState = streamingState.getState()
            if (newState.markdownContent) {
              setOutcomesContent(newState.markdownContent)
            }
          }
          
          // Handle different event types
          if (event.event_type === 'graph_started') {
            // Graph execution started
            streamingState.updateState({ 
              reasoningText: '🚀 Graph execution started...',
              currentStep: 'Initializing...'
            })
            const state = streamingState.getState()
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: state.reasoningText, 
                    isStreaming: true,
                    currentStep: state.currentStep
                  }
                : msg
            ))
          } else if (event.event_type === 'graph_error') {
            // Graph execution error
            const errorMsg = event.error || 'Unknown error occurred'
            setError(`Graph execution error: ${errorMsg}`)
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: `❌ Error: ${errorMsg}`, isStreaming: false }
                : msg
            ))
          } else if (event.event_type === 'graph_completed') {
            // Graph execution completed - extract final content from final_state
            console.log('[App] Graph completed event received:', event)
            console.log('[App] Graph completed final_state keys:', event.final_state ? Object.keys(event.final_state) : 'null')
            
            const state = streamingState.getState()
            const newReasoningText = state.reasoningText 
              ? `${state.reasoningText}\n✅ Graph execution completed`
              : '✅ Graph execution completed'
            streamingState.updateState({ reasoningText: newReasoningText })
            
            // Extract content from final_state (handled by extractContent)
            streamingState.extractContent(event)
            const updatedState = streamingState.getState()
            
            if (updatedState.markdownContent) {
              setOutcomesContent(updatedState.markdownContent)
            }
            
            const displayContent = updatedState.fullContent || updatedState.reasoningText || 'Processing...'
            console.log('[App] Graph completed - displayContent length:', displayContent.length, 'fullContent length:', updatedState.fullContent ? updatedState.fullContent.length : 0)
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: displayContent, 
                    isStreaming: true,
                    currentStep: 'Finalizing...'
                  }
                : msg
            ))
          } else if (event.event_type === 'node_error') {
            // Node execution error
            const nodeName = event.node_name || 'Unknown node'
            const errorMsg = event.error || 'Unknown error'
            const state = streamingState.getState()
            const newReasoningText = state.reasoningText 
              ? `${state.reasoningText}\n❌ Error in ${nodeName}: ${errorMsg}`
              : `❌ Error in ${nodeName}: ${errorMsg}`
            streamingState.updateState({ reasoningText: newReasoningText })
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { ...msg, content: newReasoningText, isStreaming: true }
                : msg
            ))
          } else if (event.event_type === 'progress') {
            // Progress update - update current step for spinner
            const currentStep = event.current_step || 'Processing'
            streamingState.updateState({ currentStep })
            const state = streamingState.getState()
            const displayContent = state.reasoningText || state.fullContent || 'Processing...'
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: displayContent, 
                    isStreaming: true,
                    currentStep: currentStep
                  }
                : msg
            ))
          } else if (event.event_type === 'node_started') {
            // Add reasoning step
            const nodeName = event.node_name || 'Processing'
            const state = streamingState.getState()
            const newReasoningText = state.reasoningText 
              ? `${state.reasoningText}\n🔄 ${nodeName}...`
              : `🔄 ${nodeName}...`
            streamingState.updateState({ 
              reasoningText: newReasoningText,
              currentStep: nodeName
            })
            const updatedState = streamingState.getState()
            const displayContent = updatedState.fullContent || updatedState.reasoningText || 'Processing...'
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: displayContent, 
                    isStreaming: true,
                    currentStep: nodeName
                  }
                : msg
            ))
          } else if (event.event_type === 'node_completed') {
            // Update reasoning step when node completes
            const nodeName = event.node_name || 'Processing'
            const state = streamingState.getState()
            const newReasoningText = state.reasoningText 
              ? `${state.reasoningText}\n✓ Completed: ${nodeName}`
              : `✓ Completed: ${nodeName}`
            streamingState.updateState({ reasoningText: newReasoningText })
            
            // Extract content from output_state if available
            if (event.output_state) {
              streamingState.extractContent({ 
                event_type: 'node_completed', 
                output_state: event.output_state 
              })
              const newState = streamingState.getState()
              if (newState.markdownContent) {
                setOutcomesContent(newState.markdownContent)
              }
            }
            
            // Update messages with reasoning (still streaming)
            const updatedState = streamingState.getState()
            const displayContent = updatedState.fullContent || updatedState.reasoningText || 'Processing...'
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: displayContent, 
                    isStreaming: true,
                    currentStep: `Completed: ${nodeName}`
                  }
                : msg
            ))
          } else if (event.event_type === 'result') {
            // Final result received - extract content using centralized logic
            console.log('[App] Result event received:', event)
            console.log('[App] Result event.result keys:', event.result ? Object.keys(event.result) : 'null')
            
            streamingState.updateState({ finalResult: event.result })
            
            // Extract content (already handled by extractContent above, but ensure it's called)
            streamingState.extractContent(event)
            const state = streamingState.getState()
            
            if (state.markdownContent) {
              setOutcomesContent(state.markdownContent)
            }
            
            // Update message with result but keep streaming until graph_completed
            const displayContent = state.fullContent || state.reasoningText || 'Processing...'
            console.log('[App] Result event - displayContent length:', displayContent.length, 'fullContent length:', state.fullContent ? state.fullContent.length : 0)
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId 
                ? { 
                    ...msg, 
                    content: displayContent, 
                    isStreaming: true,
                    currentStep: 'Result received'
                  }
                : msg
            ))
          } else if (event.event_type === 'state_update' && event.state_snapshot) {
            // Extract content from state_update
            streamingState.extractContent(event)
            const state = streamingState.getState()
            if (state.markdownContent) {
              setOutcomesContent(state.markdownContent)
            }
          } else if (event.event_type === 'keep_alive') {
            // Keep-alive event - just acknowledge it to maintain connection
            // Don't update UI, just log for debugging
            console.log('Keep-alive received - connection maintained')
            // Keep the message in streaming state to show spinner
            setMessages(prev => prev.map(msg => 
              msg.id === assistantMessageId && msg.isStreaming
                ? { ...msg, isStreaming: true }
                : msg
            ))
          }

          // Update the assistant message with current content
          // Show reasoning text during streaming, or fullContent if available
          const state = streamingState.getState()
          const displayContent = state.fullContent || state.reasoningText || 'Processing...'
          setMessages(prev => prev.map(msg => 
            msg.id === assistantMessageId 
              ? { 
                  ...msg, 
                  content: displayContent, 
                  isStreaming: true,
                  currentStep: state.currentStep
                }
              : msg
          ))
        }
      )

      // Small delay to ensure all events are processed
      await new Promise(resolve => setTimeout(resolve, 100))

      // Finalize the message - get final state from streaming state hook
      const finalState = streamingState.getState()
      console.log('[App] Finalizing message:', { 
        fullContent: finalState.fullContent ? `present (${finalState.fullContent.length} chars)` : 'missing',
        reasoningText: finalState.reasoningText ? `present (${finalState.reasoningText.length} chars)` : 'missing',
        markdownContent: finalState.markdownContent ? `present (${finalState.markdownContent.length} chars)` : 'missing',
        finalResult: finalState.finalResult ? 'present' : 'missing'
      })
      
      // Check the last message state for any content we might have missed
      const lastMessage = messages.find(msg => msg.id === assistantMessageId)
      if (lastMessage && lastMessage.content && 
          lastMessage.content !== 'Processing...' && 
          !lastMessage.content.includes('Response received') &&
          !finalState.fullContent) {
        console.log('[App] Using content from last message state')
        finalState.fullContent = lastMessage.content
      }
      
      // Build final message
      let finalMessage = ''
      if (finalState.fullContent && finalState.fullContent.length > 0) {
        // If we have full content, show it (with reasoning if available and different)
        if (finalState.reasoningText && finalState.reasoningText.length > 0 && 
            !finalState.fullContent.includes(finalState.reasoningText)) {
          finalMessage = `${finalState.reasoningText}\n\n---\n\n${finalState.fullContent}`
        } else {
          finalMessage = finalState.fullContent
        }
        console.log('[App] Final message from fullContent, length:', finalMessage.length)
      } else if (finalState.reasoningText && finalState.reasoningText.length > 0) {
        // If we only have reasoning text, show that
        finalMessage = finalState.reasoningText
        console.log('[App] Final message from reasoningText, length:', finalMessage.length)
      } else if (finalState.markdownContent && finalState.markdownContent.length > 0) {
        // Use markdown content if available
        finalMessage = finalState.markdownContent
        console.log('[App] Final message from markdownContent, length:', finalMessage.length)
      } else if (finalState.finalResult) {
        // Try to extract from finalResult
        const result = finalState.finalResult
        const content = result.final_answer || result.written_content || result.qa_answer || 
                       result.answer || (result.final_output?.content || result.final_output)
        if (content && typeof content === 'string') {
          finalMessage = content
          console.log('[App] Final message from finalResult, length:', finalMessage.length)
        }
      }
      
      if (!finalMessage || finalMessage.length === 0) {
        console.warn('[App] No content found! State:', finalState)
        finalMessage = 'Response received. Please check the server logs for details.'
      }
      
      console.log('[App] Final message length:', finalMessage.length)
      console.log('[App] Final message preview:', finalMessage.substring(0, 200))
      
      setMessages(prev => prev.map(msg => 
        msg.id === assistantMessageId 
          ? { ...msg, content: finalMessage, isStreaming: false }
          : msg
      ))
      
      // Ensure final outcomes content is set
      const outcomesContent = finalState.markdownContent || finalState.fullContent || finalMessage
      if (outcomesContent && outcomesContent !== 'Response received. Please check the server logs for details.') {
        setOutcomesContent(outcomesContent)
      }

    } catch (err) {
      setError(`Failed to send message: ${err.message}`)
      setMessages(prev => prev.map(msg => 
        msg.id === assistantMessageId 
          ? { ...msg, content: `Error: ${err.message}`, isStreaming: false }
          : msg
      ))
    }
  }

  const handleClearChat = () => {
    setMessages([])
    setOutcomesContent('')
    setError(null)
  }

  return (
    <div className="app">
      <div className="app-container">
        <header className="app-header">
          <h1>Agentic Chat</h1>
          <p>Conversations with AI Assistants</p>
        </header>

        <TopNav
          assistants={assistants}
          selectedAssistant={selectedAssistant}
          onSelectAssistant={setSelectedAssistant}
          datasets={datasets}
          selectedDataset={selectedDataset}
          onSelectDataset={setSelectedDataset}
          loading={loading}
        />

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <SplitScreenLayout
          leftPanel={
            <ChatInterface
              messages={messages}
              onSendMessage={handleSendMessage}
              onClearChat={handleClearChat}
              isStreaming={isStreaming}
              disabled={!selectedAssistant || !selectedDataset}
            />
          }
          rightPanel={
            <OutcomesPanel
              content={outcomesContent}
              isStreaming={isStreaming}
            />
          }
        />
      </div>
    </div>
  )
}

export default Chat

