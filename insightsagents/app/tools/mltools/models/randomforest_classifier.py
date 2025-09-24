import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    classification_report, confusion_matrix, roc_auc_score
)
import joblib
import warnings
from datetime import datetime
from ..base_pipe import BasePipe


class RFPipe(BasePipe):
    """
    A pipeline-style Random Forest classifier tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for Random Forest classification analysis"""
        self.features = None
        self.labels = None
        self.feature_columns = []
        self.target_column = None
        self.models = {}
        self.predictions = {}
        self.metrics = {}
        self.scalers = {}
        self.encoders = {}
        self.feature_selectors = {}
        self.current_analysis = None
        self.train_test_splits = {}
        self.new_predictions = {}
        self.auxiliary_features = {}
        self.derived_features = {}
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'features'):
            self.features = source_pipe.features.copy() if source_pipe.features is not None else None
        if hasattr(source_pipe, 'labels'):
            self.labels = source_pipe.labels.copy() if source_pipe.labels is not None else None
        if hasattr(source_pipe, 'feature_columns'):
            self.feature_columns = source_pipe.feature_columns.copy()
        if hasattr(source_pipe, 'target_column'):
            self.target_column = source_pipe.target_column
        if hasattr(source_pipe, 'models'):
            self.models = source_pipe.models.copy()
        if hasattr(source_pipe, 'predictions'):
            self.predictions = source_pipe.predictions.copy()
        if hasattr(source_pipe, 'metrics'):
            self.metrics = source_pipe.metrics.copy()
        if hasattr(source_pipe, 'scalers'):
            self.scalers = source_pipe.scalers.copy()
        if hasattr(source_pipe, 'encoders'):
            self.encoders = source_pipe.encoders.copy()
        if hasattr(source_pipe, 'feature_selectors'):
            self.feature_selectors = source_pipe.feature_selectors.copy()
        if hasattr(source_pipe, 'current_analysis'):
            self.current_analysis = source_pipe.current_analysis
        if hasattr(source_pipe, 'train_test_splits'):
            self.train_test_splits = source_pipe.train_test_splits.copy()
        if hasattr(source_pipe, 'new_predictions'):
            self.new_predictions = source_pipe.new_predictions.copy()
        if hasattr(source_pipe, 'auxiliary_features'):
            self.auxiliary_features = source_pipe.auxiliary_features.copy()
        if hasattr(source_pipe, 'derived_features'):
            self.derived_features = source_pipe.derived_features.copy()
        if hasattr(source_pipe, 'pending_categorical_features'):
            self.pending_categorical_features = source_pipe.pending_categorical_features.copy()
    
    def _has_results(self) -> bool:
        """Check if the pipeline has any results to merge"""
        return (len(self.models) > 0 or 
                len(self.predictions) > 0 or 
                len(self.metrics) > 0 or 
                len(self.new_predictions) > 0)
    
    def merge_to_df(self, base_df: pd.DataFrame, analysis_name: Optional[str] = None, include_metadata: bool = False, **kwargs) -> pd.DataFrame:
        """
        Merge Random Forest classification results into the base dataframe as new columns
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        analysis_name : str, optional
            Specific analysis to merge (if None, merges all)
        include_metadata : bool, default=False
            Whether to include metadata columns
        **kwargs : dict
            Additional arguments
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with Random Forest classification results merged as new columns
        """
        if not self._has_results():
            return base_df
        
        result_df = base_df.copy()
        
        # Merge predictions
        for pred_name, pred_data in self.predictions.items():
            if analysis_name is None or pred_name == analysis_name:
                if hasattr(pred_data, 'values') and len(pred_data) == len(result_df):
                    result_df[f"prediction_{pred_name}"] = pred_data.values
                elif include_metadata:
                    result_df[f"prediction_{pred_name}"] = pred_data
        
        # Merge new predictions
        for new_pred_name, new_pred_data in self.new_predictions.items():
            if analysis_name is None or new_pred_name == analysis_name:
                if hasattr(new_pred_data, 'values') and len(new_pred_data) == len(result_df):
                    result_df[f"new_prediction_{new_pred_name}"] = new_pred_data.values
                elif include_metadata:
                    result_df[f"new_prediction_{new_pred_name}"] = new_pred_data
        
        # Merge metrics
        for metric_name, metric_data in self.metrics.items():
            if analysis_name is None or metric_name == analysis_name:
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        if include_metadata:
                            result_df[f"metric_{metric_name}_{key}"] = value
        
        return result_df
    
    def to_df(self, **kwargs) -> pd.DataFrame:
        """
        Convert the Random Forest classification analysis results to a DataFrame.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in Random Forest classification pipe)
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the analysis results
            
        Raises:
        -------
        ValueError
            If no analysis has been performed
        """
        if not any([self.models, self.predictions, self.metrics]):
            raise ValueError("No Random Forest classification analysis has been performed")
        
        # Create a comprehensive results DataFrame
        results_data = []
        
        # Add model information
        for model_name, model_info in self.models.items():
            results_data.append({
                'analysis_type': 'model',
                'name': model_name,
                'type': 'RandomForestClassifier',
                'n_estimators': model_info.get('n_estimators', 'unknown'),
                'max_depth': model_info.get('max_depth', 'unknown'),
                'min_samples_split': model_info.get('min_samples_split', 'unknown'),
                'min_samples_leaf': model_info.get('min_samples_leaf', 'unknown'),
                'random_state': model_info.get('random_state', 'unknown')
            })
        
        # Add prediction information
        for pred_name, pred_info in self.predictions.items():
            results_data.append({
                'analysis_type': 'prediction',
                'name': pred_name,
                'model_used': pred_info.get('model_used', 'unknown'),
                'data_split': pred_info.get('data_split', 'unknown'),
                'n_predictions': len(pred_info.get('predictions', [])),
                'prediction_type': 'classification'
            })
        
        # Add metrics information
        for metric_name, metric_info in self.metrics.items():
            results_data.append({
                'analysis_type': 'metrics',
                'name': metric_name,
                'accuracy': metric_info.get('accuracy', 'unknown'),
                'precision': metric_info.get('precision', 'unknown'),
                'recall': metric_info.get('recall', 'unknown'),
                'f1_score': metric_info.get('f1_score', 'unknown'),
                'roc_auc': metric_info.get('roc_auc', 'unknown')
            })
        
        # Add feature information
        if self.feature_columns:
            results_data.append({
                'analysis_type': 'features',
                'name': 'feature_columns',
                'n_features': len(self.feature_columns),
                'feature_list': ', '.join(self.feature_columns[:10]) + ('...' if len(self.feature_columns) > 10 else '')
            })
        
        # Add target information
        if self.target_column:
            results_data.append({
                'analysis_type': 'target',
                'name': 'target_column',
                'target_column': self.target_column,
                'n_classes': len(self.labels.unique()) if self.labels is not None else 'unknown'
            })
        
        return pd.DataFrame(results_data)
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the Random Forest classification analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in Random Forest classification pipe)
            
        Returns:
        --------
        dict
            Summary of the Random Forest classification analysis results
        """
        if not any([self.models, self.predictions, self.metrics]):
            return {"error": "No Random Forest classification analysis has been performed"}
        
        # Count analyses by type
        analysis_types = {
            'models': len(self.models),
            'predictions': len(self.predictions),
            'metrics': len(self.metrics),
            'scalers': len(self.scalers),
            'encoders': len(self.encoders),
            'feature_selectors': len(self.feature_selectors),
            'train_test_splits': len(self.train_test_splits)
        }
        
        # Get model information
        models_info = {}
        for name, model in self.models.items():
            models_info[name] = {
                "type": "RandomForestClassifier",
                "n_estimators": model.get('n_estimators', 'unknown'),
                "max_depth": model.get('max_depth', 'unknown'),
                "min_samples_split": model.get('min_samples_split', 'unknown'),
                "min_samples_leaf": model.get('min_samples_leaf', 'unknown')
            }
        
        # Get metrics summary
        metrics_summary = {}
        for name, metric_data in self.metrics.items():
            if isinstance(metric_data, dict):
                metrics_summary[name] = {
                    "accuracy": metric_data.get('accuracy', None),
                    "precision": metric_data.get('precision', None),
                    "recall": metric_data.get('recall', None),
                    "f1_score": metric_data.get('f1_score', None),
                    "auc_roc": metric_data.get('auc_roc', None)
                }
        
        # Get prediction information
        predictions_info = {}
        for name, pred_data in self.predictions.items():
            predictions_info[name] = {
                "n_predictions": len(pred_data.get('y_pred', [])),
                "data_split": pred_data.get('data_split', 'unknown'),
                "model_name": pred_data.get('model_name', 'unknown')
            }
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "feature_columns": self.feature_columns,
            "target_column": self.target_column,
            "analysis_types": analysis_types,
            "current_analysis": self.current_analysis,
            "available_models": list(self.models.keys()),
            "available_predictions": list(self.predictions.keys()),
            "available_metrics": list(self.metrics.keys()),
            "available_scalers": list(self.scalers.keys()),
            "available_encoders": list(self.encoders.keys()),
            "available_feature_selectors": list(self.feature_selectors.keys()),
            "available_train_test_splits": list(self.train_test_splits.keys()),
            "models_info": models_info,
            "metrics_summary": metrics_summary,
            "predictions_info": predictions_info,
            "scalers_info": {name: {"type": type(scaler).__name__} 
                           for name, scaler in self.scalers.items()},
            "encoders_info": {name: {"type": type(encoder).__name__} 
                            for name, encoder in self.encoders.items()},
            "feature_selectors_info": {name: {"type": type(selector).__name__} 
                                     for name, selector in self.feature_selectors.items()},
            "train_test_splits_info": {name: {"test_size": split.get('test_size', 'unknown')} 
                                     for name, split in self.train_test_splits.items()}
        }


# Feature Engineering Functions
def generate_numerical_features(
    columns: List[str],
    operations: List[str] = ['log', 'sqrt', 'square', 'reciprocal'],
    prefix: str = 'num_feat_',
    handle_zeros: bool = True
):
    """
    Generate numerical features from existing columns
    
    Parameters:
    -----------
    columns : List[str]
        Columns to generate features from
    operations : List[str]
        Mathematical operations to apply ('log', 'sqrt', 'square', 'reciprocal')
    prefix : str
        Prefix for new feature names
    handle_zeros : bool
        Whether to handle zeros in log and reciprocal operations
        
    Returns:
    --------
    Callable
        Function that generates numerical features from an RFPipe
    """
    def _generate_numerical_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        for col in columns:
            if col not in df.columns:
                warnings.warn(f"Column '{col}' not found in data. Skipping.")
                continue
                
            if not pd.api.types.is_numeric_dtype(df[col]):
                warnings.warn(f"Column '{col}' is not numeric. Skipping.")
                continue
            
            for op in operations:
                new_col_name = f"{prefix}{op}_{col}"
                
                if op == 'log':
                    if handle_zeros:
                        df[new_col_name] = np.log1p(np.maximum(df[col], 0))
                    else:
                        df[new_col_name] = np.log(df[col])
                elif op == 'sqrt':
                    df[new_col_name] = np.sqrt(np.maximum(df[col], 0))
                elif op == 'square':
                    df[new_col_name] = df[col] ** 2
                elif op == 'reciprocal':
                    if handle_zeros:
                        df[new_col_name] = 1 / (df[col] + 1e-8)
                    else:
                        df[new_col_name] = 1 / df[col]
                
                new_pipe.feature_columns.append(new_col_name)
        
        # Update the dataframe in the pipe after all modifications
        new_pipe.data = df
        
        new_pipe.current_analysis = 'numerical_features'
        return new_pipe
    
    return _generate_numerical_features


def generate_categorical_features(
    columns: List[str],
    encoding_type: str = 'onehot',
    max_categories: int = 10,
    handle_unknown: str = 'ignore'
):
    """
    Generate categorical features using encoding
    
    Parameters:
    -----------
    columns : List[str]
        Categorical columns to encode
    encoding_type : str
        Type of encoding ('onehot', 'label', 'target')
    max_categories : int
        Maximum number of categories for one-hot encoding
    handle_unknown : str
        How to handle unknown categories
        
    Returns:
    --------
    Callable
        Function that generates categorical features from an RFPipe
    """
    def _generate_categorical_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        for col in columns:
            if col not in df.columns:
                warnings.warn(f"Column '{col}' not found in data. Skipping.")
                continue
            
            n_unique = df[col].nunique()
            
            if encoding_type == 'onehot' and n_unique <= max_categories:
                # One-hot encoding
                encoded_df = pd.get_dummies(df[col], prefix=col, dummy_na=True)
                df = pd.concat([df, encoded_df], axis=1)
                # Only add columns that actually exist in the dataframe
                for encoded_col in encoded_df.columns:
                    if encoded_col in df.columns:
                        new_pipe.feature_columns.append(encoded_col)
                
                # Update the dataframe in the pipe
                new_pipe.data = df
                
            elif encoding_type == 'label':
                # Label encoding
                le = LabelEncoder()
                new_col_name = f"{col}_encoded"
                df[new_col_name] = le.fit_transform(df[col].astype(str))
                new_pipe.encoders[col] = le
                new_pipe.feature_columns.append(new_col_name)
            
            elif encoding_type == 'target' and new_pipe.target_column:
                # Target encoding (mean of target for each category)
                target_means = df.groupby(col)[new_pipe.target_column].mean()
                new_col_name = f"{col}_target_encoded"
                df[new_col_name] = df[col].map(target_means)
                new_pipe.feature_columns.append(new_col_name)
        
        # Update the dataframe in the pipe after all modifications
        new_pipe.data = df
        
        new_pipe.current_analysis = 'categorical_features'
        
        # Debug: Print feature columns to verify they exist in dataframe
        missing_columns = [col for col in new_pipe.feature_columns if col not in new_pipe.data.columns]
        if missing_columns:
            warnings.warn(f"Feature columns not found in dataframe: {missing_columns}")
            # Remove missing columns from feature_columns
            new_pipe.feature_columns = [col for col in new_pipe.feature_columns if col in new_pipe.data.columns]
        
        return new_pipe
    
    return _generate_categorical_features


def generate_interaction_features(
    column_pairs: List[Tuple[str, str]],
    operations: List[str] = ['multiply', 'add', 'subtract', 'divide'],
    prefix: str = 'interaction_'
):
    """
    Generate interaction features between column pairs
    
    Parameters:
    -----------
    column_pairs : List[Tuple[str, str]]
        Pairs of columns to create interactions for
    operations : List[str]
        Operations to apply ('multiply', 'add', 'subtract', 'divide')
    prefix : str
        Prefix for new feature names
        
    Returns:
    --------
    Callable
        Function that generates interaction features from an RFPipe
    """
    def _generate_interaction_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        for col1, col2 in column_pairs:
            if col1 not in df.columns or col2 not in df.columns:
                warnings.warn(f"Columns '{col1}' or '{col2}' not found in data. Skipping.")
                continue
            
            if not (pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2])):
                warnings.warn(f"Columns '{col1}' or '{col2}' are not numeric. Skipping.")
                continue
            
            for op in operations:
                new_col_name = f"{prefix}{op}_{col1}_{col2}"
                
                if op == 'multiply':
                    df[new_col_name] = df[col1] * df[col2]
                elif op == 'add':
                    df[new_col_name] = df[col1] + df[col2]
                elif op == 'subtract':
                    df[new_col_name] = df[col1] - df[col2]
                elif op == 'divide':
                    df[new_col_name] = df[col1] / (df[col2] + 1e-8)  # Avoid division by zero
                
                new_pipe.feature_columns.append(new_col_name)
        
        # Update the dataframe in the pipe after all modifications
        new_pipe.data = df
        
        new_pipe.current_analysis = 'interaction_features'
        return new_pipe
    
    return _generate_interaction_features


# Labeling Functions
def create_binary_labels(
    column: str,
    condition: Union[str, Callable],
    label_column: str = 'target',
    positive_label: str = '1',
    negative_label: str = '0'
):
    """
    Create binary labels based on a condition
    
    Parameters:
    -----------
    column : str
        Column to base labels on
    condition : Union[str, Callable]
        Condition for positive label (e.g., '>100' or lambda x: x > 100)
    label_column : str
        Name of the target column to create
    positive_label : str
        Label for positive cases
    negative_label : str
        Label for negative cases
        
    Returns:
    --------
    Callable
        Function that creates binary labels from an RFPipe
    """
    def _create_binary_labels(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in data.")
        
        if isinstance(condition, str):
            # Parse string condition - check longer patterns first
            if condition.startswith('>='):
                threshold = float(condition[2:])
                mask = df[column] >= threshold
            elif condition.startswith('<='):
                threshold = float(condition[2:])
                mask = df[column] <= threshold
            elif condition.startswith('=='):
                value = condition[2:]
                # Try to convert to float, but keep as string if it fails
                try:
                    # Check if the column is numeric
                    if pd.api.types.is_numeric_dtype(df[column]):
                        value = float(value)
                    else:
                        # For non-numeric columns, keep as string
                        pass
                except ValueError:
                    # Keep as string if conversion fails
                    pass
                mask = df[column] == value
            elif condition.startswith('>'):
                threshold = float(condition[1:])
                mask = df[column] > threshold
            elif condition.startswith('<'):
                threshold = float(condition[1:])
                mask = df[column] < threshold
            else:
                raise ValueError(f"Invalid condition format: {condition}")
        
        elif callable(condition):
            mask = condition(df[column])
        else:
            raise ValueError("Condition must be a string or callable")
        
        df[label_column] = negative_label
        df.loc[mask, label_column] = positive_label
        
        # Update the dataframe in the pipe
        new_pipe.data = df
        new_pipe.target_column = label_column
        new_pipe.current_analysis = 'binary_labels'
        
        return new_pipe
    
    return _create_binary_labels


def create_multiclass_labels(
    column: str,
    bins: Union[int, List[float]],
    labels: Optional[List[str]] = None,
    label_column: str = 'target'
):
    """
    Create multiclass labels by binning a continuous variable
    
    Parameters:
    -----------
    column : str
        Column to create labels from
    bins : Union[int, List[float]]
        Number of bins or bin edges
    labels : Optional[List[str]]
        Labels for each bin
    label_column : str
        Name of the target column to create
        
    Returns:
    --------
    Callable
        Function that creates multiclass labels from an RFPipe
    """
    def _create_multiclass_labels(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in data.")
        
        df[label_column] = pd.cut(df[column], bins=bins, labels=labels)
        
        # Update the dataframe in the pipe
        new_pipe.data = df
        new_pipe.target_column = label_column
        new_pipe.current_analysis = 'multiclass_labels'
        
        return new_pipe
    
    return _create_multiclass_labels


# Feature Selection Functions
def select_features(
    method: str = 'kbest',
    k: int = 10,
    score_func=f_classif
):
    """
    Select top k features using statistical tests
    
    Parameters:
    -----------
    method : str
        Feature selection method ('kbest', 'mutual_info')
    k : int
        Number of features to select
    score_func : callable
        Scoring function for feature selection
        
    Returns:
    --------
    Callable
        Function that selects features from an RFPipe
    """
    def _select_features(pipe):
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available for feature selection.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate that all feature columns exist in the dataframe
        missing_columns = [col for col in new_pipe.feature_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Feature columns not found in dataframe: {missing_columns}")
        
        # Filter out non-numerical features for feature selection
        numerical_features = []
        non_numerical_features = []
        
        for col in new_pipe.feature_columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numerical_features.append(col)
            else:
                non_numerical_features.append(col)
        
        if non_numerical_features:
            print(f"Warning: Skipping non-numerical features for feature selection: {non_numerical_features}")
        
        if not numerical_features:
            raise ValueError("No numerical features available for feature selection.")
        
        X = df[numerical_features]
        y = df[new_pipe.target_column]
        
        if method == 'kbest':
            selector = SelectKBest(score_func=score_func, k=k)
        elif method == 'mutual_info':
            selector = SelectKBest(score_func=mutual_info_classif, k=k)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        X_selected = selector.fit_transform(X, y)
        selected_features = [numerical_features[i] for i in selector.get_support(indices=True)]
        
        new_pipe.feature_columns = selected_features
        new_pipe.feature_selectors[method] = selector
        new_pipe.current_analysis = 'feature_selection'
        
        return new_pipe
    
    return _select_features


# Training Functions
def train_random_forest(
    test_size: float = 0.2,
    random_state: int = 42,
    n_estimators: int = 100,
    max_depth: Optional[int] = None,
    min_samples_split: int = 2,
    min_samples_leaf: int = 1,
    model_name: str = 'rf_model'
):
    """
    Train a Random Forest classifier
    
    Parameters:
    -----------
    test_size : float
        Proportion of data for testing
    random_state : int
        Random seed for reproducibility
    n_estimators : int
        Number of trees in the forest
    max_depth : Optional[int]
        Maximum depth of trees
    min_samples_split : int
        Minimum samples required to split a node
    min_samples_leaf : int
        Minimum samples required at a leaf node
    model_name : str
        Name to store the model under
        
    Returns:
    --------
    Callable
        Function that trains a Random Forest from an RFPipe
    """
    def _train_random_forest(pipe):
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available for training.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate that all feature columns exist in the dataframe
        missing_columns = [col for col in new_pipe.feature_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Feature columns not found in dataframe: {missing_columns}")
        
        X = df[new_pipe.feature_columns]
        y = df[new_pipe.target_column]
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # Create and train the model
        rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state
        )
        
        rf.fit(X_train, y_train)
        
        # Store model and data splits
        new_pipe.models[model_name] = rf
        new_pipe.train_test_splits[model_name] = {
            'X_train': X_train,
            'X_test': X_test,
            'y_train': y_train,
            'y_test': y_test
        }
        
        new_pipe.current_analysis = f'train_{model_name}'
        
        return new_pipe
    
    return _train_random_forest


def save_model(
    model_name: str = 'rf_model',
    filepath: Optional[str] = None
):
    """
    Save a trained model to disk
    
    Parameters:
    -----------
    model_name : str
        Name of the model to save
    filepath : Optional[str]
        Path to save the model (if None, uses model_name with timestamp)
        
    Returns:
    --------
    Callable
        Function that saves a model from an RFPipe
    """
    def _save_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found in pipeline.")
        
        new_pipe = pipe.copy()
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f"{model_name}_{timestamp}.joblib"
        else:
            save_path = filepath
        
        joblib.dump(pipe.models[model_name], save_path)
        print(f"Model saved to: {save_path}")
        
        return new_pipe
    
    return _save_model


# Inference Functions
def predict(
    model_name: str = 'rf_model',
    data_split: str = 'test',
    prediction_name: Optional[str] = None
):
    """
    Make predictions using a trained model
    
    Parameters:
    -----------
    model_name : str
        Name of the model to use for prediction
    data_split : str
        Which data split to predict on ('train', 'test', 'all')
    prediction_name : Optional[str]
        Name to store predictions under
        
    Returns:
    --------
    Callable
        Function that makes predictions from an RFPipe
    """
    def _predict(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found in pipeline.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        if prediction_name is None:
            pred_name = f"{model_name}_{data_split}_predictions"
        else:
            pred_name = prediction_name
        
        if data_split == 'test':
            X = new_pipe.train_test_splits[model_name]['X_test']
            y_true = new_pipe.train_test_splits[model_name]['y_test']
        elif data_split == 'train':
            X = new_pipe.train_test_splits[model_name]['X_train']
            y_true = new_pipe.train_test_splits[model_name]['y_train']
        elif data_split == 'all':
            # Validate that all feature columns exist in the dataframe
            missing_columns = [col for col in new_pipe.feature_columns if col not in new_pipe.data.columns]
            if missing_columns:
                raise ValueError(f"Feature columns not found in dataframe: {missing_columns}")
            X = new_pipe.data[new_pipe.feature_columns]
            y_true = new_pipe.data[new_pipe.target_column]
        else:
            raise ValueError("data_split must be 'train', 'test', or 'all'")
        
        y_pred = model.predict(X)
        y_pred_proba = model.predict_proba(X)
        
        new_pipe.predictions[pred_name] = {
            'y_true': y_true,
            'y_pred': y_pred,
            'y_pred_proba': y_pred_proba,
            'feature_importance': model.feature_importances_,
            'feature_names': new_pipe.feature_columns
        }
        
        new_pipe.current_analysis = f'predict_{pred_name}'
        
        return new_pipe
    
    return _predict


# Evaluation Functions
def calculate_metrics(
    prediction_name: Optional[str] = None,
    model_name: str = 'rf_model',
    average: str = 'weighted'
):
    """
    Calculate classification metrics
    
    Parameters:
    -----------
    prediction_name : Optional[str]
        Name of predictions to evaluate
    model_name : str
        Model name to use if prediction_name not specified
    average : str
        Averaging method for multiclass metrics
        
    Returns:
    --------
    Callable
        Function that calculates metrics from an RFPipe
    """
    def _calculate_metrics(pipe):
        if prediction_name is None:
            pred_name = f"{model_name}_test_predictions"
        else:
            pred_name = prediction_name
        
        if pred_name not in pipe.predictions:
            raise ValueError(f"Predictions '{pred_name}' not found in pipeline.")
        
        new_pipe = pipe.copy()
        
        pred_data = new_pipe.predictions[pred_name]
        y_true = pred_data['y_true']
        y_pred = pred_data['y_pred']
        y_pred_proba = pred_data['y_pred_proba']
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average=average, zero_division=0),
            'recall': recall_score(y_true, y_pred, average=average, zero_division=0),
            'f1_score': f1_score(y_true, y_pred, average=average, zero_division=0)
        }
        
        # Add AUC for binary classification
        if len(np.unique(y_true)) == 2:
            metrics['auc_roc'] = roc_auc_score(y_true, y_pred_proba[:, 1])
        
        # Add confusion matrix
        metrics['confusion_matrix'] = confusion_matrix(y_true, y_pred)
        
        # Add classification report
        metrics['classification_report'] = classification_report(y_true, y_pred, output_dict=True)
        
        # Add feature importance
        if 'feature_importance' in pred_data:
            feature_importance_df = pd.DataFrame({
                'feature': pred_data['feature_names'],
                'importance': pred_data['feature_importance']
            }).sort_values('importance', ascending=False)
            metrics['feature_importance'] = feature_importance_df
        
        new_pipe.metrics[pred_name] = metrics
        new_pipe.current_analysis = f'metrics_{pred_name}'
        
        return new_pipe
    
    return _calculate_metrics


def print_metrics(
    prediction_name: Optional[str] = None,
    model_name: str = 'rf_model'
):
    """
    Print classification metrics in a formatted way
    
    Parameters:
    -----------
    prediction_name : Optional[str]
        Name of predictions to print metrics for
    model_name : str
        Model name to use if prediction_name not specified
        
    Returns:
    --------
    Callable
        Function that prints metrics from an RFPipe
    """
    def _print_metrics(pipe):
        if prediction_name is None:
            pred_name = f"{model_name}_test_predictions"
        else:
            pred_name = prediction_name
        
        if pred_name not in pipe.metrics:
            raise ValueError(f"Metrics for '{pred_name}' not found in pipeline.")
        
        metrics = pipe.metrics[pred_name]
        
        print(f"\n=== Classification Metrics for {pred_name} ===")
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1-Score:  {metrics['f1_score']:.4f}")
        
        if 'auc_roc' in metrics:
            print(f"AUC-ROC:   {metrics['auc_roc']:.4f}")
        
        print(f"\nConfusion Matrix:")
        print(metrics['confusion_matrix'])
        
        if 'feature_importance' in metrics:
            print(f"\nTop 10 Most Important Features:")
            print(metrics['feature_importance'].head(10))
        
        return pipe
    
    return _print_metrics


def save_rf_model(
    model_name: str = 'rf_model',
    filepath: Optional[str] = None,
    include_preprocessing: bool = True
):
    """
    Save a trained Random Forest model with preprocessing pipeline
    
    Parameters:
    -----------
    model_name : str
        Name of the model to save
    filepath : Optional[str]
        Path to save the model
    include_preprocessing : bool
        Whether to include scalers, encoders, and feature selectors
        
    Returns:
    --------
    Callable
        Function that saves a Random Forest model from an RFPipe
    """
    def _save_rf_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        new_pipe = pipe.copy()
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f"{model_name}_{timestamp}.joblib"
        else:
            save_path = filepath
        
        # Package model with metadata
        model_package = {
            'model': pipe.models[model_name],
            'model_type': 'RandomForestClassifier',
            'feature_columns': pipe.feature_columns,
            'target_column': pipe.target_column,
            'train_test_splits': pipe.train_test_splits.get(model_name, {}),
            'predictions': {k: v for k, v in pipe.predictions.items() if model_name in k},
            'metrics': {k: v for k, v in pipe.metrics.items() if model_name in k}
        }
        
        if include_preprocessing:
            model_package.update({
                'scalers': pipe.scalers,
                'encoders': pipe.encoders,
                'feature_selectors': pipe.feature_selectors
            })
        
        joblib.dump(model_package, save_path)
        print(f"Random Forest model saved to: {save_path}")
        
        return new_pipe
    
    return _save_rf_model


def load_rf_model(
    filepath: str,
    model_name: str = 'loaded_model'
):
    """
    Load a previously saved Random Forest model
    
    Parameters:
    -----------
    filepath : str
        Path to the saved model file
    model_name : str
        Name for the loaded model
        
    Returns:
    --------
    Callable
        Function that loads Random Forest models into an RFPipe
    """
    def _load_rf_model(pipe):
        try:
            model_package = joblib.load(filepath)
            
            new_pipe = pipe.copy()
            
            # Restore model
            new_pipe.models[model_name] = model_package['model']
            
            # Restore feature columns and target column
            if 'feature_columns' in model_package:
                new_pipe.feature_columns = model_package['feature_columns']
            if 'target_column' in model_package:
                new_pipe.target_column = model_package['target_column']
            
            # Restore train-test splits
            if 'train_test_splits' in model_package:
                new_pipe.train_test_splits[model_name] = model_package['train_test_splits']
            
            # Restore predictions
            if 'predictions' in model_package:
                for pred_name, pred_data in model_package['predictions'].items():
                    new_pred_name = pred_name.replace('rf_model', model_name)
                    new_pipe.predictions[new_pred_name] = pred_data
            
            # Restore metrics
            if 'metrics' in model_package:
                for metric_name, metric_data in model_package['metrics'].items():
                    new_metric_name = metric_name.replace('rf_model', model_name)
                    new_pipe.metrics[new_metric_name] = metric_data
            
            # Restore preprocessing components
            if 'scalers' in model_package:
                new_pipe.scalers = model_package['scalers']
            if 'encoders' in model_package:
                new_pipe.encoders = model_package['encoders']
            if 'feature_selectors' in model_package:
                new_pipe.feature_selectors = model_package['feature_selectors']
            
            new_pipe.current_analysis = f'loaded_model_{model_name}'
            
            print(f"Successfully loaded Random Forest model from: {filepath}")
            print(f"Model name: {model_name}")
            print(f"Model type: {model_package.get('model_type', 'unknown')}")
            print(f"Number of features: {len(model_package.get('feature_columns', []))}")
            print(f"Target column: {model_package.get('target_column', 'unknown')}")
            
            return new_pipe
            
        except Exception as e:
            raise ValueError(f"Failed to load model from {filepath}: {str(e)}")
    
    return _load_rf_model


def add_features(
    feature_columns: List[str],
    feature_type: str = 'classification',
    feature_name: str = 'additional_features'
):
    """
    Add new features to the Random Forest classification pipeline
    
    Parameters:
    -----------
    feature_columns : List[str]
        List of new feature column names to add
    feature_type : str
        Type of features ('classification', 'auxiliary', 'derived')
    feature_name : str
        Name for the feature addition operation
        
    Returns:
    --------
    Callable
        Function that adds features to an RFPipe
    """
    def _add_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided before adding features.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Validate that new features exist in the data
        missing_features = [col for col in feature_columns if col not in df.columns]
        if missing_features:
            raise ValueError(f"Missing features in data: {missing_features}")
        
        # Add features based on type
        if feature_type == 'classification':
            # Check if these are categorical features that need encoding
            categorical_features = []
            numerical_features = []
            
            for col in feature_columns:
                if col in df.columns:
                    if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                        # This is a categorical feature - don't add to feature_columns yet
                        categorical_features.append(col)
                    else:
                        # This is a numerical feature - safe to add
                        numerical_features.append(col)
            
            # Add numerical features to feature_columns
            if numerical_features:
                new_pipe.feature_columns.extend(numerical_features)
                print(f"Added {len(numerical_features)} numerical classification features: {numerical_features}")
            
            # Store categorical features for later encoding
            if categorical_features:
                if not hasattr(new_pipe, 'pending_categorical_features'):
                    new_pipe.pending_categorical_features = {}
                new_pipe.pending_categorical_features[feature_name] = {
                    'columns': categorical_features,
                    'type': 'categorical'
                }
                print(f"Added {len(categorical_features)} categorical features (pending encoding): {categorical_features}")
            
        elif feature_type == 'auxiliary':
            # Store auxiliary features (not used for classification but available for analysis)
            if not hasattr(new_pipe, 'auxiliary_features'):
                new_pipe.auxiliary_features = {}
            new_pipe.auxiliary_features[feature_name] = {
                'columns': feature_columns,
                'type': 'auxiliary'
            }
            print(f"Added {len(feature_columns)} auxiliary features: {feature_columns}")
            
        elif feature_type == 'derived':
            # Store derived features (computed from existing features)
            if not hasattr(new_pipe, 'derived_features'):
                new_pipe.derived_features = {}
            new_pipe.derived_features[feature_name] = {
                'columns': feature_columns,
                'type': 'derived'
            }
            print(f"Added {len(feature_columns)} derived features: {feature_columns}")
        
        else:
            raise ValueError(f"Unknown feature type: {feature_type}")
        
        new_pipe.current_analysis = f'add_features_{feature_name}'
        
        return new_pipe
    
    return _add_features


def retrain_rf_model(
    model_name: str,
    new_data: Optional[pd.DataFrame] = None,
    feature_subset: Optional[List[str]] = None,
    update_config: Optional[Dict] = None,
    retrain_name: str = 'retrained_model'
):
    """
    Retrain a Random Forest model with new data or updated configuration
    
    Parameters:
    -----------
    model_name : str
        Name of the existing model to retrain
    new_data : Optional[pd.DataFrame]
        New data to use for retraining (if None, uses existing data)
    feature_subset : Optional[List[str]]
        Subset of features to use for retraining
    update_config : Optional[Dict]
        Updated configuration parameters for the model
    retrain_name : str
        Name for the retrained model
        
    Returns:
    --------
    Callable
        Function that retrains Random Forest models from an RFPipe
    """
    def _retrain_rf_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for retraining.")
        
        new_pipe = pipe.copy()
        
        # Get the original model configuration
        original_model = new_pipe.models[model_name]
        original_config = {
            'n_estimators': original_model.n_estimators,
            'max_depth': original_model.max_depth,
            'min_samples_split': original_model.min_samples_split,
            'min_samples_leaf': original_model.min_samples_leaf,
            'random_state': original_model.random_state
        }
        
        # Update configuration if provided
        if update_config:
            original_config.update(update_config)
        
        # Determine data to use for retraining
        # Initialize features to use for retraining
        features_to_use = feature_subset if feature_subset is not None else new_pipe.feature_columns
            
        if new_data is not None:
            retrain_data = new_data.copy()
            
            missing_features = [col for col in features_to_use if col not in retrain_data.columns]
            if missing_features:
                print(f"Warning: Missing features in new data: {missing_features}")
                print("Attempting to apply preprocessing to new data...")
                
                # Try to apply the same preprocessing steps that were used during training
                # Apply numerical feature transformations
                for feature in missing_features:
                    if feature.startswith('num_feat_log_'):
                        base_col = feature.replace('num_feat_log_', '')
                        if base_col in retrain_data.columns:
                            retrain_data[feature] = np.log(np.abs(retrain_data[base_col]) + 1e-8)
                    elif feature.startswith('num_feat_sqrt_'):
                        base_col = feature.replace('num_feat_sqrt_', '')
                        if base_col in retrain_data.columns:
                            retrain_data[feature] = np.sqrt(np.abs(retrain_data[base_col]))
                    elif feature.startswith('num_feat_square_'):
                        base_col = feature.replace('num_feat_square_', '')
                        if base_col in retrain_data.columns:
                            retrain_data[feature] = retrain_data[base_col] ** 2
                    elif feature.startswith('interaction_multiply_'):
                        # Extract column names from interaction feature
                        parts = feature.replace('interaction_multiply_', '').split('_')
                        if len(parts) >= 2:
                            col1 = parts[0]
                            col2 = '_'.join(parts[1:])
                            if col1 in retrain_data.columns and col2 in retrain_data.columns:
                                retrain_data[feature] = retrain_data[col1] * retrain_data[col2]
                    elif feature.startswith('interaction_divide_'):
                        # Extract column names from interaction feature
                        parts = feature.replace('interaction_divide_', '').split('_')
                        if len(parts) >= 2:
                            col1 = parts[0]
                            col2 = '_'.join(parts[1:])
                            if col1 in retrain_data.columns and col2 in retrain_data.columns:
                                retrain_data[feature] = retrain_data[col1] / (retrain_data[col2] + 1e-8)
                    else:
                        # Generic one-hot encoding handling for any categorical feature
                        # Look for pattern: base_column_category
                        for base_col in retrain_data.columns:
                            if feature.startswith(f'{base_col}_') and feature != base_col:
                                category = feature.replace(f'{base_col}_', '')
                                retrain_data[feature] = (retrain_data[base_col] == category).astype(int)
                                break
                
                # Check again for missing features after preprocessing
                still_missing = [col for col in features_to_use if col not in retrain_data.columns]
                if still_missing:
                    print(f"Still missing features after preprocessing: {still_missing}")
                    # Use only available features
                    available_features = [col for col in features_to_use if col in retrain_data.columns]
                    if not available_features:
                        raise ValueError(f"No required features found in new data after preprocessing. Available columns: {list(retrain_data.columns)}")
                    print(f"Using available features: {available_features}")
                    features_to_use = available_features
        else:
            retrain_data = new_pipe.data
            if retrain_data is None:
                raise ValueError("No data available for retraining.")
        
        # Select features for retraining
        clustering_features = features_to_use
        
        # Validate features exist in data
        missing_features = [col for col in clustering_features if col not in retrain_data.columns]
        if missing_features:
            raise ValueError(f"Missing features in data: {missing_features}")
        
        # Validate target column exists
        if new_pipe.target_column not in retrain_data.columns:
            raise ValueError(f"Target column '{new_pipe.target_column}' not found in data. Available columns: {list(retrain_data.columns)}")
        
        X = retrain_data[clustering_features]
        y = retrain_data[new_pipe.target_column]
        
        # Create new model with updated configuration
        retrained_model = RandomForestClassifier(
            n_estimators=original_config['n_estimators'],
            max_depth=original_config['max_depth'],
            min_samples_split=original_config['min_samples_split'],
            min_samples_leaf=original_config['min_samples_leaf'],
            random_state=original_config['random_state']
        )
        
        # Fit the retrained model
        retrained_model.fit(X, y)
        
        # Store the retrained model
        new_pipe.models[retrain_name] = retrained_model
        
        # Generate predictions for retrained model
        y_pred = retrained_model.predict(X)
        y_pred_proba = retrained_model.predict_proba(X)
        
        new_pipe.predictions[f'{retrain_name}_predictions'] = {
            'y_true': y,
            'y_pred': y_pred,
            'y_pred_proba': y_pred_proba,
            'feature_importance': retrained_model.feature_importances_,
            'feature_names': clustering_features
        }
        
        # Update data if using new data
        if new_data is not None:
            new_pipe.data = retrain_data
        
        new_pipe.current_analysis = f'retrain_{retrain_name}'
        
        print(f"Successfully retrained model '{model_name}' as '{retrain_name}'")
        print(f"Number of estimators: {original_config['n_estimators']}")
        print(f"Max depth: {original_config['max_depth']}")
        print(f"Features used: {len(clustering_features)}")
        print(f"Data points: {len(X)}")
        
        return new_pipe
    
    return _retrain_rf_model


def predict_on_new_data(
    model_name: str,
    new_data: pd.DataFrame,
    feature_subset: Optional[List[str]] = None,
    prediction_name: str = 'new_data_predictions'
):
    """
    Make predictions on new data using a trained Random Forest model
    
    Parameters:
    -----------
    model_name : str
        Name of the trained model to use for prediction
    new_data : pd.DataFrame
        New data to predict on (can be raw data or preprocessed data)
    feature_subset : Optional[List[str]]
        Subset of features to use for prediction
    prediction_name : str
        Name for the prediction results
        
    Returns:
    --------
    Callable
        Function that predicts on new data from an RFPipe
    """
    def _predict_on_new_data(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for prediction.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]
        
        # Select features for prediction
        if feature_subset:
            prediction_features = feature_subset
        else:
            prediction_features = new_pipe.feature_columns
        
        # Check if new data has the required features
        missing_features = [col for col in prediction_features if col not in new_data.columns]
        
        # Ensure feature order matches the model's expected order
        if hasattr(model, 'feature_names_in_'):
            expected_features = model.feature_names_in_
            # Reorder prediction_features to match expected order
            available_features = [f for f in expected_features if f in new_data.columns]
            missing_expected = [f for f in expected_features if f not in new_data.columns]
            
            if missing_expected:
                print(f"Warning: Missing expected features: {missing_expected}")
                # Add missing features with default values
                for feature in missing_expected:
                    new_data[feature] = 0.0
                print(f"Added {len(missing_expected)} missing features with default values")
            
            # Use all expected features in the correct order
            prediction_features = expected_features.tolist()
        else:
            # Fallback to available features
            prediction_features = [f for f in prediction_features if f in new_data.columns]
        
        if missing_features:
            # If features are missing, we need to apply preprocessing
            print(f"Missing features in new data. Attempting to apply preprocessing...")
            print(f"Missing features: {missing_features}")
            
            # Try to apply the same preprocessing steps that were used during training
            processed_data = new_data.copy()
            
            # Apply numerical feature transformations
            if hasattr(new_pipe, 'scalers') and new_pipe.scalers:
                for scaler_name, scaler in new_pipe.scalers.items():
                    if scaler_name in processed_data.columns:
                        processed_data[scaler_name] = scaler.transform(processed_data[[scaler_name]])
            
            # Apply categorical encodings
            if hasattr(new_pipe, 'encoders') and new_pipe.encoders:
                for encoder_name, encoder_info in new_pipe.encoders.items():
                    if encoder_name in processed_data.columns:
                        # Apply one-hot encoding
                        encoded = encoder_info.transform(processed_data[[encoder_name]])
                        encoded_df = pd.DataFrame(encoded, columns=encoder_info.get_feature_names_out([encoder_name]))
                        processed_data = pd.concat([processed_data, encoded_df], axis=1)
                        processed_data.drop(columns=[encoder_name], inplace=True)
            
            # Handle one-hot encoded features that might be missing
            for feature in missing_features:
                if '_' in feature and any(col in feature for col in processed_data.columns):
                    # Generic one-hot encoding handling for any categorical feature
                    # Look for pattern: base_column_category
                    for base_col in processed_data.columns:
                        if feature.startswith(f'{base_col}_') and feature != base_col:
                            category = feature.replace(f'{base_col}_', '')
                            processed_data[feature] = (processed_data[base_col] == category).astype(int)
                            break
            
            # Try to create basic engineered features that might be missing
            for feature in missing_features:
                if feature.startswith('num_feat_log_'):
                    base_col = feature.replace('num_feat_log_', '')
                    if base_col in processed_data.columns:
                        processed_data[feature] = np.log(np.abs(processed_data[base_col]) + 1e-8)
                elif feature.startswith('num_feat_sqrt_'):
                    base_col = feature.replace('num_feat_sqrt_', '')
                    if base_col in processed_data.columns:
                        processed_data[feature] = np.sqrt(np.abs(processed_data[base_col]))
                elif feature.startswith('interaction_multiply_'):
                    # Extract column names from interaction feature
                    parts = feature.replace('interaction_multiply_', '').split('_')
                    if len(parts) >= 2:
                        col1 = parts[0]
                        col2 = '_'.join(parts[1:])
                        if col1 in processed_data.columns and col2 in processed_data.columns:
                            processed_data[feature] = processed_data[col1] * processed_data[col2]
                elif feature.startswith('interaction_divide_'):
                    # Extract column names from interaction feature
                    parts = feature.replace('interaction_divide_', '').split('_')
                    if len(parts) >= 2:
                        col1 = parts[0]
                        col2 = '_'.join(parts[1:])
                        if col1 in processed_data.columns and col2 in processed_data.columns:
                            processed_data[feature] = processed_data[col1] / (processed_data[col2] + 1e-8)
            
            # Check again for missing features after preprocessing
            still_missing = [col for col in prediction_features if col not in processed_data.columns]
            if still_missing:
                print(f"Still missing features after preprocessing: {still_missing}")
                # Use only available features
                available_features = [col for col in prediction_features if col in processed_data.columns]
                if not available_features:
                    raise ValueError(f"No required features found in new data after preprocessing. Available columns: {list(processed_data.columns)}")
                print(f"Using available features: {available_features}")
                prediction_features = available_features
                X_new = processed_data[prediction_features]
            else:
                print("All features available after preprocessing!")
                X_new = processed_data[prediction_features]
        else:
            # All features are available
            X_new = new_data[prediction_features]
        
        # Make predictions
        y_pred = model.predict(X_new)
        y_pred_proba = model.predict_proba(X_new)
        
        # Create results DataFrame
        results_df = new_data.copy()
        results_df[f'{prediction_name}_prediction'] = y_pred
        results_df[f'{prediction_name}_confidence'] = np.max(y_pred_proba, axis=1)
        
        # Add class probabilities for each class
        n_classes = y_pred_proba.shape[1]
        for i in range(n_classes):
            results_df[f'{prediction_name}_prob_class_{i}'] = y_pred_proba[:, i]
        
        # Store prediction results
        if not hasattr(new_pipe, 'new_predictions'):
            new_pipe.new_predictions = {}
        
        new_pipe.new_predictions[prediction_name] = {
            'data': results_df,
            'predictions': y_pred,
            'probabilities': y_pred_proba,
            'feature_importance': model.feature_importances_,
            'feature_names': prediction_features,
            'model_used': model_name
        }
        
        new_pipe.current_analysis = f'new_prediction_{prediction_name}'
        
        print(f"Successfully predicted on {len(new_data)} new data points")
        print(f"Model used: {model_name}")
        print(f"Features used: {len(prediction_features)}")
        print(f"Prediction distribution: {dict(pd.Series(y_pred).value_counts().sort_index())}")
        
        return new_pipe
    
    return _predict_on_new_data


def get_new_prediction_results(
    prediction_name: Optional[str] = None
):
    """
    Get new prediction results from the pipeline
    
    Parameters:
    -----------
    prediction_name : Optional[str]
        Specific prediction to retrieve (if None, returns all)
        
    Returns:
    --------
    Callable
        Function that retrieves new prediction results from an RFPipe
    """
    def _get_new_prediction_results(pipe):
        if not hasattr(pipe, 'new_predictions') or not pipe.new_predictions:
            return {"error": "No new prediction results found. Run predict_on_new_data first."}
        
        if prediction_name:
            if prediction_name in pipe.new_predictions:
                return pipe.new_predictions[prediction_name]
            else:
                return {"error": f"New prediction '{prediction_name}' not found"}
        
        return pipe.new_predictions
    
    return _get_new_prediction_results


def print_rf_summary(
    model_name: Optional[str] = None
):
    """
    Print comprehensive Random Forest analysis summary
    
    Parameters:
    -----------
    model_name : Optional[str]
        Specific model to summarize (if None, summarizes all)
        
    Returns:
    --------
    Callable
        Function that prints Random Forest summary from an RFPipe
    """
    def _print_rf_summary(pipe):
        print(f"\n=== Random Forest Classification Analysis Summary ===")
        
        if pipe.data is not None:
            print(f"Data points: {len(pipe.data)}")
            print(f"Features: {len(pipe.feature_columns)}")
            print(f"Target column: {pipe.target_column}")
            if pipe.target_column and pipe.target_column in pipe.data.columns:
                target_dist = pipe.data[pipe.target_column].value_counts()
                print(f"Target distribution: {dict(target_dist)}")
        
        # Model information
        if pipe.models:
            print(f"\n=== Models ===")
            for name, model in pipe.models.items():
                if model_name is None or name == model_name:
                    print(f"\nModel: {name}")
                    print(f"  Type: RandomForestClassifier")
                    print(f"  Number of estimators: {model.n_estimators}")
                    print(f"  Max depth: {model.max_depth}")
                    print(f"  Min samples split: {model.min_samples_split}")
                    print(f"  Min samples leaf: {model.min_samples_leaf}")
        
        # Predictions information
        if pipe.predictions:
            print(f"\n=== Predictions ===")
            for name, pred_data in pipe.predictions.items():
                if model_name is None or model_name in name:
                    print(f"\nPrediction: {name}")
                    print(f"  Number of predictions: {len(pred_data.get('y_pred', []))}")
                    if 'y_true' in pred_data:
                        print(f"  True labels available: Yes")
        
        # Metrics information
        if pipe.metrics:
            print(f"\n=== Metrics ===")
            for name, metrics in pipe.metrics.items():
                if model_name is None or model_name in name:
                    if isinstance(metrics, dict):
                        print(f"\nMetrics: {name}")
                        if 'accuracy' in metrics:
                            print(f"  Accuracy: {metrics['accuracy']:.4f}")
                        if 'precision' in metrics:
                            print(f"  Precision: {metrics['precision']:.4f}")
                        if 'recall' in metrics:
                            print(f"  Recall: {metrics['recall']:.4f}")
                        if 'f1_score' in metrics:
                            print(f"  F1-Score: {metrics['f1_score']:.4f}")
                        if 'auc_roc' in metrics:
                            print(f"  AUC-ROC: {metrics['auc_roc']:.4f}")
        
        # Feature importance information
        if pipe.predictions:
            print(f"\n=== Feature Importance ===")
            for name, pred_data in pipe.predictions.items():
                if model_name is None or model_name in name:
                    if 'feature_importance' in pred_data:
                        importance_df = pd.DataFrame({
                            'feature': pred_data['feature_names'],
                            'importance': pred_data['feature_importance']
                        }).sort_values('importance', ascending=False)
                        print(f"\nTop 5 features for {name}:")
                        for _, row in importance_df.head(5).iterrows():
                            print(f"  {row['feature']}: {row['importance']:.4f}")
        
        # Preprocessing information
        if pipe.scalers:
            print(f"\n=== Scalers ===")
            for name, scaler in pipe.scalers.items():
                print(f"  {name}: {type(scaler).__name__}")
        
        if pipe.encoders:
            print(f"\n=== Encoders ===")
            for name, encoder in pipe.encoders.items():
                print(f"  {name}: {type(encoder).__name__}")
        
        if pipe.feature_selectors:
            print(f"\n=== Feature Selectors ===")
            for name, selector in pipe.feature_selectors.items():
                print(f"  {name}: {type(selector).__name__}")
        
        return pipe
    
    return _print_rf_summary