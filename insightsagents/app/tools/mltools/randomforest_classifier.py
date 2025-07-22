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


class RFPipe:
    """
    A pipeline-style Random Forest classifier tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
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
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe RFPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = RFPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe.features = self.features.copy() if self.features is not None else None
        new_pipe.labels = self.labels.copy() if self.labels is not None else None
        new_pipe.feature_columns = self.feature_columns.copy()
        new_pipe.target_column = self.target_column
        new_pipe.models = self.models.copy()
        new_pipe.predictions = self.predictions.copy()
        new_pipe.metrics = self.metrics.copy()
        new_pipe.scalers = self.scalers.copy()
        new_pipe.encoders = self.encoders.copy()
        new_pipe.feature_selectors = self.feature_selectors.copy()
        new_pipe.current_analysis = self.current_analysis
        new_pipe.train_test_splits = self.train_test_splits.copy()
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create an RFPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


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
                new_pipe.feature_columns.extend(encoded_df.columns.tolist())
                
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
        
        new_pipe.current_analysis = 'categorical_features'
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
            # Parse string condition
            if condition.startswith('>'):
                threshold = float(condition[1:])
                mask = df[column] > threshold
            elif condition.startswith('>='):
                threshold = float(condition[2:])
                mask = df[column] >= threshold
            elif condition.startswith('<'):
                threshold = float(condition[1:])
                mask = df[column] < threshold
            elif condition.startswith('<='):
                threshold = float(condition[2:])
                mask = df[column] <= threshold
            elif condition.startswith('=='):
                value = condition[2:]
                try:
                    value = float(value)
                except ValueError:
                    pass
                mask = df[column] == value
            else:
                raise ValueError(f"Invalid condition format: {condition}")
        
        elif callable(condition):
            mask = condition(df[column])
        else:
            raise ValueError("Condition must be a string or callable")
        
        df[label_column] = negative_label
        df.loc[mask, label_column] = positive_label
        
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
        
        X = df[new_pipe.feature_columns]
        y = df[new_pipe.target_column]
        
        if method == 'kbest':
            selector = SelectKBest(score_func=score_func, k=k)
        elif method == 'mutual_info':
            selector = SelectKBest(score_func=mutual_info_classif, k=k)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        X_selected = selector.fit_transform(X, y)
        selected_features = [new_pipe.feature_columns[i] for i in selector.get_support(indices=True)]
        
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