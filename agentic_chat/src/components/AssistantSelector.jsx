import './AssistantSelector.css'

function AssistantSelector({ assistants, selectedAssistant, onSelectAssistant, loading, compact = false }) {
  if (loading) {
    return (
      <div className="assistant-selector">
        <div className="loading">Loading assistants...</div>
      </div>
    )
  }

  if (assistants.length === 0) {
    return (
      <div className="assistant-selector">
        <div className="empty-state">No assistants available</div>
      </div>
    )
  }

  return (
    <div className={`assistant-selector ${compact ? 'compact' : ''}`}>
      <label htmlFor="assistant-select" className="selector-label">
        {compact ? 'Assistant:' : 'Select Assistant:'}
      </label>
      <select
        id="assistant-select"
        value={selectedAssistant?.assistant_id || ''}
        onChange={(e) => {
          const assistant = assistants.find(a => a.assistant_id === e.target.value)
          onSelectAssistant(assistant)
        }}
        className="selector-dropdown"
      >
        {assistants.map(assistant => (
          <option key={assistant.assistant_id} value={assistant.assistant_id}>
            {assistant.name || assistant.assistant_id}
            {assistant.description ? ` - ${assistant.description}` : ''}
          </option>
        ))}
      </select>
      {selectedAssistant && !compact && (
        <div className="assistant-info">
          <div className="info-item">
            <strong>ID:</strong> {selectedAssistant.assistant_id}
          </div>
          {selectedAssistant.description && (
            <div className="info-item">
              <strong>Description:</strong> {selectedAssistant.description}
            </div>
          )}
          <div className="info-item">
            <strong>Graphs:</strong> {selectedAssistant.graph_count || 0}
          </div>
        </div>
      )}
    </div>
  )
}

export default AssistantSelector

