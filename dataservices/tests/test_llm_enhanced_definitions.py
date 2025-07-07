#!/usr/bin/env python3
"""
Test script for LLM-enhanced definitions
Demonstrates how metrics, views, and calculated columns are created using LLMDefinitionGenerator
and stored in the database with enhanced metadata.
"""

import asyncio
import json
from datetime import datetime
from app.service.models import MetricCreate, ViewCreate, CalculatedColumnCreate
from app.schemas.dbmodels import SQLColumn, CalculatedColumn, Table, Project, Dataset, Metric, View
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")

async def test_llm_enhanced_definitions():
    """Test creating metrics, views, and calculated columns with LLM enhancement"""
    
    # Create async engine and session
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            print("🧪 Testing LLM-Enhanced Definitions")
            print("=" * 50)
            
            # Step 1: Create a test project
            print("\n📁 Step 1: Creating test project...")
            project = Project(
                project_id="llm_enhanced_test",
                display_name="LLM Enhanced Definitions Test",
                description="Project to test LLM-enhanced metric, view, and calculated column creation",
                created_by="test_user",
                status="draft",
                json_metadata={
                    "business_context": {
                        "domain": "E-commerce",
                        "key_metrics": ["revenue", "conversion_rate", "customer_lifetime_value"],
                        "business_goals": ["increase_sales", "improve_customer_satisfaction"],
                        "kpi_focus": ["monthly_recurring_revenue", "customer_acquisition_cost"]
                    }
                }
            )
            db.add(project)
            await db.commit()
            await db.refresh(project)
            print(f"✅ Created project: {project.project_id}")
            
            # Step 2: Create a test dataset
            print("\n📊 Step 2: Creating test dataset...")
            dataset = Dataset(
                project_id=project.project_id,
                name="sales_data",
                display_name="Sales Data",
                description="Sales data for testing LLM-enhanced definitions"
            )
            db.add(dataset)
            await db.commit()
            await db.refresh(dataset)
            print(f"✅ Created dataset: {dataset.dataset_id}")
            
            # Step 3: Create a test table with columns
            print("\n📋 Step 3: Creating test table with columns...")
            table = Table(
                project_id=project.project_id,
                dataset_id=dataset.dataset_id,
                name="sales",
                display_name="Sales Table",
                description="Sales transactions table for testing LLM enhancements",
                table_type="table"
            )
            db.add(table)
            await db.commit()
            await db.refresh(table)
            print(f"✅ Created table: {table.table_id}")
            
            # Add regular columns to the table
            regular_columns = [
                SQLColumn(
                    table_id=table.table_id,
                    name="order_id",
                    display_name="Order ID",
                    description="Unique order identifier",
                    column_type="column",
                    data_type="INTEGER",
                    usage_type="identifier",
                    is_nullable=False,
                    is_primary_key=True,
                    ordinal_position=1,
                    modified_by="test_user"
                ),
                SQLColumn(
                    table_id=table.table_id,
                    name="customer_id",
                    display_name="Customer ID",
                    description="Customer who placed the order",
                    column_type="column",
                    data_type="INTEGER",
                    usage_type="identifier",
                    is_nullable=False,
                    ordinal_position=2,
                    modified_by="test_user"
                ),
                SQLColumn(
                    table_id=table.table_id,
                    name="order_date",
                    display_name="Order Date",
                    description="Date when order was placed",
                    column_type="column",
                    data_type="TIMESTAMP",
                    usage_type="timestamp",
                    is_nullable=False,
                    ordinal_position=3,
                    modified_by="test_user"
                ),
                SQLColumn(
                    table_id=table.table_id,
                    name="quantity",
                    display_name="Quantity",
                    description="Number of items ordered",
                    column_type="column",
                    data_type="INTEGER",
                    usage_type="measure",
                    is_nullable=False,
                    ordinal_position=4,
                    modified_by="test_user"
                ),
                SQLColumn(
                    table_id=table.table_id,
                    name="unit_price",
                    display_name="Unit Price",
                    description="Price per unit",
                    column_type="column",
                    data_type="DECIMAL(10,2)",
                    usage_type="measure",
                    is_nullable=False,
                    ordinal_position=5,
                    modified_by="test_user"
                ),
                SQLColumn(
                    table_id=table.table_id,
                    name="total_amount",
                    display_name="Total Amount",
                    description="Total order amount",
                    column_type="column",
                    data_type="DECIMAL(10,2)",
                    usage_type="measure",
                    is_nullable=False,
                    ordinal_position=6,
                    modified_by="test_user"
                )
            ]
            
            for col in regular_columns:
                db.add(col)
            await db.commit()
            print(f"✅ Added {len(regular_columns)} regular columns")
            
            # Step 4: Test LLM-enhanced metric creation
            print("\n📊 Step 4: Testing LLM-enhanced metric creation...")
            from app.service.project_workflow_service import MetricsService
            
            metrics_service = MetricsService(db, project.project_id)
            
            metric_data = MetricCreate(
                name="total_revenue",
                display_name="Total Revenue",
                description="Calculate total revenue from all orders",
                metric_sql="SELECT SUM(total_amount) FROM sales",
                metric_type="sum",
                aggregation_type="sum"
            )
            
            try:
                enhanced_metric = await metrics_service.add_metric(table.table_id, metric_data, "test_user")
                print(f"✅ Created enhanced metric: {enhanced_metric.name}")
                print(f"   - Display Name: {enhanced_metric.display_name}")
                print(f"   - Description: {enhanced_metric.description}")
                print(f"   - Enhanced: {enhanced_metric.json_metadata.get('generated_by') == 'llm_definition_generator' if enhanced_metric.json_metadata else False}")
                print(f"   - Confidence Score: {enhanced_metric.json_metadata.get('confidence_score') if enhanced_metric.json_metadata else 'N/A'}")
                print(f"   - Chain of Thought: {enhanced_metric.json_metadata.get('chain_of_thought', 'N/A')[:100]}...")
                print(f"   - Suggestions: {len(enhanced_metric.json_metadata.get('suggestions', []))} suggestions")
            except Exception as e:
                print(f"❌ Error creating enhanced metric: {str(e)}")
            
            # Step 5: Test LLM-enhanced view creation
            print("\n👁️ Step 5: Testing LLM-enhanced view creation...")
            
            view_data = ViewCreate(
                name="daily_sales_summary",
                display_name="Daily Sales Summary",
                description="View showing daily sales summary for reporting",
                view_sql="SELECT DATE(order_date) as sale_date, COUNT(*) as order_count, SUM(total_amount) as daily_revenue FROM sales GROUP BY DATE(order_date)",
                view_type="aggregated"
            )
            
            try:
                enhanced_view = await metrics_service.add_view(table.table_id, view_data, "test_user")
                print(f"✅ Created enhanced view: {enhanced_view.name}")
                print(f"   - Display Name: {enhanced_view.display_name}")
                print(f"   - Description: {enhanced_view.description}")
                print(f"   - Enhanced: {enhanced_view.json_metadata.get('generated_by') == 'llm_definition_generator' if enhanced_view.json_metadata else False}")
                print(f"   - Confidence Score: {enhanced_view.json_metadata.get('confidence_score') if enhanced_view.json_metadata else 'N/A'}")
                print(f"   - Chain of Thought: {enhanced_view.json_metadata.get('chain_of_thought', 'N/A')[:100]}...")
                print(f"   - Suggestions: {len(enhanced_view.json_metadata.get('suggestions', []))} suggestions")
            except Exception as e:
                print(f"❌ Error creating enhanced view: {str(e)}")
            
            # Step 6: Test LLM-enhanced calculated column creation
            print("\n🧮 Step 6: Testing LLM-enhanced calculated column creation...")
            
            calc_column_data = {
                "name": "profit_margin",
                "display_name": "Profit Margin",
                "description": "Calculate profit margin percentage",
                "calculation_sql": "CASE WHEN unit_price > 0 THEN ((total_amount - (quantity * unit_price * 0.7)) / total_amount) * 100 ELSE 0 END",
                "data_type": "DECIMAL(5,2)",
                "usage_type": "calculated",
                "is_nullable": True,
                "dependencies": ["quantity", "unit_price", "total_amount"],
                "metadata": {
                    "business_purpose": "Calculate profit margin for pricing analysis",
                    "formula": "((total_amount - cost) / total_amount) * 100"
                }
            }
            
            try:
                enhanced_calc_column = await metrics_service.add_calculated_column(table.table_id, calc_column_data, "test_user")
                print(f"✅ Created enhanced calculated column: {enhanced_calc_column.name}")
                print(f"   - Display Name: {enhanced_calc_column.display_name}")
                print(f"   - Description: {enhanced_calc_column.description}")
                print(f"   - Column Type: {enhanced_calc_column.column_type}")
                print(f"   - Enhanced: {enhanced_calc_column.json_metadata.get('generated_by') == 'llm_definition_generator' if enhanced_calc_column.json_metadata else False}")
                print(f"   - Confidence Score: {enhanced_calc_column.json_metadata.get('confidence_score') if enhanced_calc_column.json_metadata else 'N/A'}")
                print(f"   - Chain of Thought: {enhanced_calc_column.json_metadata.get('chain_of_thought', 'N/A')[:100]}...")
                print(f"   - Suggestions: {len(enhanced_calc_column.json_metadata.get('suggestions', []))} suggestions")
                
                # Get the associated CalculatedColumn
                calc_column = await db.execute(
                    select(CalculatedColumn).where(CalculatedColumn.column_id == enhanced_calc_column.column_id)
                )
                calc_column = calc_column.scalar_one_or_none()
                
                if calc_column:
                    print(f"   - Calculation SQL: {calc_column.calculation_sql}")
                    print(f"   - Dependencies: {calc_column.dependencies}")
                
            except Exception as e:
                print(f"❌ Error creating enhanced calculated column: {str(e)}")
            
            # Step 7: Query and display all enhanced definitions
            print("\n📋 Step 7: Querying all enhanced definitions...")
            
            # Get all metrics
            metrics = await db.execute(
                select(Metric).where(Metric.table_id == table.table_id)
            )
            metrics = metrics.scalars().all()
            
            print(f"📊 Metrics ({len(metrics)}):")
            for metric in metrics:
                enhanced = metric.json_metadata.get('generated_by') == 'llm_definition_generator' if metric.json_metadata else False
                print(f"   - {metric.name} ({'Enhanced' if enhanced else 'Standard'})")
                if enhanced:
                    print(f"     Confidence: {metric.json_metadata.get('confidence_score', 'N/A')}")
                    print(f"     Related Tables: {metric.json_metadata.get('related_tables', [])}")
            
            # Get all views
            views = await db.execute(
                select(View).where(View.table_id == table.table_id)
            )
            views = views.scalars().all()
            
            print(f"👁️ Views ({len(views)}):")
            for view in views:
                enhanced = view.json_metadata.get('generated_by') == 'llm_definition_generator' if view.json_metadata else False
                print(f"   - {view.name} ({'Enhanced' if enhanced else 'Standard'})")
                if enhanced:
                    print(f"     Confidence: {view.json_metadata.get('confidence_score', 'N/A')}")
                    print(f"     Related Tables: {view.json_metadata.get('related_tables', [])}")
            
            # Get all calculated columns
            calc_columns = await db.execute(
                select(SQLColumn).where(
                    SQLColumn.table_id == table.table_id,
                    SQLColumn.column_type == 'calculated_column'
                )
            )
            calc_columns = calc_columns.scalars().all()
            
            print(f"🧮 Calculated Columns ({len(calc_columns)}):")
            for col in calc_columns:
                enhanced = col.json_metadata.get('generated_by') == 'llm_definition_generator' if col.json_metadata else False
                print(f"   - {col.name} ({'Enhanced' if enhanced else 'Standard'})")
                if enhanced:
                    print(f"     Confidence: {col.json_metadata.get('confidence_score', 'N/A')}")
                    print(f"     Related Tables: {col.json_metadata.get('related_tables', [])}")
            
            # Step 8: Show detailed metadata for one enhanced definition
            print("\n🔍 Step 8: Detailed metadata for enhanced definitions...")
            
            if metrics:
                enhanced_metric = next((m for m in metrics if m.json_metadata and m.json_metadata.get('generated_by') == 'llm_definition_generator'), None)
                if enhanced_metric:
                    print(f"📊 Enhanced Metric Details - {enhanced_metric.name}:")
                    print(f"   - Original Name: {enhanced_metric.json_metadata.get('original_data', {}).get('name', 'N/A')}")
                    print(f"   - Enhanced Name: {enhanced_metric.name}")
                    print(f"   - Enhanced Display Name: {enhanced_metric.display_name}")
                    print(f"   - Enhanced Description: {enhanced_metric.description}")
                    print(f"   - Enhanced SQL: {enhanced_metric.metric_sql}")
                    print(f"   - Chain of Thought: {enhanced_metric.json_metadata.get('chain_of_thought', 'N/A')}")
                    print(f"   - Related Tables: {enhanced_metric.json_metadata.get('related_tables', [])}")
                    print(f"   - Related Columns: {enhanced_metric.json_metadata.get('related_columns', [])}")
                    print(f"   - Suggestions: {enhanced_metric.json_metadata.get('suggestions', [])}")
                    print(f"   - Metadata Keys: {list(enhanced_metric.json_metadata.keys())}")
            
            print("\n✅ Test completed successfully!")
            print("\n🎯 Key Benefits of LLM Enhancement:")
            print("   - Enhanced business-friendly names and descriptions")
            print("   - Optimized SQL queries with proper formatting")
            print("   - Detailed chain of thought explanations")
            print("   - Related tables and columns for data lineage")
            print("   - Comprehensive metadata for governance")
            print("   - Confidence scores for quality assessment")
            print("   - Actionable suggestions for improvement")
            print("   - Fallback to original method if LLM fails")
            
        except Exception as e:
            print(f"❌ Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            print("\n🧹 Cleaning up test data...")
            try:
                # Delete in reverse order due to foreign key constraints
                # Delete calculated columns
                calc_columns = await db.execute(
                    select(CalculatedColumn).join(SQLColumn).where(SQLColumn.table_id == table.table_id)
                )
                for calc_col in calc_columns.scalars().all():
                    await db.delete(calc_col)
                
                # Delete SQLColumns
                columns = await db.execute(
                    select(SQLColumn).where(SQLColumn.table_id == table.table_id)
                )
                for col in columns.scalars().all():
                    await db.delete(col)
                
                # Delete metrics and views
                metrics = await db.execute(select(Metric).where(Metric.table_id == table.table_id))
                for metric in metrics.scalars().all():
                    await db.delete(metric)
                
                views = await db.execute(select(View).where(View.table_id == table.table_id))
                for view in views.scalars().all():
                    await db.delete(view)
                
                # Delete table, dataset, and project
                await db.delete(table)
                await db.delete(dataset)
                await db.delete(project)
                await db.commit()
                print("✅ Cleanup completed")
            except Exception as e:
                print(f"⚠️ Cleanup error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_llm_enhanced_definitions()) 