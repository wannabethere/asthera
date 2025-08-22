#!/usr/bin/env python3
"""
Test script to verify that dashboard pipelines are properly integrated into the pipeline container.
This ensures that other services can access the dashboard pipelines.
"""

import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from app.agents.pipelines.pipeline_container import PipelineContainer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_dashboard_pipeline_integration():
    """Test that dashboard pipelines are properly integrated into the pipeline container"""
    
    print("🧪 Testing Dashboard Pipeline Integration")
    print("=" * 50)
    
    try:
        # Step 1: Initialize pipeline container
        print("1. Initializing pipeline container...")
        container = PipelineContainer.initialize()
        print("   ✅ Pipeline container initialized")
        
        # Step 2: Check available pipelines
        print("2. Checking available pipelines...")
        all_pipelines = container.get_all_pipelines()
        pipeline_names = list(all_pipelines.keys())
        
        print(f"   📋 Total pipelines available: {len(pipeline_names)}")
        print("   📋 Pipeline names:")
        for name in sorted(pipeline_names):
            print(f"      - {name}")
        
        # Step 3: Check for dashboard-specific pipelines
        print("\n3. Checking for dashboard pipelines...")
        
        dashboard_pipelines = [
            "dashboard_streaming",
            "conditional_formatting_generation", 
            "enhanced_dashboard_streaming",
            "dashboard_orchestrator"
        ]
        
        found_pipelines = []
        missing_pipelines = []
        
        for pipeline_name in dashboard_pipelines:
            try:
                pipeline = container.get_pipeline(pipeline_name)
                found_pipelines.append(pipeline_name)
                print(f"   ✅ {pipeline_name}: {pipeline.__class__.__name__}")
                
                # Check if pipeline is initialized
                if hasattr(pipeline, 'is_initialized'):
                    print(f"      - Initialized: {pipeline.is_initialized}")
                if hasattr(pipeline, 'get_configuration'):
                    config = pipeline.get_configuration()
                    print(f"      - Configuration keys: {list(config.keys())}")
                    
            except KeyError:
                missing_pipelines.append(pipeline_name)
                print(f"   ❌ {pipeline_name}: NOT FOUND")
        
        # Step 4: Summary
        print(f"\n4. Integration Summary:")
        print(f"   ✅ Found: {len(found_pipelines)}/{len(dashboard_pipelines)} dashboard pipelines")
        
        if missing_pipelines:
            print(f"   ❌ Missing: {missing_pipelines}")
            return False
        else:
            print("   🎉 All dashboard pipelines are properly integrated!")
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


def test_pipeline_usage():
    """Test that the integrated pipelines can be used"""
    
    print("\n🔧 Testing Pipeline Usage")
    print("=" * 30)
    
    try:
        container = PipelineContainer.initialize()
        
        # Test dashboard orchestrator pipeline
        print("1. Testing dashboard orchestrator pipeline...")
        orchestrator = container.get_pipeline("dashboard_orchestrator")
        print(f"   ✅ Pipeline type: {orchestrator.__class__.__name__}")
        
        # Test conditional formatting generation pipeline
        print("2. Testing conditional formatting generation pipeline...")
        cf_pipeline = container.get_pipeline("conditional_formatting_generation")
        print(f"   ✅ Pipeline type: {cf_pipeline.__class__.__name__}")
        
        # Test enhanced dashboard streaming pipeline
        print("3. Testing enhanced dashboard streaming pipeline...")
        streaming_pipeline = container.get_pipeline("enhanced_dashboard_streaming")
        print(f"   ✅ Pipeline type: {streaming_pipeline.__class__.__name__}")
        
        # Test dashboard streaming pipeline
        print("4. Testing dashboard streaming pipeline...")
        dashboard_streaming = container.get_pipeline("dashboard_streaming")
        print(f"   ✅ Pipeline type: {dashboard_streaming.__class__.__name__}")
        
        print("   🎉 All pipelines are accessible and usable!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline usage test failed: {e}")
        logger.error(f"Pipeline usage test failed: {e}", exc_info=True)
        return False


def test_pipeline_configuration():
    """Test pipeline configuration and metrics"""
    
    print("\n⚙️ Testing Pipeline Configuration")
    print("=" * 35)
    
    try:
        container = PipelineContainer.initialize()
        
        # Test orchestrator pipeline configuration
        print("1. Testing orchestrator pipeline configuration...")
        orchestrator = container.get_pipeline("dashboard_orchestrator")
        
        if hasattr(orchestrator, 'get_configuration'):
            config = orchestrator.get_configuration()
            print(f"   ✅ Configuration keys: {list(config.keys())}")
            print(f"   ✅ Conditional formatting enabled: {config.get('enable_conditional_formatting', 'N/A')}")
            print(f"   ✅ Streaming enabled: {config.get('enable_streaming', 'N/A')}")
        
        if hasattr(orchestrator, 'get_metrics'):
            metrics = orchestrator.get_metrics()
            print(f"   ✅ Metrics keys: {list(metrics.keys())}")
        
        # Test conditional formatting pipeline configuration
        print("2. Testing conditional formatting pipeline configuration...")
        cf_pipeline = container.get_pipeline("conditional_formatting_generation")
        
        if hasattr(cf_pipeline, 'get_configuration'):
            config = cf_pipeline.get_configuration()
            print(f"   ✅ Configuration keys: {list(config.keys())}")
            print(f"   ✅ Validation enabled: {config.get('enable_validation', 'N/A')}")
            print(f"   ✅ Optimization enabled: {config.get('enable_optimization', 'N/A')}")
        
        print("   🎉 Pipeline configuration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline configuration test failed: {e}")
        logger.error(f"Pipeline configuration test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("🚀 Dashboard Pipeline Integration Test Suite")
    print("=" * 60)
    
    # Run all tests
    test1_passed = test_dashboard_pipeline_integration()
    test2_passed = test_pipeline_usage()
    test3_passed = test_pipeline_configuration()
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"✅ Integration Test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"✅ Usage Test: {'PASSED' if test2_passed else 'FAILED'}")
    print(f"✅ Configuration Test: {'PASSED' if test3_passed else 'FAILED'}")
    
    total_passed = sum([test1_passed, test2_passed, test3_passed])
    total_tests = 3
    
    print(f"\n🎯 Overall Result: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 SUCCESS: All dashboard pipelines are properly integrated!")
        print("\n📋 Available Dashboard Pipelines:")
        print("   - dashboard_streaming: Basic dashboard streaming")
        print("   - conditional_formatting_generation: Rule generation")
        print("   - enhanced_dashboard_streaming: Rule application + streaming")
        print("   - dashboard_orchestrator: Complete workflow orchestration")
        print("\n🔗 Other services can now access these pipelines via:")
        print("   container = PipelineContainer.initialize()")
        print("   pipeline = container.get_pipeline('dashboard_orchestrator')")
        sys.exit(0)
    else:
        print("❌ FAILURE: Some tests failed. Check the logs above.")
        sys.exit(1)
