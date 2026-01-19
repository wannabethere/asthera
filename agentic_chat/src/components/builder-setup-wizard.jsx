import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  Target, Database, Table, Users, ChevronRight, ChevronLeft,
  CheckCircle, Circle, Sparkles, Bot, Zap, Shield, TrendingUp,
  FileText, Settings, Play, ArrowRight, Search, Filter
} from 'lucide-react';

const BuilderSetupWizard = () => {
  const navigate = useNavigate();
  const { builderType: urlBuilderType } = useParams();
  const [currentStep, setCurrentStep] = useState(1);
  const builderType = urlBuilderType || 'feature'; // 'feature' or 'case-study'
  
  // Form state
  const [goal, setGoal] = useState('');
  const [selectedDataSource, setSelectedDataSource] = useState(null);
  const [selectedTables, setSelectedTables] = useState([]);
  const [selectedAssistants, setSelectedAssistants] = useState([]);
  const [searchTables, setSearchTables] = useState('');

  // Setup steps
  const setupSteps = [
    { id: 1, name: 'Set Goal', icon: Target, description: 'Define what you want to achieve' },
    { id: 2, name: 'Data Source', icon: Database, description: 'Select where your data comes from' },
    { id: 3, name: 'Select Tables', icon: Table, description: 'Choose relevant tables' },
    { id: 4, name: 'Select Assistants', icon: Users, description: 'Pick AI assistants to help' }
  ];

  // Mock data sources
  const dataSources = [
    {
      id: 'snowflake',
      name: 'Snowflake',
      type: 'Data Warehouse',
      icon: '❄️',
      status: 'connected',
      tables: 45
    },
    {
      id: 'postgres',
      name: 'PostgreSQL',
      type: 'Database',
      icon: '🐘',
      status: 'connected',
      tables: 23
    },
    {
      id: 'bigquery',
      name: 'BigQuery',
      type: 'Data Warehouse',
      icon: '📊',
      status: 'connected',
      tables: 67
    },
    {
      id: 's3',
      name: 'AWS S3',
      type: 'Object Storage',
      icon: '☁️',
      status: 'connected',
      tables: 12
    }
  ];

  // Mock tables (based on selected data source and goal)
  const availableTables = [
    {
      id: 'compliance_controls',
      name: 'compliance_controls',
      rows: 1247,
      columns: 23,
      relevance: 95,
      description: 'Compliance control definitions with status and scores'
    },
    {
      id: 'audit_findings',
      name: 'audit_findings',
      rows: 456,
      columns: 18,
      relevance: 88,
      description: 'Audit findings and remediation tracking'
    },
    {
      id: 'risk_assessments',
      name: 'risk_assessments',
      rows: 892,
      columns: 15,
      relevance: 92,
      description: 'Risk assessment results and scores'
    },
    {
      id: 'evidence_collection',
      name: 'evidence_collection',
      rows: 3421,
      columns: 12,
      relevance: 78,
      description: 'Evidence artifacts for compliance controls'
    },
    {
      id: 'policy_documents',
      name: 'policy_documents',
      rows: 234,
      columns: 10,
      relevance: 65,
      description: 'Policy and procedure documentation'
    }
  ];

  // Mock assistants
  const availableAssistants = [
    {
      id: 'compliance-expert',
      name: 'Compliance Expert',
      icon: Shield,
      color: 'blue',
      description: 'Specializes in regulatory compliance, SOC2, ISO27001, and audit readiness',
      capabilities: ['Framework alignment', 'Control mapping', 'Gap analysis'],
      recommended: true
    },
    {
      id: 'risk-analyst',
      name: 'Risk Analyst',
      icon: TrendingUp,
      color: 'red',
      description: 'Expert in risk quantification using FAIR methodology and CVaR analysis',
      capabilities: ['Risk scoring', 'Likelihood × Impact', 'Monte Carlo simulation'],
      recommended: true
    },
    {
      id: 'data-engineer',
      name: 'Data Engineer',
      icon: Database,
      color: 'purple',
      description: 'Builds optimized data pipelines and feature transformations',
      capabilities: ['Pipeline design', 'SQL optimization', 'Data quality'],
      recommended: false
    },
    {
      id: 'ml-specialist',
      name: 'ML Specialist',
      icon: Sparkles,
      color: 'green',
      description: 'Develops machine learning features and predictive models',
      capabilities: ['Feature engineering', 'Model training', 'Predictions'],
      recommended: false
    }
  ];

  const handleNext = () => {
    if (currentStep < setupSteps.length) {
      setCurrentStep(currentStep + 1);
    } else {
      // Complete setup and launch builder
      console.log('Launching builder with config:', {
        builderType,
        goal,
        dataSource: selectedDataSource,
        tables: selectedTables,
        assistants: selectedAssistants
      });
      
      // Navigate to the appropriate builder
      if (builderType === 'case-study') {
        navigate('/builder/case-study', { 
          state: { 
            goal, 
            dataSource: selectedDataSource, 
            tables: selectedTables, 
            assistants: selectedAssistants 
          } 
        });
      } else {
        navigate('/builder/feature', { 
          state: { 
            goal, 
            dataSource: selectedDataSource, 
            tables: selectedTables, 
            assistants: selectedAssistants 
          } 
        });
      }
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const isStepComplete = (stepId) => {
    switch (stepId) {
      case 1: return goal.trim() !== '';
      case 2: return selectedDataSource !== null;
      case 3: return selectedTables.length > 0;
      case 4: return selectedAssistants.length > 0;
      default: return false;
    }
  };

  const canProceed = () => {
    return isStepComplete(currentStep);
  };

  const toggleTable = (tableId) => {
    if (selectedTables.includes(tableId)) {
      setSelectedTables(selectedTables.filter(id => id !== tableId));
    } else {
      setSelectedTables([...selectedTables, tableId]);
    }
  };

  const toggleAssistant = (assistantId) => {
    if (selectedAssistants.includes(assistantId)) {
      setSelectedAssistants(selectedAssistants.filter(id => id !== assistantId));
    } else {
      setSelectedAssistants([...selectedAssistants, assistantId]);
    }
  };

  const selectAllRecommended = () => {
    const recommended = availableAssistants
      .filter(a => a.recommended)
      .map(a => a.id);
    setSelectedAssistants(recommended);
  };

  const filteredTables = availableTables
    .filter(table => 
      table.name.toLowerCase().includes(searchTables.toLowerCase()) ||
      table.description.toLowerCase().includes(searchTables.toLowerCase())
    )
    .sort((a, b) => b.relevance - a.relevance);

  // Step 1: Set Goal
  const StepSetGoal = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Target className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">What's your goal?</h2>
        <p className="text-gray-600">Tell us what you want to achieve with this builder</p>
      </div>

      <div className="max-w-2xl mx-auto">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Describe your goal
        </label>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder={builderType === 'feature' 
            ? "e.g., Build compliance features with risk scoring for SOC2 audit readiness"
            : "e.g., Create a comprehensive SOC2 audit readiness program with dashboards and alerts for CISO"
          }
          className="w-full p-4 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
          rows={4}
        />
        
        <div className="mt-4 bg-blue-50 rounded-lg p-4 border border-blue-200">
          <div className="flex gap-3">
            <Sparkles className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">💡 Tips for writing a good goal:</p>
              <ul className="list-disc ml-4 space-y-1 text-blue-800">
                <li>Be specific about what you want to achieve</li>
                <li>Mention any frameworks or methodologies (e.g., SOC2, FAIR)</li>
                <li>Include your target audience if applicable</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition-all">
            <div className="font-medium text-sm text-gray-900 mb-1">📊 Example: Feature Engineering</div>
            <div className="text-xs text-gray-600">Build risk and compliance features for audit readiness</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 cursor-pointer hover:border-blue-300 hover:bg-blue-50 transition-all">
            <div className="font-medium text-sm text-gray-900 mb-1">📚 Example: Case Study</div>
            <div className="text-xs text-gray-600">Create executive dashboards and automated alerts</div>
          </div>
        </div>
      </div>
    </div>
  );

  // Step 2: Select Data Source
  const StepSelectDataSource = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Database className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Select Data Source</h2>
        <p className="text-gray-600">Choose where your data is stored</p>
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {dataSources.map((source) => (
            <div
              key={source.id}
              onClick={() => setSelectedDataSource(source.id)}
              className={`p-6 rounded-xl border-2 cursor-pointer transition-all ${
                selectedDataSource === source.id
                  ? 'border-blue-500 bg-blue-50 shadow-lg'
                  : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="text-3xl">{source.icon}</div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{source.name}</h3>
                    <p className="text-xs text-gray-600">{source.type}</p>
                  </div>
                </div>
                {selectedDataSource === source.id && (
                  <CheckCircle className="w-6 h-6 text-blue-600" />
                )}
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                  <span className="text-gray-600">Connected</span>
                </div>
                <span className="text-gray-600">{source.tables} tables</span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 bg-yellow-50 rounded-lg p-4 border border-yellow-200">
          <div className="flex gap-3">
            <Settings className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-900">
              <p className="font-semibold mb-1">Need to connect a new data source?</p>
              <p className="text-yellow-800">Visit Settings → Data Sources to add new connections</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Step 3: Select Tables
  const StepSelectTables = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-teal-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Table className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Select Tables</h2>
        <p className="text-gray-600">Choose tables relevant to your goal</p>
      </div>

      <div className="max-w-4xl mx-auto">
        {/* Search and Filter */}
        <div className="mb-6 flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchTables}
              onChange={(e) => setSearchTables(e.target.value)}
              placeholder="Search tables..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">Filter</span>
          </button>
        </div>

        {/* Selected count */}
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {selectedTables.length} table{selectedTables.length !== 1 ? 's' : ''} selected
          </span>
          <button
            onClick={() => setSelectedTables(filteredTables.map(t => t.id))}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Select all
          </button>
        </div>

        {/* Tables list */}
        <div className="space-y-3">
          {filteredTables.map((table) => {
            const isSelected = selectedTables.includes(table.id);
            return (
              <div
                key={table.id}
                onClick={() => toggleTable(table.id)}
                className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-blue-300'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-semibold text-gray-900">{table.name}</h3>
                      <div className={`px-2 py-0.5 rounded text-xs font-medium ${
                        table.relevance >= 90 ? 'bg-green-100 text-green-800' :
                        table.relevance >= 75 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {table.relevance}% relevant
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{table.description}</p>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{table.rows.toLocaleString()} rows</span>
                      <span>•</span>
                      <span>{table.columns} columns</span>
                    </div>
                  </div>
                  <div className="ml-4">
                    {isSelected ? (
                      <CheckCircle className="w-6 h-6 text-blue-600" />
                    ) : (
                      <Circle className="w-6 h-6 text-gray-300" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 bg-blue-50 rounded-lg p-4 border border-blue-200">
          <div className="flex gap-3">
            <Sparkles className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <p className="font-semibold mb-1">💡 Relevance Score</p>
              <p className="text-blue-800">Tables are ranked by relevance to your goal using AI analysis of column names, descriptions, and data patterns.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Step 4: Select Assistants
  const StepSelectAssistants = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-gradient-to-br from-orange-500 to-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Users className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Select AI Assistants</h2>
        <p className="text-gray-600">Choose assistants that will help you build</p>
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {selectedAssistants.length} assistant{selectedAssistants.length !== 1 ? 's' : ''} selected
          </span>
          <button
            onClick={selectAllRecommended}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            Select all recommended
          </button>
        </div>

        <div className="space-y-4">
          {availableAssistants.map((assistant) => {
            const isSelected = selectedAssistants.includes(assistant.id);
            const Icon = assistant.icon;
            const colorClasses = {
              blue: 'from-blue-500 to-blue-600',
              red: 'from-red-500 to-red-600',
              purple: 'from-purple-500 to-purple-600',
              green: 'from-green-500 to-green-600'
            };

            return (
              <div
                key={assistant.id}
                onClick={() => toggleAssistant(assistant.id)}
                className={`p-5 rounded-xl border-2 cursor-pointer transition-all ${
                  isSelected
                    ? 'border-blue-500 bg-blue-50 shadow-lg'
                    : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className={`w-12 h-12 bg-gradient-to-br ${colorClasses[assistant.color]} rounded-xl flex items-center justify-center flex-shrink-0`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold text-gray-900">{assistant.name}</h3>
                      {assistant.recommended && (
                        <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs font-medium">
                          Recommended
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mb-3">{assistant.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {assistant.capabilities.map((capability, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs"
                        >
                          {capability}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="ml-4">
                    {isSelected ? (
                      <CheckCircle className="w-6 h-6 text-blue-600" />
                    ) : (
                      <Circle className="w-6 h-6 text-gray-300" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-6 bg-green-50 rounded-lg p-4 border border-green-200">
          <div className="flex gap-3">
            <Zap className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-green-900">
              <p className="font-semibold mb-1">⚡ Multiple Assistants Work Together</p>
              <p className="text-green-800">Selected assistants will collaborate to provide comprehensive help based on their specialized expertise.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Progress indicator
  const ProgressIndicator = () => (
    <div className="mb-8">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        {setupSteps.map((step, index) => {
          const isCompleted = currentStep > step.id;
          const isCurrent = currentStep === step.id;
          const Icon = step.icon;
          
          return (
            <div key={step.id} className="flex items-center flex-1">
              <div className={`flex flex-col items-center ${index < setupSteps.length - 1 ? 'flex-1' : ''}`}>
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-all ${
                    isCompleted
                      ? 'bg-green-500 text-white'
                      : isCurrent
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-200 text-gray-400'
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle className="w-6 h-6" />
                  ) : (
                    <Icon className="w-6 h-6" />
                  )}
                </div>
                <div className="text-center">
                  <div
                    className={`text-sm font-medium ${
                      isCurrent ? 'text-blue-600' : isCompleted ? 'text-green-600' : 'text-gray-500'
                    }`}
                  >
                    {step.name}
                  </div>
                  <div className="text-xs text-gray-500 mt-1 hidden md:block">
                    {step.description}
                  </div>
                </div>
              </div>
              {index < setupSteps.length - 1 && (
                <div
                  className={`h-1 flex-1 mx-4 transition-all ${
                    isCompleted ? 'bg-green-500' : 'bg-gray-200'
                  }`}
                  style={{ maxWidth: '100px' }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {builderType === 'feature' ? '🎯 Feature Builder' : '📚 Case Study Builder'} Setup
          </h1>
          <p className="text-gray-600">Let's configure your builder in a few simple steps</p>
        </div>

        {/* Progress Indicator */}
        <ProgressIndicator />

        {/* Step Content */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-6">
          {currentStep === 1 && <StepSetGoal />}
          {currentStep === 2 && <StepSelectDataSource />}
          {currentStep === 3 && <StepSelectTables />}
          {currentStep === 4 && <StepSelectAssistants />}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <button
            onClick={handleBack}
            disabled={currentStep === 1}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all ${
              currentStep === 1
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-white text-gray-700 border-2 border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            }`}
          >
            <ChevronLeft className="w-5 h-5" />
            Back
          </button>

          <div className="text-sm text-gray-600">
            Step {currentStep} of {setupSteps.length}
          </div>

          <button
            onClick={handleNext}
            disabled={!canProceed()}
            className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all ${
              canProceed()
                ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:from-blue-600 hover:to-purple-700 shadow-lg'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            {currentStep === setupSteps.length ? (
              <>
                Launch Builder
                <Play className="w-5 h-5" />
              </>
            ) : (
              <>
                Continue
                <ChevronRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default BuilderSetupWizard;
