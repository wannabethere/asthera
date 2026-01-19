import './DatasetSelector.css'

function DatasetSelector({ datasets, selectedDataset, onSelectDataset, loading, compact = false }) {
  if (loading) {
    return (
      <div className="dataset-selector">
        <div className="loading">Loading datasets...</div>
      </div>
    )
  }

  if (datasets.length === 0) {
    return (
      <div className="dataset-selector">
        <div className="empty-state">No datasets available</div>
      </div>
    )
  }

  return (
    <div className={`dataset-selector ${compact ? 'compact' : ''}`}>
      <label htmlFor="dataset-select" className="selector-label">
        {compact ? 'Dataset:' : 'Select Dataset:'}
      </label>
      <select
        id="dataset-select"
        value={selectedDataset?.project_id || ''}
        onChange={(e) => {
          const dataset = datasets.find(d => d.project_id === e.target.value)
          onSelectDataset(dataset)
        }}
        className="selector-dropdown"
      >
        <option value="">-- Select a dataset --</option>
        {datasets.map(dataset => (
          <option key={dataset.project_id} value={dataset.project_id}>
            {dataset.name || dataset.title || dataset.project_id}
          </option>
        ))}
      </select>
      {selectedDataset && !compact && (
        <div className="dataset-info">
          <div className="info-item">
            <strong>Project ID:</strong> {selectedDataset.project_id}
          </div>
          {selectedDataset.description && (
            <div className="info-item">
              <strong>Description:</strong> {selectedDataset.description}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DatasetSelector

