import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './components/HomePage'
import Chat from './components/Chat'
import BuilderSetupWizard from './components/builder-setup-wizard'
import FinalCaseStudyBuilder from './components/final-case-study-builder'
import FinalFeatureBuilder from './components/final-feature-builder'
import HRComplianceStrategyMap from './components/hr_compliance_strategy_map_mock_react'
import HRComplianceScorecard from './components/HRComplianceStrategy'
import './App.css'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/strategy-map" element={<HRComplianceStrategyMap />} />
        <Route path="/scorecard-builder" element={<HRComplianceScorecard />} />
        <Route path="/builder-setup/:builderType" element={<BuilderSetupWizard />} />
        <Route path="/builder/case-study" element={<FinalCaseStudyBuilder />} />
        <Route path="/builder/feature" element={<FinalFeatureBuilder />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App
