#!/usr/bin/env python3
"""
Test script for calculated columns functionality
Demonstrates how calculated columns are now treated as SQLColumns with type 'calculated_column'
"""

import asyncio
import json
from datetime import datetime
from app.service.models import CalculatedColumnCreate
from app.schemas.dbmodels import SQLColumn, CalculatedColumn, Table, Project, Dataset
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")

async def test_calculated_column_creation():
    """Test creating a calculated column as a SQLColumn with type 'calculated_column'"""
    
    # Create async engine and session
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            print("🧪 Testing Calculated Column Creation")
            print("=" * 50)
            
            # Step 1: Create a test project
            print("\n📁 Step 1: Creating test project...")
            project = Project(
                project_id="test_calc_project",
                display_name="Test Calculated Columns Project",
                description="Project to test calculated column functionality",
                created_by="test_user",
                status="draft"
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
                description="Sales data for testing calculated columns"
            )
            db.add(dataset)
            await db.commit()
            await db.refresh(dataset)
            print(f"✅ Created dataset: {dataset.dataset_id}")
            
            # Step 3: Create a test table
            print("\n📋 Step 3: Creating test table...")
            table = Table(
                project_id=project.project_id,
                dataset_id=dataset.dataset_id,
                name="sales",
                display_name="Sales Table",
                description="Sales transactions table",
                table_type="table"
            )
            db.add(table)
            await db.commit()
            await db.refresh(table)
            print(f"✅ Created table: {table.table_id}")
            
            # Step 4: Add regular columns to the table
            print("\n📝 Step 4: Adding regular columns...")
            regular_columns = [
                SQLColumn(
                    table_id=table.table_id,
                    name="quantity",
                    display_name="Quantity",
                    description="Number of items sold",
                    column_type="column",
                    data_type="INTEGER",
                    usage_type="measure",
                    is_nullable=False,
                    ordinal_position=1,
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
                    ordinal_position=2,
                    modified_by="test_user"
                )
            ]
            
            for col in regular_columns:
                db.add(col)
            await db.commit()
            print(f"✅ Added {len(regular_columns)} regular columns")
            
            # Step 5: Create calculated column data
            print("\n🧮 Step 5: Creating calculated column...")
            calc_column_data = CalculatedColumnCreate(
                name="total_amount",
                display_name="Total Amount",
                description="Total amount (quantity * unit_price)",
                calculation_sql="quantity * unit_price",
                data_type="DECIMAL(10,2)",
                usage_type="calculated",
                is_nullable=True,
                is_primary_key=False,
                is_foreign_key=False,
                ordinal_position=3,
                dependencies=["quantity", "unit_price"],
                metadata={
                    "business_purpose": "Calculate total sale amount",
                    "formula": "quantity * unit_price",
                    "category": "financial"
                }
            )
            
            # Step 6: Create the calculated column as SQLColumn
            print("\n🔧 Step 6: Creating SQLColumn with type 'calculated_column'...")
            calculated_column = SQLColumn(
                table_id=table.table_id,
                name=calc_column_data.name,
                display_name=calc_column_data.display_name,
                description=calc_column_data.description,
                column_type='calculated_column',  # This is the key difference!
                data_type=calc_column_data.data_type,
                usage_type=calc_column_data.usage_type,
                is_nullable=calc_column_data.is_nullable,
                is_primary_key=calc_column_data.is_primary_key,
                is_foreign_key=calc_column_data.is_foreign_key,
                default_value=calc_column_data.default_value,
                ordinal_position=calc_column_data.ordinal_position,
                json_metadata=calc_column_data.metadata,
                modified_by="test_user"
            )
            
            db.add(calculated_column)
            await db.commit()
            await db.refresh(calculated_column)
            print(f"✅ Created calculated column SQLColumn: {calculated_column.column_id}")
            
            # Step 7: Create the associated CalculatedColumn with calculation details
            print("\n⚙️ Step 7: Creating associated CalculatedColumn...")
            calc_column = CalculatedColumn(
                column_id=calculated_column.column_id,
                calculation_sql=calc_column_data.calculation_sql,
                function_id=calc_column_data.function_id,
                dependencies=calc_column_data.dependencies,
                modified_by="test_user"
            )
            
            db.add(calc_column)
            await db.commit()
            await db.refresh(calc_column)
            print(f"✅ Created CalculatedColumn: {calc_column.calculated_column_id}")
            
            # Step 8: Verify the relationship
            print("\n🔍 Step 8: Verifying the relationship...")
            # Query the calculated column with its associated calculation
            result = await db.execute(
                select(SQLColumn)
                .options(selectinload(SQLColumn.calculated_column))
                .where(SQLColumn.column_id == calculated_column.column_id)
            )
            column_with_calc = result.scalar_one()
            
            print(f"📊 Column Details:")
            print(f"   - Column ID: {column_with_calc.column_id}")
            print(f"   - Name: {column_with_calc.name}")
            print(f"   - Column Type: {column_with_calc.column_type}")
            print(f"   - Data Type: {column_with_calc.data_type}")
            print(f"   - Usage Type: {column_with_calc.usage_type}")
            print(f"   - Has CalculatedColumn: {column_with_calc.calculated_column is not None}")
            
            if column_with_calc.calculated_column:
                print(f"   - Calculation SQL: {column_with_calc.calculated_column.calculation_sql}")
                print(f"   - Dependencies: {column_with_calc.calculated_column.dependencies}")
            
            # Step 9: Query all columns in the table to show the mix
            print("\n📋 Step 9: All columns in the table...")
            all_columns = await db.execute(
                select(SQLColumn)
                .where(SQLColumn.table_id == table.table_id)
                .order_by(SQLColumn.ordinal_position)
            )
            columns = all_columns.scalars().all()
            
            print(f"📊 Table '{table.name}' has {len(columns)} columns:")
            for col in columns:
                print(f"   - {col.name} ({col.column_type}) - {col.data_type}")
                if col.column_type == 'calculated_column':
                    print(f"     └─ Calculation: {col.calculated_column.calculation_sql}")
            
            print("\n✅ Test completed successfully!")
            print("\n🎯 Key Points:")
            print("   - Calculated columns are SQLColumns with column_type='calculated_column'")
            print("   - They have all standard column properties (name, data_type, etc.)")
            print("   - The calculation logic is stored in the associated CalculatedColumn")
            print("   - This allows calculated columns to be treated like regular columns")
            print("   - They can be queried, filtered, and used in relationships")
            
        except Exception as e:
            print(f"❌ Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            print("\n🧹 Cleaning up test data...")
            try:
                # Delete in reverse order due to foreign key constraints
                await db.execute(select(CalculatedColumn).where(CalculatedColumn.column_id == calculated_column.column_id))
                calc_columns = await db.execute(select(CalculatedColumn).where(CalculatedColumn.column_id == calculated_column.column_id))
                for calc_col in calc_columns.scalars().all():
                    await db.delete(calc_col)
                
                await db.execute(select(SQLColumn).where(SQLColumn.table_id == table.table_id))
                columns = await db.execute(select(SQLColumn).where(SQLColumn.table_id == table.table_id))
                for col in columns.scalars().all():
                    await db.delete(col)
                
                await db.delete(table)
                await db.delete(dataset)
                await db.delete(project)
                await db.commit()
                print("✅ Cleanup completed")
            except Exception as e:
                print(f"⚠️ Cleanup error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_calculated_column_creation()) 