#!/usr/bin/env python3
"""
Data Analysis Utility for Feature Recommendation Agent
Pre-calculates all data analysis and stores as JSON to avoid numpy serialization issues
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import uuid


@dataclass
class DataAnalysisResult:
    """Complete data analysis result stored as JSON-serializable data"""
    
    # Basic info
    shape_rows: int
    shape_cols: int
    total_rows: int
    total_columns: int
    
    # Column analysis
    column_types: Dict[str, str]
    column_descriptions: Dict[str, str]
    missing_values_pct: Dict[str, float]
    unique_values_count: Dict[str, int]
    
    # Numerical analysis
    numerical_columns: List[str]
    numerical_distributions: Dict[str, Dict[str, float]]
    numerical_correlations: Dict[str, Dict[str, float]]
    
    # Categorical analysis
    categorical_columns: List[str]
    categorical_cardinality: Dict[str, int]
    categorical_value_counts: Dict[str, Dict[str, int]]
    
    # Datetime analysis
    datetime_columns: List[str]
    datetime_ranges: Dict[str, Dict[str, str]]
    
    # Quality metrics
    data_quality_score: float
    completeness_score: float
    consistency_score: float
    
    # Business relevance
    business_relevance_score: Dict[str, float]
    business_keywords_found: Dict[str, List[str]]
    
    # Insights
    correlation_insights: List[str]
    data_quality_insights: List[str]
    business_insights: List[str]
    
    # Metadata
    analysis_timestamp: str
    analysis_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataAnalysisResult':
        """Create from dictionary"""
        return cls(**data)


class DataAnalysisUtility:
    """Utility for comprehensive data analysis and JSON storage"""
    
    def __init__(self):
        self.business_keywords = {
            'customer': ['customer', 'client', 'user', 'member'],
            'revenue': ['revenue', 'sales', 'income', 'earnings', 'profit'],
            'cost': ['cost', 'expense', 'spend', 'budget'],
            'risk': ['risk', 'probability', 'chance', 'likelihood'],
            'value': ['value', 'worth', 'price', 'amount'],
            'performance': ['performance', 'efficiency', 'productivity'],
            'engagement': ['engagement', 'interaction', 'activity', 'usage'],
            'quality': ['quality', 'satisfaction', 'rating', 'score']
        }
    
    def analyze_dataframe(self, df: pd.DataFrame, dataset_name: str = "dataset") -> DataAnalysisResult:
        """
        Comprehensive data analysis that returns JSON-serializable results
        
        Args:
            df: DataFrame to analyze
            dataset_name: Name for the dataset
            
        Returns:
            DataAnalysisResult with all analysis stored as JSON-serializable data
        """
        
        print(f"🔍 Analyzing dataset: {dataset_name} ({df.shape[0]} rows, {df.shape[1]} columns)")
        
        # Basic info
        shape_rows, shape_cols = df.shape
        total_rows = len(df)
        total_columns = len(df.columns)
        
        # Column analysis
        column_types = {}
        column_descriptions = {}
        missing_values_pct = {}
        unique_values_count = {}
        
        numerical_columns = []
        categorical_columns = []
        datetime_columns = []
        
        for col in df.columns:
            # Missing values
            missing_pct = (df[col].isnull().sum() / len(df)) * 100
            missing_values_pct[col] = float(missing_pct)
            
            # Unique values
            unique_count = df[col].nunique()
            unique_values_count[col] = int(unique_count)
            
            # Column type and description
            if pd.api.types.is_numeric_dtype(df[col]):
                column_types[col] = "numerical"
                numerical_columns.append(col)
                column_descriptions[col] = f"Numerical column with {unique_count} unique values"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                column_types[col] = "datetime"
                datetime_columns.append(col)
                column_descriptions[col] = f"Datetime column with {unique_count} unique values"
            else:
                column_types[col] = "categorical"
                categorical_columns.append(col)
                column_descriptions[col] = f"Categorical column with {unique_count} unique values"
        
        # Numerical analysis
        numerical_distributions = {}
        numerical_correlations = {}
        
        if numerical_columns:
            # Statistical distributions
            for col in numerical_columns:
                series = df[col].dropna()
                if len(series) > 0:
                    numerical_distributions[col] = {
                        "mean": float(series.mean()),
                        "std": float(series.std()),
                        "min": float(series.min()),
                        "max": float(series.max()),
                        "median": float(series.median()),
                        "skewness": float(series.skew()),
                        "kurtosis": float(series.kurtosis()),
                        "q25": float(series.quantile(0.25)),
                        "q75": float(series.quantile(0.75)),
                        "missing_count": int(df[col].isnull().sum()),
                        "missing_pct": float((df[col].isnull().sum() / len(df)) * 100)
                    }
            
            # Correlation matrix
            if len(numerical_columns) > 1:
                corr_matrix = df[numerical_columns].corr()
                for i, col1 in enumerate(numerical_columns):
                    numerical_correlations[col1] = {}
                    for j, col2 in enumerate(numerical_columns):
                        if i != j:
                            corr_value = float(corr_matrix.iloc[i, j])
                            numerical_correlations[col1][col2] = corr_value
        
        # Categorical analysis
        categorical_cardinality = {}
        categorical_value_counts = {}
        
        for col in categorical_columns:
            categorical_cardinality[col] = int(df[col].nunique())
            
            # Top 10 value counts
            value_counts = df[col].value_counts().head(10)
            categorical_value_counts[col] = {
                str(k): int(v) for k, v in value_counts.items()
            }
        
        # Datetime analysis
        datetime_ranges = {}
        
        for col in datetime_columns:
            series = df[col].dropna()
            if len(series) > 0:
                datetime_ranges[col] = {
                    "min_date": str(series.min()),
                    "max_date": str(series.max()),
                    "date_range_days": int((series.max() - series.min()).days),
                    "missing_count": int(df[col].isnull().sum())
                }
        
        # Quality metrics
        completeness_score = 1.0 - (sum(missing_values_pct.values()) / len(missing_values_pct) / 100)
        consistency_score = self._calculate_consistency_score(df, column_types)
        data_quality_score = (completeness_score + consistency_score) / 2
        
        # Business relevance
        business_relevance_score = {}
        business_keywords_found = {}
        
        for col in df.columns:
            score = 0.5  # Base score
            found_keywords = []
            
            for category, keywords in self.business_keywords.items():
                for keyword in keywords:
                    if keyword in col.lower():
                        score += 0.1
                        found_keywords.append(keyword)
            
            business_relevance_score[col] = min(score, 1.0)
            business_keywords_found[col] = found_keywords
        
        # Generate insights
        correlation_insights = self._generate_correlation_insights(numerical_correlations)
        data_quality_insights = self._generate_quality_insights(df, missing_values_pct, column_types)
        business_insights = self._generate_business_insights(df, business_relevance_score, business_keywords_found)
        
        # Create result
        result = DataAnalysisResult(
            shape_rows=shape_rows,
            shape_cols=shape_cols,
            total_rows=total_rows,
            total_columns=total_columns,
            column_types=column_types,
            column_descriptions=column_descriptions,
            missing_values_pct=missing_values_pct,
            unique_values_count=unique_values_count,
            numerical_columns=numerical_columns,
            numerical_distributions=numerical_distributions,
            numerical_correlations=numerical_correlations,
            categorical_columns=categorical_columns,
            categorical_cardinality=categorical_cardinality,
            categorical_value_counts=categorical_value_counts,
            datetime_columns=datetime_columns,
            datetime_ranges=datetime_ranges,
            data_quality_score=data_quality_score,
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            business_relevance_score=business_relevance_score,
            business_keywords_found=business_keywords_found,
            correlation_insights=correlation_insights,
            data_quality_insights=data_quality_insights,
            business_insights=business_insights,
            analysis_timestamp=pd.Timestamp.now().isoformat()
        )
        
        print(f"✅ Analysis complete: Quality score = {data_quality_score:.2f}")
        return result
    
    def _calculate_consistency_score(self, df: pd.DataFrame, column_types: Dict[str, str]) -> float:
        """Calculate data consistency score"""
        consistency_checks = 0
        total_checks = 0
        
        for col, col_type in column_types.items():
            if col_type == "numerical":
                # Check for reasonable numerical values
                series = df[col].dropna()
                if len(series) > 0:
                    total_checks += 1
                    # Check if values are within reasonable bounds (not all zeros, not all same)
                    if series.std() > 0 and series.nunique() > 1:
                        consistency_checks += 1
            
            elif col_type == "categorical":
                # Check for reasonable categorical values
                total_checks += 1
                if df[col].nunique() > 1 and df[col].nunique() < len(df) * 0.9:
                    consistency_checks += 1
        
        return consistency_checks / total_checks if total_checks > 0 else 1.0
    
    def _generate_correlation_insights(self, correlations: Dict[str, Dict[str, float]]) -> List[str]:
        """Generate correlation insights"""
        insights = []
        
        for col1, corr_dict in correlations.items():
            for col2, corr_value in corr_dict.items():
                if abs(corr_value) > 0.7:
                    strength = "strongly" if abs(corr_value) > 0.8 else "moderately"
                    direction = "positive" if corr_value > 0 else "negative"
                    insights.append(
                        f"{col1} and {col2} are {strength} {direction}ly correlated ({corr_value:.2f})"
                    )
        
        return insights
    
    def _generate_quality_insights(self, df: pd.DataFrame, missing_pct: Dict[str, float], column_types: Dict[str, str]) -> List[str]:
        """Generate data quality insights"""
        insights = []
        
        # Missing data insights
        high_missing = [col for col, pct in missing_pct.items() if pct > 20]
        if high_missing:
            insights.append(f"High missing data in columns: {', '.join(high_missing[:3])}")
        
        # Column type insights
        num_numerical = len([col for col, type_ in column_types.items() if type_ == "numerical"])
        num_categorical = len([col for col, type_ in column_types.items() if type_ == "categorical"])
        
        insights.append(f"Dataset has {num_numerical} numerical and {num_categorical} categorical columns")
        
        return insights
    
    def _generate_business_insights(self, df: pd.DataFrame, relevance_scores: Dict[str, float], keywords_found: Dict[str, List[str]]) -> List[str]:
        """Generate business relevance insights"""
        insights = []
        
        # High relevance columns
        high_relevance = [col for col, score in relevance_scores.items() if score > 0.7]
        if high_relevance:
            insights.append(f"High business relevance columns: {', '.join(high_relevance[:3])}")
        
        # Keyword insights
        keyword_counts = {}
        for col, keywords in keywords_found.items():
            for keyword in keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        if keyword_counts:
            top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            insights.append(f"Most common business keywords: {', '.join([k for k, v in top_keywords])}")
        
        return insights
    
    def save_analysis(self, analysis: DataAnalysisResult, filepath: str) -> str:
        """Save analysis result to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(analysis.to_dict(), f, indent=2)
        return filepath
    
    def load_analysis(self, filepath: str) -> DataAnalysisResult:
        """Load analysis result from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return DataAnalysisResult.from_dict(data)


# Enhanced DataFrameStorage with analysis capabilities
class EnhancedDataFrameStorage:
    """Enhanced DataFrame storage with integrated data analysis"""
    
    def __init__(self):
        self._storage: Dict[str, pd.DataFrame] = {}
        self._analysis_storage: Dict[str, DataAnalysisResult] = {}
        self.analysis_utility = DataAnalysisUtility()
    
    def store_dataframe_with_analysis(self, df: pd.DataFrame, key: str = None, dataset_name: str = "dataset") -> str:
        """Store DataFrame and pre-calculate analysis"""
        if key is None:
            key = str(uuid.uuid4())
        
        # Store DataFrame
        self._storage[key] = df
        
        # Pre-calculate analysis
        analysis = self.analysis_utility.analyze_dataframe(df, dataset_name)
        self._analysis_storage[key] = analysis
        
        return key
    
    def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Get DataFrame by key"""
        return self._storage.get(key)
    
    def get_analysis(self, key: str) -> Optional[DataAnalysisResult]:
        """Get pre-calculated analysis by key"""
        return self._analysis_storage.get(key)
    
    def get_analysis_dict(self, key: str) -> Optional[Dict[str, Any]]:
        """Get analysis as dictionary for easy use"""
        analysis = self._analysis_storage.get(key)
        return analysis.to_dict() if analysis else None
    
    def remove_dataframe(self, key: str) -> bool:
        """Remove DataFrame and analysis"""
        if key in self._storage:
            del self._storage[key]
            if key in self._analysis_storage:
                del self._analysis_storage[key]
            return True
        return False
    
    def clear_all(self):
        """Clear all stored data"""
        self._storage.clear()
        self._analysis_storage.clear()


# Global enhanced storage instance
enhanced_dataframe_storage = EnhancedDataFrameStorage() 