import './SplitScreenLayout.css'

function SplitScreenLayout({ leftPanel, rightPanel, leftTitle, rightTitle }) {
  return (
    <div className="split-screen-layout">
      <div className="split-panel left-panel">
        {leftTitle && (
          <div className="panel-header">
            <h3>{leftTitle}</h3>
          </div>
        )}
        <div className="panel-content">
          {leftPanel}
        </div>
      </div>
      <div className="split-panel right-panel">
        {rightTitle && (
          <div className="panel-header">
            <h3>{rightTitle}</h3>
          </div>
        )}
        <div className="panel-content">
          {rightPanel}
        </div>
      </div>
    </div>
  )
}

export default SplitScreenLayout

