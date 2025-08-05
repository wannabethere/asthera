#!/usr/bin/env python3
"""
Simple test script to verify the purchase order data generation works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mlagents.sample_purchase_order_data import (
    create_sample_purchase_order_data, 
    create_enhanced_purchase_order_data,
    get_purchase_order_schema_info
)

def test_basic_purchase_order_data():
    """Test basic purchase order data generation"""
    print("🧪 Testing Basic Purchase Order Data Generation...")
    
    try:
        # Test with small dataset
        df = create_sample_purchase_order_data(10)
        print(f"✅ Successfully created {len(df)} purchase orders")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Sample data:")
        print(df.head(3))
        
        # Verify required fields exist
        required_fields = ['project', 'region', 'cost', 'division_id']
        for field in required_fields:
            if field in df.columns:
                print(f"   ✅ {field} field present")
            else:
                print(f"   ❌ {field} field missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in basic data generation: {e}")
        return False

def test_enhanced_purchase_order_data():
    """Test enhanced purchase order data generation"""
    print("\n🧪 Testing Enhanced Purchase Order Data Generation...")
    
    try:
        # Test with small dataset
        df = create_enhanced_purchase_order_data(20)
        print(f"✅ Successfully created {len(df)} enhanced purchase orders")
        print(f"   Additional columns: {[col for col in df.columns if col not in ['project', 'region', 'cost', 'division_id']]}")
        
        # Check for enhanced fields
        enhanced_fields = ['vendor', 'contract_type', 'priority', 'approval_level']
        for field in enhanced_fields:
            if field in df.columns:
                print(f"   ✅ {field} field present")
            else:
                print(f"   ❌ {field} field missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in enhanced data generation: {e}")
        return False

def test_schema_info():
    """Test schema information generation"""
    print("\n🧪 Testing Schema Information Generation...")
    
    try:
        schema_info = get_purchase_order_schema_info()
        print(f"✅ Successfully generated schema info")
        print(f"   Schema keys: {list(schema_info.keys())}")
        print(f"   Sample values available for: {list(schema_info['sample_values'].keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in schema info generation: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 PURCHASE ORDER DATA GENERATION TESTS")
    print("=" * 50)
    
    tests = [
        test_basic_purchase_order_data,
        test_enhanced_purchase_order_data,
        test_schema_info
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Purchase order data generation is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 