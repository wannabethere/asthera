import React from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, BookOpen, Target, ArrowRight, Map, LayoutDashboard } from 'lucide-react';

const HomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 flex items-center justify-center p-6">
      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Welcome to Agentic Chat
          </h1>
          <p className="text-xl text-gray-600">
            Choose how you'd like to get started
          </p>
        </div>

        {/* Action Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Current Chat Button */}
          <button
            onClick={() => navigate('/chat')}
            className="group bg-white rounded-2xl p-8 border-2 border-gray-200 hover:border-blue-500 hover:shadow-xl transition-all duration-300 text-left"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <MessageSquare className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Current Chat
            </h3>
            <p className="text-gray-600 mb-6 leading-relaxed">
              Start a conversation with AI assistants. Ask questions, get insights, and explore your data through natural language.
            </p>
            <div className="flex items-center text-blue-600 font-medium group-hover:translate-x-2 transition-transform">
              <span>Start Chatting</span>
              <ArrowRight className="w-5 h-5 ml-2" />
            </div>
          </button>

          {/* Case Study Builder Button */}
          <button
            onClick={() => navigate('/builder-setup/case-study')}
            className="group bg-white rounded-2xl p-8 border-2 border-gray-200 hover:border-purple-500 hover:shadow-xl transition-all duration-300 text-left"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <BookOpen className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Case Study Builder
            </h3>
            <p className="text-gray-600 mb-6 leading-relaxed">
              Create comprehensive solutions with dashboards, alerts, and automations. Build complete case studies tailored to your personas.
            </p>
            <div className="flex items-center text-purple-600 font-medium group-hover:translate-x-2 transition-transform">
              <span>Build Case Study</span>
              <ArrowRight className="w-5 h-5 ml-2" />
            </div>
          </button>

          {/* Feature Builder Button - Direct to Leen planner (4-step flow) */}
          <button
            onClick={() => navigate('/builder/feature')}
            className="group bg-white rounded-2xl p-8 border-2 border-gray-200 hover:border-green-500 hover:shadow-xl transition-all duration-300 text-left"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-teal-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <Target className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Feature Builder
            </h3>
            <p className="text-gray-600 mb-6 leading-relaxed">
              VM Report & Asset Inventory. 4-step flow: select sources → capabilities → data models → build. Final summary in markdown.
            </p>
            <div className="flex items-center text-green-600 font-medium group-hover:translate-x-2 transition-transform">
              <span>Build Features</span>
              <ArrowRight className="w-5 h-5 ml-2" />
            </div>
          </button>

          {/* Strategy Map Button */}
          <button
            onClick={() => navigate('/strategy-map')}
            className="group bg-white rounded-2xl p-8 border-2 border-gray-200 hover:border-amber-500 hover:shadow-xl transition-all duration-300 text-left"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <Map className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Strategy Map
            </h3>
            <p className="text-gray-600 mb-6 leading-relaxed">
              Explore HR compliance data lineage. See sources, entities, features, and metrics in an interactive strategy map.
            </p>
            <div className="flex items-center text-amber-600 font-medium group-hover:translate-x-2 transition-transform">
              <span>Explore Map</span>
              <ArrowRight className="w-5 h-5 ml-2" />
            </div>
          </button>

          {/* Scorecard Builder Button */}
          <button
            onClick={() => navigate('/scorecard-builder')}
            className="group bg-white rounded-2xl p-8 border-2 border-gray-200 hover:border-rose-500 hover:shadow-xl transition-all duration-300 text-left"
          >
            <div className="w-16 h-16 bg-gradient-to-br from-rose-500 to-red-600 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <LayoutDashboard className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              KPI Scorecard
            </h3>
            <p className="text-gray-600 mb-6 leading-relaxed">
              Build hierarchical KPI scorecards. Pin metrics and features from the strategy map, save/load/export scorecards.
            </p>
            <div className="flex items-center text-rose-600 font-medium group-hover:translate-x-2 transition-transform">
              <span>Build Scorecard</span>
              <ArrowRight className="w-5 h-5 ml-2" />
            </div>
          </button>
        </div>

        {/* Footer Note */}
        <div className="mt-12 text-center">
          <p className="text-sm text-gray-500">
            All builders use AI assistants to help you create powerful solutions
          </p>
        </div>
      </div>
    </div>
  );
};

export default HomePage;

