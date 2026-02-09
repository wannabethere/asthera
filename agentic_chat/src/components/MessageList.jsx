import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './MessageList.css'

function MessageList({ messages, isStreaming, messagesEndRef }) {
  if (messages.length === 0) {
    return (
      <div className="message-list empty">
        <div className="empty-message">
          <p>Start a conversation by sending a message below.</p>
          <p className="hint">Select an assistant and dataset, then type your question.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="message-list">
      {messages.map((message, index) => {
        // Skip reasoning messages that are duplicates
        if (message.type === 'reasoning') {
          return (
            <div 
              key={message.id} 
              className="message message-reasoning"
            >
              <div className="message-content">
                {message.content}
              </div>
            </div>
          )
        }

        const content = message.content || (message.isStreaming ? 'Thinking...' : '')
        const isAssistant = message.role === 'assistant'
        const showAsMarkdown = isAssistant && content && content !== 'Thinking...'

        return (
          <div 
            key={message.id} 
            className={`message message-${message.role}`}
          >
            <div className="message-content">
              {showAsMarkdown ? (
                <div className="message-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </div>
              ) : (
                content
              )}
              {message.isStreaming && (
                <div className="spinning-wheel-container">
                  <div className="spinning-wheel"></div>
                  {message.currentStep && (
                    <span className="current-step-text">{message.currentStep}</span>
                  )}
                </div>
              )}
              {!message.isStreaming && isAssistant && message.type !== 'reasoning' && (
                <span className="message-checkmark">✓</span>
              )}
            </div>
          </div>
        )
      })}
      {isStreaming && messages.length > 0 && messages[messages.length - 1].role === 'user' && (
        <div className="message message-assistant">
          <div className="message-content">
            Processing...
            <span className="streaming-indicator">●</span>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  )
}

export default MessageList

