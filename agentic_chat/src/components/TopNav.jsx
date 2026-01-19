import AssistantSelector from './AssistantSelector'
import DatasetSelector from './DatasetSelector'
import './TopNav.css'

function TopNav({ assistants, selectedAssistant, onSelectAssistant, datasets, selectedDataset, onSelectDataset, loading }) {
  return (
    <div className="top-nav">
      <div className="nav-content">
        <div className="nav-selectors">
          <AssistantSelector
            assistants={assistants}
            selectedAssistant={selectedAssistant}
            onSelectAssistant={onSelectAssistant}
            loading={loading}
            compact={true}
          />
          <DatasetSelector
            datasets={datasets}
            selectedDataset={selectedDataset}
            onSelectDataset={onSelectDataset}
            loading={false}
            compact={true}
          />
        </div>
      </div>
    </div>
  )
}

export default TopNav

