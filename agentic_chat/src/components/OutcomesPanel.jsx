import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './OutcomesPanel.css'

function OutcomesPanel({ content, isStreaming }) {
  if (!content && !isStreaming) {
    return (
      <div className="outcomes-panel">
        <div className="outcomes-header">
          <h2>Outcomes</h2>
        </div>
        <div className="outcomes-content empty">
          <p>Results will appear here as the assistant processes your query.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="outcomes-panel">
      <div className="outcomes-header">
        <h2>Outcomes</h2>
        {isStreaming && (
          <span className="streaming-badge">
            <span className="streaming-dot"></span>
            Streaming...
          </span>
        )}
      </div>
      <div className="outcomes-content">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          className="markdown-content"
        >
          {content || 'Processing...'}
        </ReactMarkdown>
        {isStreaming && (
          <div className="streaming-indicator">
            <span className="typing-cursor">▊</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default OutcomesPanel

