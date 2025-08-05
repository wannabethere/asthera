import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from sklearn.linear_model import LogisticRegression, RidgeClassifier, LogisticRegressionCV
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, LabelEncoder, PolynomialFeatures
from sklearn.feature_selection import SelectKBest, f_classif, chi2, RFE, SelectFromModel
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV, RandomizedSearchCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, 
    confusion_matrix, classification_report, roc_curve, precision_recall_curve,
    log_loss, matthews_corrcoef, cohen_kappa_score
)
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import joblib
import warnings
from datetime import datetime
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor
from sklearn.pipeline import Pipeline
import itertools
from ..base_pipe import BasePipe


class LogisticRegressionPipe(BasePipe):
    """
    A pipeline-style logistic regression tool that enables functional composition
    with a meterstick-like interface for classification tasks.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for logistic regression analysis"""
        self.original_data = None
        self.feature_columns = []
        self.target_column = None
        self.models = {}
        self.predictions = {}
        self.evaluation_metrics = {}
        self.feature_importance = {}
        self.scalers = {}
        self.feature_selectors = {}
        self.hyperparameter_tuning = {}
        self.cross_validation = {}
        self.calibration_results = {}
        self.current_analysis = None
        self.class_mapping = {}
        self.train_test_splits = {}
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'original_data'):
            self.original_data = source_pipe.original_data.copy() if source_pipe.original_data is not None else None
        if hasattr(source_pipe, 'feature_columns'):
            self.feature_columns = source_pipe.feature_columns.copy()
        if hasattr(source_pipe, 'target_column'):
            self.target_column = source_pipe.target_column
        if hasattr(source_pipe, 'models'):
            self.models = source_pipe.models.copy()
        if hasattr(source_pipe, 'predictions'):
            self.predictions = source_pipe.predictions.copy()
        if hasattr(source_pipe, 'evaluation_metrics'):
            self.evaluation_metrics = source_pipe.evaluation_metrics.copy()
        if hasattr(source_pipe, 'feature_importance'):
            self.feature_importance = source_pipe.feature_importance.copy()
        if hasattr(source_pipe, 'scalers'):
            self.scalers = source_pipe.scalers.copy()
        if hasattr(source_pipe, 'feature_selectors'):
            self.feature_selectors = source_pipe.feature_selectors.copy()
        if hasattr(source_pipe, 'hyperparameter_tuning'):
            self.hyperparameter_tuning = source_pipe.hyperparameter_tuning.copy()
        if hasattr(source_pipe, 'cross_validation'):
            self.cross_validation = source_pipe.cross_validation.copy()
        if hasattr(source_pipe, 'calibration_results'):
            self.calibration_results = source_pipe.calibration_results.copy()
        if hasattr(source_pipe, 'current_analysis'):
            self.current_analysis = source_pipe.current_analysis
        if hasattr(source_pipe, 'class_mapping'):
            self.class_mapping = source_pipe.class_mapping.copy()
        if hasattr(source_pipe, 'train_test_splits'):
            self.train_test_splits = source_pipe.train_test_splits.copy()
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the logistic regression analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in logistic regression pipe)
            
        Returns:
        --------
        dict
            Summary of the logistic regression analysis results
        """
        if not any([self.models, self.predictions, self.evaluation_metrics]):
            return {"error": "No logistic regression analysis has been performed"}
        
        # Count analyses by type
        analysis_types = {
            'models': len(self.models),
            'predictions': len(self.predictions),
            'evaluation_metrics': len(self.evaluation_metrics),
            'feature_importance': len(self.feature_importance),
            'scalers': len(self.scalers),
            'feature_selectors': len(self.feature_selectors),
            'hyperparameter_tuning': len(self.hyperparameter_tuning),
            'cross_validation': len(self.cross_validation),
            'calibration_results': len(self.calibration_results)
        }
        
        # Get target distribution if available
        target_dist = None
        if self.data is not None and self.target_column:
            target_dist = self.data[self.target_column].value_counts().to_dict()
        
        # Get model information
        models_info = {}
        for name, model_info in self.models.items():
            models_info[name] = {
                "type": model_info.get('type', 'unknown'),
                "solver": model_info.get('config', {}).get('solver', 'unknown'),
                "regularization": model_info.get('config', {}).get('penalty', 'unknown'),
                "fitted": model_info.get('fitted', False)
            }
        
        # Get evaluation metrics summary
        metrics_summary = {}
        for name, metrics in self.evaluation_metrics.items():
            metrics_summary[name] = {
                "accuracy": metrics.get('accuracy', None),
                "precision": metrics.get('precision', None),
                "recall": metrics.get('recall', None),
                "f1_score": metrics.get('f1_score', None),
                "auc_score": metrics.get('auc_score', None)
            }
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "feature_columns": self.feature_columns,
            "target_column": self.target_column,
            "target_distribution": target_dist,
            "class_mapping": self.class_mapping,
            "analysis_types": analysis_types,
            "current_analysis": self.current_analysis,
            "available_models": list(self.models.keys()),
            "available_predictions": list(self.predictions.keys()),
            "available_evaluation_metrics": list(self.evaluation_metrics.keys()),
            "available_feature_importance": list(self.feature_importance.keys()),
            "available_scalers": list(self.scalers.keys()),
            "available_feature_selectors": list(self.feature_selectors.keys()),
            "available_hyperparameter_tuning": list(self.hyperparameter_tuning.keys()),
            "available_cross_validation": list(self.cross_validation.keys()),
            "available_calibration_results": list(self.calibration_results.keys()),
            "models_info": models_info,
            "evaluation_metrics_summary": metrics_summary,
            "scalers_info": {name: {"type": type(scaler).__name__} 
                           for name, scaler in self.scalers.items()},
            "feature_selectors_info": {name: {"method": selector.get('method', 'unknown'), 
                                            "n_features": selector.get('k', 'unknown')} 
                                     for name, selector in self.feature_selectors.items()}
        }
    
    def to_df(self, include_metadata: bool = False, include_original: bool = True):
        """
        Convert the logistic regression analysis results to a DataFrame
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        include_original : bool, default=True
            Whether to include original data columns in the output DataFrame
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the logistic regression analysis results
            
        Raises:
        -------
        ValueError
            If no data is available
        """
        if self.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        # Get the result DataFrame (contains original data + predictions)
        result_df = self.data.copy()
        
        # Filter columns based on parameters
        columns_to_include = []
        
        if include_original:
            # Include original columns (those that don't have prediction suffixes)
            original_cols = [col for col in result_df.columns 
                           if not any(suffix in col for suffix in ['_prediction', '_probability', '_score'])]
            columns_to_include.extend(original_cols)
        
        # Include prediction columns
        prediction_cols = [col for col in result_df.columns 
                          if any(suffix in col for suffix in ['_prediction', '_probability', '_score'])]
        columns_to_include.extend(prediction_cols)
        
        # Create the output DataFrame
        output_df = result_df[columns_to_include].copy()
        
        # Add metadata if requested
        if include_metadata:
            # Add information about available analyses
            if self.models:
                output_df['has_models'] = True
                output_df['model_names'] = ', '.join(self.models.keys())
            else:
                output_df['has_models'] = False
                output_df['model_names'] = ''
            
            if self.predictions:
                output_df['has_predictions'] = True
                output_df['prediction_names'] = ', '.join(self.predictions.keys())
            else:
                output_df['has_predictions'] = False
                output_df['prediction_names'] = ''
            
            if self.evaluation_metrics:
                output_df['has_evaluation_metrics'] = True
                output_df['evaluation_metric_names'] = ', '.join(self.evaluation_metrics.keys())
            else:
                output_df['has_evaluation_metrics'] = False
                output_df['evaluation_metric_names'] = ''
            
            # Add current analysis information
            output_df['current_analysis'] = self.current_analysis or 'none'
            output_df['target_column'] = self.target_column or 'none'
            output_df['n_features'] = len(self.feature_columns)
        
        return output_df


# Data Preparation Functions
def prepare_classification_data(
    feature_columns: List[str],
    target_column: str,
    scaling_method: str = 'standard',
    handle_missing: str = 'drop',
    handle_categorical: str = 'encode',
    remove_outliers: bool = False,
    outlier_method: str = 'iqr',
    outlier_threshold: float = 3.0,
    encode_target: bool = True
):
    """
    Prepare data for logistic regression
    
    Parameters:
    -----------
    feature_columns : List[str]
        Columns to use as features
    target_column : str
        Target column for classification
    scaling_method : str
        Scaling method ('standard', 'minmax', 'robust', 'none')
    handle_missing : str
        How to handle missing values ('drop', 'mean', 'median', 'mode')
    handle_categorical : str
        How to handle categorical features ('encode', 'drop', 'dummy')
    remove_outliers : bool
        Whether to remove outliers
    outlier_method : str
        Outlier detection method ('iqr', 'zscore')
    outlier_threshold : float
        Threshold for outlier removal
    encode_target : bool
        Whether to encode the target variable
        
    Returns:
    --------
    Callable
        Function that prepares classification data from a LogisticRegressionPipe
    """
    def _prepare_classification_data(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()
        
        # Validate columns exist
        all_columns = feature_columns + [target_column]
        missing_cols = [col for col in all_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in data: {missing_cols}")
        
        # Handle missing values
        if handle_missing == 'drop':
            df = df[all_columns].dropna()
        elif handle_missing == 'mean':
            for col in feature_columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].mean())
        elif handle_missing == 'median':
            for col in feature_columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = df[col].fillna(df[col].median())
        elif handle_missing == 'mode':
            for col in feature_columns:
                mode_val = df[col].mode()
                if not mode_val.empty:
                    df[col] = df[col].fillna(mode_val[0])
        
        # Handle categorical features
        processed_features = []
        for col in feature_columns:
            if pd.api.types.is_categorical_dtype(df[col]) or df[col].dtype == 'object':
                if handle_categorical == 'encode':
                    le = LabelEncoder()
                    df[col] = le.fit_transform(df[col].astype(str))
                    processed_features.append(col)
                elif handle_categorical == 'dummy':
                    dummies = pd.get_dummies(df[col], prefix=col)
                    df = pd.concat([df, dummies], axis=1)
                    processed_features.extend(dummies.columns.tolist())
                # 'drop' means we just don't include it
                elif handle_categorical != 'drop':
                    processed_features.append(col)
            else:
                processed_features.append(col)
        
        # Remove outliers if requested
        if remove_outliers:
            numeric_features = [col for col in processed_features 
                              if pd.api.types.is_numeric_dtype(df[col])]
            
            if numeric_features:
                if outlier_method == 'iqr':
                    Q1 = df[numeric_features].quantile(0.25)
                    Q3 = df[numeric_features].quantile(0.75)
                    IQR = Q3 - Q1
                    outlier_mask = ~((df[numeric_features] < (Q1 - 1.5 * IQR)) | 
                                   (df[numeric_features] > (Q3 + 1.5 * IQR))).any(axis=1)
                elif outlier_method == 'zscore':
                    z_scores = np.abs((df[numeric_features] - df[numeric_features].mean()) / 
                                    df[numeric_features].std())
                    outlier_mask = (z_scores < outlier_threshold).all(axis=1)
                else:
                    raise ValueError(f"Unknown outlier method: {outlier_method}")
                
                df = df[outlier_mask]
        
        # Scale features
        numeric_features = [col for col in processed_features 
                          if pd.api.types.is_numeric_dtype(df[col])]
        
        if numeric_features and scaling_method != 'none':
            if scaling_method == 'standard':
                scaler = StandardScaler()
            elif scaling_method == 'minmax':
                scaler = MinMaxScaler()
            elif scaling_method == 'robust':
                scaler = RobustScaler()
            else:
                raise ValueError(f"Unknown scaling method: {scaling_method}")
            
            df[numeric_features] = scaler.fit_transform(df[numeric_features])
            new_pipe.scalers['features'] = scaler
        
        # Handle target encoding
        if encode_target and not pd.api.types.is_numeric_dtype(df[target_column]):
            le_target = LabelEncoder()
            df[target_column] = le_target.fit_transform(df[target_column].astype(str))
            new_pipe.class_mapping = dict(enumerate(le_target.classes_))
        
        # Update pipe attributes
        new_pipe.data = df
        new_pipe.feature_columns = processed_features
        new_pipe.target_column = target_column
        new_pipe.current_analysis = 'data_preparation'
        
        return new_pipe
    
    return _prepare_classification_data


def engineer_features(
    interaction_features: bool = True,
    polynomial_features: Optional[List[str]] = None,
    polynomial_degree: int = 2,
    ratio_features: Optional[List[Tuple[str, str]]] = None,
    binning_features: Optional[Dict[str, int]] = None,
    statistical_features: bool = True
):
    """
    Engineer features for logistic regression
    
    Parameters:
    -----------
    interaction_features : bool
        Whether to create pairwise interaction features
    polynomial_features : Optional[List[str]]
        Features to create polynomial terms for
    polynomial_degree : int
        Degree of polynomial features
    ratio_features : Optional[List[Tuple[str, str]]]
        Pairs of features to create ratios
    binning_features : Optional[Dict[str, int]]
        Features to bin with number of bins
    statistical_features : bool
        Whether to create statistical aggregation features
        
    Returns:
    --------
    Callable
        Function that engineers features from a LogisticRegressionPipe
    """
    def _engineer_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()
        new_features = []
        
        # Create interaction features
        if interaction_features and len(new_pipe.feature_columns) >= 2:
            numeric_features = [col for col in new_pipe.feature_columns 
                              if pd.api.types.is_numeric_dtype(df[col])]
            
            for i, col1 in enumerate(numeric_features):
                for col2 in numeric_features[i+1:]:
                    interaction_name = f'{col1}_x_{col2}'
                    df[interaction_name] = df[col1] * df[col2]
                    new_features.append(interaction_name)
        
        # Create polynomial features
        if polynomial_features:
            for col in polynomial_features:
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    for degree in range(2, polynomial_degree + 1):
                        poly_name = f'{col}_poly_{degree}'
                        df[poly_name] = df[col] ** degree
                        new_features.append(poly_name)
        
        # Create ratio features
        if ratio_features:
            for col1, col2 in ratio_features:
                if col1 in df.columns and col2 in df.columns:
                    if pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2]):
                        ratio_name = f'{col1}_div_{col2}'
                        df[ratio_name] = df[col1] / (df[col2] + 1e-8)  # Avoid division by zero
                        new_features.append(ratio_name)
        
        # Create binning features
        if binning_features:
            for col, n_bins in binning_features.items():
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    binned_name = f'{col}_binned'
                    df[binned_name] = pd.cut(df[col], bins=n_bins, labels=False)
                    new_features.append(binned_name)
        
        # Create statistical features
        if statistical_features:
            numeric_features = [col for col in new_pipe.feature_columns 
                              if pd.api.types.is_numeric_dtype(df[col])]
            
            if len(numeric_features) >= 2:
                # Mean of all numeric features
                df['features_mean'] = df[numeric_features].mean(axis=1)
                new_features.append('features_mean')
                
                # Standard deviation of all numeric features
                df['features_std'] = df[numeric_features].std(axis=1)
                new_features.append('features_std')
                
                # Min and max
                df['features_min'] = df[numeric_features].min(axis=1)
                df['features_max'] = df[numeric_features].max(axis=1)
                new_features.extend(['features_min', 'features_max'])
        
        # Update feature columns and data
        new_pipe.data = df
        new_pipe.feature_columns.extend(new_features)
        new_pipe.current_analysis = 'feature_engineering'
        
        return new_pipe
    
    return _engineer_features


def select_features(
    method: str = 'k_best',
    k: int = 10,
    score_func: str = 'f_classif',
    selector_name: str = 'default'
):
    """
    Apply feature selection for logistic regression
    
    Parameters:
    -----------
    method : str
        Feature selection method ('k_best', 'rfe', 'from_model')
    k : int
        Number of features to select
    score_func : str
        Scoring function ('f_classif', 'chi2')
    selector_name : str
        Name to store the selector under
        
    Returns:
    --------
    Callable
        Function that selects features from a LogisticRegressionPipe
    """
    def _select_features(pipe):
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available.")
        
        new_pipe = pipe.copy()
        X = new_pipe.data[new_pipe.feature_columns]
        y = new_pipe.data[new_pipe.target_column]
        
        if method == 'k_best':
            if score_func == 'f_classif':
                selector = SelectKBest(f_classif, k=k)
            elif score_func == 'chi2':
                # Ensure non-negative values for chi2
                X = X - X.min() + 1e-8
                selector = SelectKBest(chi2, k=k)
            else:
                raise ValueError(f"Unknown score function: {score_func}")
                
        elif method == 'rfe':
            base_estimator = LogisticRegression(random_state=42, max_iter=1000)
            selector = RFE(base_estimator, n_features_to_select=k)
            
        elif method == 'from_model':
            base_estimator = RandomForestClassifier(n_estimators=100, random_state=42)
            selector = SelectFromModel(base_estimator, max_features=k)
            
        else:
            raise ValueError(f"Unknown selection method: {method}")
        
        # Fit selector and transform features
        X_selected = selector.fit_transform(X, y)
        
        # Get selected feature names
        if hasattr(selector, 'get_support'):
            mask = selector.get_support()
            selected_features = [feat for feat, selected in zip(new_pipe.feature_columns, mask) if selected]
        else:
            # For SelectFromModel
            selected_features = [feat for feat, selected in 
                               zip(new_pipe.feature_columns, selector.get_support()) if selected]
        
        # Update data with selected features
        new_pipe.feature_columns = selected_features
        
        # Store selector
        new_pipe.feature_selectors[selector_name] = {
            'selector': selector,
            'method': method,
            'k': len(selected_features),
            'selected_features': selected_features
        }
        
        new_pipe.current_analysis = f'feature_selection_{selector_name}'
        
        return new_pipe
    
    return _select_features


# Model Configuration and Training Functions
def configure_logistic_regression(
    penalty: str = 'l2',
    C: float = 1.0,
    solver: str = 'lbfgs',
    max_iter: int = 1000,
    random_state: int = 42,
    class_weight: Optional[Union[str, Dict]] = None,
    multi_class: str = 'auto',
    model_name: str = 'logistic_model'
):
    """
    Configure logistic regression model
    
    Parameters:
    -----------
    penalty : str
        Regularization penalty ('l1', 'l2', 'elasticnet', 'none')
    C : float
        Inverse of regularization strength
    solver : str
        Algorithm to use ('liblinear', 'lbfgs', 'newton-cg', 'sag', 'saga')
    max_iter : int
        Maximum number of iterations
    random_state : int
        Random seed
    class_weight : Optional[Union[str, Dict]]
        Class weights ('balanced', dict, or None)
    multi_class : str
        Multi-class strategy ('auto', 'ovr', 'multinomial')
    model_name : str
        Name for the model
        
    Returns:
    --------
    Callable
        Function that configures logistic regression in a LogisticRegressionPipe
    """
    def _configure_logistic_regression(pipe):
        new_pipe = pipe.copy()
        
        model = LogisticRegression(
            penalty=penalty,
            C=C,
            solver=solver,
            max_iter=max_iter,
            random_state=random_state,
            class_weight=class_weight,
            multi_class=multi_class
        )
        
        new_pipe.models[model_name] = {
            'model': model,
            'type': 'logistic_regression',
            'config': {
                'penalty': penalty,
                'C': C,
                'solver': solver,
                'max_iter': max_iter,
                'random_state': random_state,
                'class_weight': class_weight,
                'multi_class': multi_class
            },
            'fitted': False
        }
        
        new_pipe.current_analysis = f'configure_{model_name}'
        
        return new_pipe
    
    return _configure_logistic_regression


def configure_ridge_classifier(
    alpha: float = 1.0,
    solver: str = 'auto',
    random_state: int = 42,
    class_weight: Optional[Union[str, Dict]] = None,
    model_name: str = 'ridge_model'
):
    """
    Configure Ridge classifier model
    
    Parameters:
    -----------
    alpha : float
        Regularization strength
    solver : str
        Solver to use ('auto', 'svd', 'cholesky', 'lsqr', 'sparse_cg', 'sag', 'saga')
    random_state : int
        Random seed
    class_weight : Optional[Union[str, Dict]]
        Class weights
    model_name : str
        Name for the model
        
    Returns:
    --------
    Callable
        Function that configures Ridge classifier in a LogisticRegressionPipe
    """
    def _configure_ridge_classifier(pipe):
        new_pipe = pipe.copy()
        
        model = RidgeClassifier(
            alpha=alpha,
            solver=solver,
            random_state=random_state,
            class_weight=class_weight
        )
        
        new_pipe.models[model_name] = {
            'model': model,
            'type': 'ridge_classifier',
            'config': {
                'alpha': alpha,
                'solver': solver,
                'random_state': random_state,
                'class_weight': class_weight
            },
            'fitted': False
        }
        
        new_pipe.current_analysis = f'configure_{model_name}'
        
        return new_pipe
    
    return _configure_ridge_classifier


def split_train_test(
    test_size: float = 0.2,
    random_state: int = 42,
    stratify: bool = True,
    split_name: str = 'default'
):
    """
    Split data into training and testing sets
    
    Parameters:
    -----------
    test_size : float
        Proportion of data to use for testing
    random_state : int
        Random seed
    stratify : bool
        Whether to stratify split by target
    split_name : str
        Name for the split
        
    Returns:
    --------
    Callable
        Function that splits data from a LogisticRegressionPipe
    """
    def _split_train_test(pipe):
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available.")
        
        new_pipe = pipe.copy()
        X = new_pipe.data[new_pipe.feature_columns]
        y = new_pipe.data[new_pipe.target_column]
        
        stratify_param = y if stratify else None
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify_param
        )
        
        new_pipe.train_test_splits[split_name] = {
            'X_train': X_train,
            'X_test': X_test,
            'y_train': y_train,
            'y_test': y_test,
            'test_size': test_size,
            'stratify': stratify
        }
        
        new_pipe.current_analysis = f'train_test_split_{split_name}'
        
        return new_pipe
    
    return _split_train_test


def fit_model(
    model_name: str,
    split_name: str = 'default'
):
    """
    Fit logistic regression model
    
    Parameters:
    -----------
    model_name : str
        Name of the model to fit
    split_name : str
        Name of the train/test split to use
        
    Returns:
    --------
    Callable
        Function that fits model from a LogisticRegressionPipe
    """
    def _fit_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if split_name not in pipe.train_test_splits:
            raise ValueError(f"Train/test split '{split_name}' not found.")
        
        new_pipe = pipe.copy()
        model_info = new_pipe.models[model_name]
        model = model_info['model']
        
        split_data = new_pipe.train_test_splits[split_name]
        X_train = split_data['X_train']
        y_train = split_data['y_train']
        
        # Fit the model
        model.fit(X_train, y_train)
        
        # Mark as fitted
        new_pipe.models[model_name]['fitted'] = True
        
        new_pipe.current_analysis = f'fit_{model_name}'
        
        return new_pipe
    
    return _fit_model


# Prediction and Evaluation Functions
def predict(
    model_name: str,
    split_name: str = 'default',
    prediction_name: Optional[str] = None,
    include_probabilities: bool = True
):
    """
    Make predictions with fitted model
    
    Parameters:
    -----------
    model_name : str
        Name of the fitted model
    split_name : str
        Name of the train/test split to use
    prediction_name : Optional[str]
        Name for predictions (defaults to model_name)
    include_probabilities : bool
        Whether to include class probabilities
        
    Returns:
    --------
    Callable
        Function that makes predictions from a LogisticRegressionPipe
    """
    def _predict(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if not pipe.models[model_name]['fitted']:
            raise ValueError(f"Model '{model_name}' has not been fitted.")
        
        if split_name not in pipe.train_test_splits:
            raise ValueError(f"Train/test split '{split_name}' not found.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]['model']
        split_data = new_pipe.train_test_splits[split_name]
        
        pred_name = prediction_name or model_name
        
        # Make predictions on test set
        X_test = split_data['X_test']
        y_test = split_data['y_test']
        
        y_pred = model.predict(X_test)
        
        predictions = {
            'y_true': y_test,
            'y_pred': y_pred,
            'model_used': model_name,
            'split_used': split_name
        }
        
        if include_probabilities and hasattr(model, 'predict_proba'):
            y_proba = model.predict_proba(X_test)
            predictions['y_proba'] = y_proba
            
            # Add probability columns to main data
            for i, class_label in enumerate(model.classes_):
                prob_col = f'{pred_name}_prob_class_{class_label}'
                # Create a series with the same index as the test data
                prob_series = pd.Series(y_proba[:, i], index=X_test.index)
                new_pipe.data[prob_col] = prob_series
        
        # Add predictions to main data
        pred_series = pd.Series(y_pred, index=X_test.index)
        new_pipe.data[f'{pred_name}_prediction'] = pred_series
        
        new_pipe.predictions[pred_name] = predictions
        new_pipe.current_analysis = f'predict_{pred_name}'
        
        return new_pipe
    
    return _predict


def evaluate_model(
    prediction_name: str,
    metrics: List[str] = ['accuracy', 'precision', 'recall', 'f1', 'auc', 'confusion_matrix']
):
    """
    Evaluate model performance
    
    Parameters:
    -----------
    prediction_name : str
        Name of the predictions to evaluate
    metrics : List[str]
        Metrics to calculate
        
    Returns:
    --------
    Callable
        Function that evaluates model from a LogisticRegressionPipe
    """
    def _evaluate_model(pipe):
        if prediction_name not in pipe.predictions:
            raise ValueError(f"Predictions '{prediction_name}' not found.")
        
        new_pipe = pipe.copy()
        pred_data = new_pipe.predictions[prediction_name]
        
        y_true = pred_data['y_true']
        y_pred = pred_data['y_pred']
        y_proba = pred_data.get('y_proba')
        
        evaluation_results = {}
        
        # Calculate requested metrics
        if 'accuracy' in metrics:
            evaluation_results['accuracy'] = accuracy_score(y_true, y_pred)
        
        if 'precision' in metrics:
            evaluation_results['precision'] = precision_score(y_true, y_pred, average='weighted')
        
        if 'recall' in metrics:
            evaluation_results['recall'] = recall_score(y_true, y_pred, average='weighted')
        
        if 'f1' in metrics:
            evaluation_results['f1_score'] = f1_score(y_true, y_pred, average='weighted')
        
        if 'auc' in metrics and y_proba is not None:
            if len(np.unique(y_true)) == 2:  # Binary classification
                evaluation_results['auc_score'] = roc_auc_score(y_true, y_proba[:, 1])
            else:  # Multi-class
                evaluation_results['auc_score'] = roc_auc_score(y_true, y_proba, multi_class='ovr')
        
        if 'confusion_matrix' in metrics:
            evaluation_results['confusion_matrix'] = confusion_matrix(y_true, y_pred)
        
        if 'classification_report' in metrics:
            evaluation_results['classification_report'] = classification_report(y_true, y_pred, output_dict=True)
        
        if 'log_loss' in metrics and y_proba is not None:
            evaluation_results['log_loss'] = log_loss(y_true, y_proba)
        
        if 'matthews_corrcoef' in metrics:
            evaluation_results['matthews_corrcoef'] = matthews_corrcoef(y_true, y_pred)
        
        if 'cohen_kappa' in metrics:
            evaluation_results['cohen_kappa'] = cohen_kappa_score(y_true, y_pred)
        
        # Add class-wise metrics
        evaluation_results['class_wise_precision'] = precision_score(y_true, y_pred, average=None)
        evaluation_results['class_wise_recall'] = recall_score(y_true, y_pred, average=None)
        evaluation_results['class_wise_f1'] = f1_score(y_true, y_pred, average=None)
        
        new_pipe.evaluation_metrics[prediction_name] = evaluation_results
        new_pipe.current_analysis = f'evaluate_{prediction_name}'
        
        return new_pipe
    
    return _evaluate_model


def calculate_feature_importance(
    model_name: str,
    method: str = 'coefficients',
    importance_name: Optional[str] = None
):
    """
    Calculate feature importance
    
    Parameters:
    -----------
    model_name : str
        Name of the fitted model
    method : str
        Method to calculate importance ('coefficients', 'permutation')
    importance_name : Optional[str]
        Name for importance results
        
    Returns:
    --------
    Callable
        Function that calculates feature importance from a LogisticRegressionPipe
    """
    def _calculate_feature_importance(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if not pipe.models[model_name]['fitted']:
            raise ValueError(f"Model '{model_name}' has not been fitted.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]['model']
        
        imp_name = importance_name or model_name
        
        if method == 'coefficients':
            if hasattr(model, 'coef_'):
                if len(model.coef_.shape) == 1:  # Binary classification
                    importance_values = np.abs(model.coef_[0])
                else:  # Multi-class
                    importance_values = np.mean(np.abs(model.coef_), axis=0)
                
                importance_df = pd.DataFrame({
                    'feature': new_pipe.feature_columns,
                    'importance': importance_values
                }).sort_values('importance', ascending=False)
                
            else:
                raise ValueError(f"Model '{model_name}' does not have coefficients.")
        
        elif method == 'permutation':
            # Need test data for permutation importance
            if new_pipe.train_test_splits:
                split_name = list(new_pipe.train_test_splits.keys())[0]
                split_data = new_pipe.train_test_splits[split_name]
                
                perm_importance = permutation_importance(
                    model, split_data['X_test'], split_data['y_test'], 
                    n_repeats=10, random_state=42
                )
                
                importance_df = pd.DataFrame({
                    'feature': new_pipe.feature_columns,
                    'importance': perm_importance.importances_mean,
                    'importance_std': perm_importance.importances_std
                }).sort_values('importance', ascending=False)
            else:
                raise ValueError("No train/test splits available for permutation importance.")
        
        else:
            raise ValueError(f"Unknown importance method: {method}")
        
        new_pipe.feature_importance[imp_name] = {
            'method': method,
            'importance_data': importance_df,
            'model_used': model_name
        }
        
        new_pipe.current_analysis = f'feature_importance_{imp_name}'
        
        return new_pipe
    
    return _calculate_feature_importance


# Cross-validation and Hyperparameter Tuning
def cross_validate_model(
    model_name: str,
    cv_folds: int = 5,
    scoring: str = 'accuracy',
    cv_name: str = 'default'
):
    """
    Perform cross-validation
    
    Parameters:
    -----------
    model_name : str
        Name of the model to cross-validate
    cv_folds : int
        Number of cross-validation folds
    scoring : str
        Scoring metric
    cv_name : str
        Name for cross-validation results
        
    Returns:
    --------
    Callable
        Function that performs cross-validation from a LogisticRegressionPipe
    """
    def _cross_validate_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]['model']
        
        X = new_pipe.data[new_pipe.feature_columns]
        y = new_pipe.data[new_pipe.target_column]
        
        cv_scores = cross_val_score(model, X, y, cv=cv_folds, scoring=scoring)
        
        cv_results = {
            'scores': cv_scores,
            'mean_score': cv_scores.mean(),
            'std_score': cv_scores.std(),
            'cv_folds': cv_folds,
            'scoring': scoring,
            'model_used': model_name
        }
        
        new_pipe.cross_validation[cv_name] = cv_results
        new_pipe.current_analysis = f'cross_validation_{cv_name}'
        
        return new_pipe
    
    return _cross_validate_model


def tune_hyperparameters(
    model_name: str,
    param_grid: Dict[str, List],
    search_method: str = 'grid',
    cv_folds: int = 5,
    scoring: str = 'accuracy',
    n_iter: int = 50,
    tuning_name: str = 'default'
):
    """
    Tune hyperparameters
    
    Parameters:
    -----------
    model_name : str
        Name of the model to tune
    param_grid : Dict[str, List]
        Parameter grid for tuning
    search_method : str
        Search method ('grid', 'random')
    cv_folds : int
        Number of cross-validation folds
    scoring : str
        Scoring metric
    n_iter : int
        Number of iterations for random search
    tuning_name : str
        Name for tuning results
        
    Returns:
    --------
    Callable
        Function that tunes hyperparameters from a LogisticRegressionPipe
    """
    def _tune_hyperparameters(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if pipe.data is None or not pipe.feature_columns or not pipe.target_column:
            raise ValueError("Data, features, and target must be available.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]['model']
        
        X = new_pipe.data[new_pipe.feature_columns]
        y = new_pipe.data[new_pipe.target_column]
        
        if search_method == 'grid':
            search = GridSearchCV(
                model, param_grid, cv=cv_folds, scoring=scoring, n_jobs=-1
            )
        elif search_method == 'random':
            search = RandomizedSearchCV(
                model, param_grid, n_iter=n_iter, cv=cv_folds, 
                scoring=scoring, random_state=42, n_jobs=-1
            )
        else:
            raise ValueError(f"Unknown search method: {search_method}")
        
        search.fit(X, y)
        
        tuning_results = {
            'best_params': search.best_params_,
            'best_score': search.best_score_,
            'cv_results': search.cv_results_,
            'search_method': search_method,
            'model_used': model_name,
            'best_estimator': search.best_estimator_
        }
        
        # Update model with best parameters
        tuned_model_name = f'{model_name}_tuned'
        new_pipe.models[tuned_model_name] = {
            'model': search.best_estimator_,
            'type': new_pipe.models[model_name]['type'],
            'config': {**new_pipe.models[model_name]['config'], **search.best_params_},
            'fitted': True
        }
        
        new_pipe.hyperparameter_tuning[tuning_name] = tuning_results
        new_pipe.current_analysis = f'hyperparameter_tuning_{tuning_name}'
        
        return new_pipe
    
    return _tune_hyperparameters


# Visualization Functions
def plot_confusion_matrix(
    prediction_name: str,
    figsize: Tuple[int, int] = (8, 6),
    normalize: Optional[str] = None
):
    """
    Plot confusion matrix
    
    Parameters:
    -----------
    prediction_name : str
        Name of predictions to plot
    figsize : Tuple[int, int]
        Figure size
    normalize : Optional[str]
        Normalization method ('true', 'pred', 'all', None)
        
    Returns:
    --------
    Callable
        Function that plots confusion matrix from a LogisticRegressionPipe
    """
    def _plot_confusion_matrix(pipe):
        if prediction_name not in pipe.evaluation_metrics:
            raise ValueError(f"Evaluation metrics for '{prediction_name}' not found.")
        
        cm = pipe.evaluation_metrics[prediction_name]['confusion_matrix']
        
        if normalize:
            if normalize == 'true':
                cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            elif normalize == 'pred':
                cm = cm.astype('float') / cm.sum(axis=0)
            elif normalize == 'all':
                cm = cm.astype('float') / cm.sum()
        
        plt.figure(figsize=figsize)
        sns.heatmap(cm, annot=True, fmt='.2f' if normalize else 'd', cmap='Blues')
        plt.title(f'Confusion Matrix - {prediction_name}')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_confusion_matrix


def plot_feature_importance(
    importance_name: str,
    top_k: int = 20,
    figsize: Tuple[int, int] = (10, 8)
):
    """
    Plot feature importance
    
    Parameters:
    -----------
    importance_name : str
        Name of importance results to plot
    top_k : int
        Number of top features to display
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots feature importance from a LogisticRegressionPipe
    """
    def _plot_feature_importance(pipe):
        if importance_name not in pipe.feature_importance:
            raise ValueError(f"Feature importance '{importance_name}' not found.")
        
        importance_data = pipe.feature_importance[importance_name]['importance_data']
        top_features = importance_data.head(top_k)
        
        plt.figure(figsize=figsize)
        plt.barh(range(len(top_features)), top_features['importance'])
        plt.yticks(range(len(top_features)), top_features['feature'])
        plt.xlabel('Importance')
        plt.title(f'Top {top_k} Feature Importance - {importance_name}')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_feature_importance


def plot_roc_curve(
    prediction_name: str,
    figsize: Tuple[int, int] = (8, 6)
):
    """
    Plot ROC curve
    
    Parameters:
    -----------
    prediction_name : str
        Name of predictions to plot
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots ROC curve from a LogisticRegressionPipe
    """
    def _plot_roc_curve(pipe):
        if prediction_name not in pipe.predictions:
            raise ValueError(f"Predictions '{prediction_name}' not found.")
        
        pred_data = pipe.predictions[prediction_name]
        y_true = pred_data['y_true']
        y_proba = pred_data.get('y_proba')
        
        if y_proba is None:
            raise ValueError("Probabilities not available for ROC curve.")
        
        plt.figure(figsize=figsize)
        
        if len(np.unique(y_true)) == 2:  # Binary classification
            fpr, tpr, _ = roc_curve(y_true, y_proba[:, 1])
            auc_score = roc_auc_score(y_true, y_proba[:, 1])
            plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc_score:.3f})')
        else:  # Multi-class
            # Plot ROC curve for each class
            for i in range(y_proba.shape[1]):
                y_true_binary = (y_true == i).astype(int)
                fpr, tpr, _ = roc_curve(y_true_binary, y_proba[:, i])
                auc_score = roc_auc_score(y_true_binary, y_proba[:, i])
                plt.plot(fpr, tpr, label=f'Class {i} (AUC = {auc_score:.3f})')
        
        plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title(f'ROC Curve - {prediction_name}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_roc_curve


# Model Management Functions
def save_model(
    model_name: str,
    filepath: Optional[str] = None,
    include_preprocessing: bool = True
):
    """
    Save logistic regression model with preprocessing pipeline
    
    Parameters:
    -----------
    model_name : str
        Name of the model to save
    filepath : Optional[str]
        Path to save the model
    include_preprocessing : bool
        Whether to include scalers and selectors
        
    Returns:
    --------
    Callable
        Function that saves model from a LogisticRegressionPipe
    """
    def _save_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            save_path = f"{model_name}_{timestamp}.joblib"
        else:
            save_path = filepath
        
        # Package model with metadata
        model_package = {
            'model': pipe.models[model_name]['model'],
            'model_type': pipe.models[model_name]['type'],
            'config': pipe.models[model_name]['config'],
            'feature_columns': pipe.feature_columns,
            'target_column': pipe.target_column,
            'class_mapping': pipe.class_mapping,
            'fitted': pipe.models[model_name]['fitted']
        }
        
        if include_preprocessing:
            model_package.update({
                'scalers': pipe.scalers,
                'feature_selectors': pipe.feature_selectors
            })
        
        # Include evaluation metrics if available
        if model_name in pipe.evaluation_metrics:
            model_package['evaluation_metrics'] = pipe.evaluation_metrics[model_name]
        
        # Include feature importance if available
        if model_name in pipe.feature_importance:
            model_package['feature_importance'] = pipe.feature_importance[model_name]
        
        joblib.dump(model_package, save_path)
        print(f"Logistic regression model saved to: {save_path}")
        
        return pipe
    
    return _save_model


def load_model(
    filepath: str,
    model_name: str = 'loaded_model'
):
    """
    Load a previously saved logistic regression model
    
    Parameters:
    -----------
    filepath : str
        Path to the saved model file
    model_name : str
        Name for the loaded model
        
    Returns:
    --------
    Callable
        Function that loads model into a LogisticRegressionPipe
    """
    def _load_model(pipe):
        try:
            model_package = joblib.load(filepath)
            
            new_pipe = pipe.copy()
            
            # Restore model
            new_pipe.models[model_name] = {
                'model': model_package['model'],
                'type': model_package['model_type'],
                'config': model_package['config'],
                'fitted': model_package.get('fitted', True)
            }
            
            # Restore pipeline configuration
            if 'feature_columns' in model_package:
                new_pipe.feature_columns = model_package['feature_columns']
            
            if 'target_column' in model_package:
                new_pipe.target_column = model_package['target_column']
            
            if 'class_mapping' in model_package:
                new_pipe.class_mapping = model_package['class_mapping']
            
            # Restore preprocessing components
            if 'scalers' in model_package:
                new_pipe.scalers = model_package['scalers']
            
            if 'feature_selectors' in model_package:
                new_pipe.feature_selectors = model_package['feature_selectors']
            
            # Restore evaluation metrics
            if 'evaluation_metrics' in model_package:
                new_pipe.evaluation_metrics[model_name] = model_package['evaluation_metrics']
            
            # Restore feature importance
            if 'feature_importance' in model_package:
                new_pipe.feature_importance[model_name] = model_package['feature_importance']
            
            new_pipe.current_analysis = f'loaded_model_{model_name}'
            
            print(f"Successfully loaded logistic regression model from: {filepath}")
            print(f"Model type: {model_package['model_type']}")
            print(f"Number of features: {len(model_package.get('feature_columns', []))}")
            print(f"Target column: {model_package.get('target_column', 'unknown')}")
            
            return new_pipe
            
        except Exception as e:
            raise ValueError(f"Failed to load model from {filepath}: {str(e)}")
    
    return _load_model


def print_model_summary(
    model_name: str
):
    """
    Print comprehensive model summary
    
    Parameters:
    -----------
    model_name : str
        Name of the model to summarize
        
    Returns:
    --------
    Callable
        Function that prints model summary from a LogisticRegressionPipe
    """
    def _print_model_summary(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        print(f"\n=== Logistic Regression Summary for {model_name} ===")
        
        # Model configuration
        config = pipe.models[model_name]['config']
        print(f"Model type: {pipe.models[model_name]['type']}")
        print(f"Regularization: {config.get('penalty', 'unknown')}")
        print(f"C (inverse regularization): {config.get('C', 'unknown')}")
        print(f"Solver: {config.get('solver', 'unknown')}")
        print(f"Fitted: {pipe.models[model_name]['fitted']}")
        
        # Data information
        print(f"\nData Information:")
        print(f"Number of features: {len(pipe.feature_columns)}")
        print(f"Target column: {pipe.target_column}")
        if pipe.class_mapping:
            print(f"Classes: {list(pipe.class_mapping.values())}")
        
        # Evaluation metrics
        if model_name in pipe.evaluation_metrics:
            metrics = pipe.evaluation_metrics[model_name]
            print(f"\nEvaluation Metrics:")
            if 'accuracy' in metrics:
                print(f"  Accuracy: {metrics['accuracy']:.4f}")
            if 'precision' in metrics:
                print(f"  Precision: {metrics['precision']:.4f}")
            if 'recall' in metrics:
                print(f"  Recall: {metrics['recall']:.4f}")
            if 'f1_score' in metrics:
                print(f"  F1 Score: {metrics['f1_score']:.4f}")
            if 'auc_score' in metrics:
                print(f"  AUC Score: {metrics['auc_score']:.4f}")
        
        # Feature importance
        if model_name in pipe.feature_importance:
            importance_data = pipe.feature_importance[model_name]['importance_data']
            print(f"\nTop 5 Most Important Features:")
            for i, row in importance_data.head().iterrows():
                print(f"  {row['feature']}: {row['importance']:.4f}")
        
        # Cross-validation results
        cv_results = [cv for cv_name, cv in pipe.cross_validation.items() 
                     if cv.get('model_used') == model_name]
        if cv_results:
            cv = cv_results[0]
            print(f"\nCross-Validation Results:")
            print(f"  Mean Score: {cv['mean_score']:.4f} ± {cv['std_score']:.4f}")
            print(f"  Scoring: {cv['scoring']}")
        
        return pipe
    
    return _print_model_summary