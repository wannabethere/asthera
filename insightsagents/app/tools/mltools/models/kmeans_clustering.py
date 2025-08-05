import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.feature_selection import VarianceThreshold
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import joblib
import warnings
from datetime import datetime
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
import itertools
from ..base_pipe import BasePipe


class KMeansPipe(BasePipe):
    """
    A pipeline-style K-means clustering tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for K-means clustering analysis"""
        self.original_data = None
        self.feature_columns = []
        self.models = {}
        self.cluster_assignments = {}
        self.cluster_profiles = {}
        self.evaluation_metrics = {}
        self.scalers = {}
        self.dimensionality_reducers = {}
        self.elbow_analysis = {}
        self.silhouette_analysis = {}
        self.current_analysis = None
        self.visualization_data = {}
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'original_data'):
            self.original_data = source_pipe.original_data.copy() if source_pipe.original_data is not None else None
        if hasattr(source_pipe, 'feature_columns'):
            self.feature_columns = source_pipe.feature_columns.copy()
        if hasattr(source_pipe, 'models'):
            self.models = source_pipe.models.copy()
        if hasattr(source_pipe, 'cluster_assignments'):
            self.cluster_assignments = source_pipe.cluster_assignments.copy()
        if hasattr(source_pipe, 'cluster_profiles'):
            self.cluster_profiles = source_pipe.cluster_profiles.copy()
        if hasattr(source_pipe, 'evaluation_metrics'):
            self.evaluation_metrics = source_pipe.evaluation_metrics.copy()
        if hasattr(source_pipe, 'scalers'):
            self.scalers = source_pipe.scalers.copy()
        if hasattr(source_pipe, 'dimensionality_reducers'):
            self.dimensionality_reducers = source_pipe.dimensionality_reducers.copy()
        if hasattr(source_pipe, 'elbow_analysis'):
            self.elbow_analysis = source_pipe.elbow_analysis.copy()
        if hasattr(source_pipe, 'silhouette_analysis'):
            self.silhouette_analysis = source_pipe.silhouette_analysis.copy()
        if hasattr(source_pipe, 'current_analysis'):
            self.current_analysis = source_pipe.current_analysis
        if hasattr(source_pipe, 'visualization_data'):
            self.visualization_data = source_pipe.visualization_data.copy()
    
    def to_df(self, **kwargs) -> pd.DataFrame:
        """
        Convert the K-means clustering analysis results to a DataFrame.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments:
            - include_clusters: bool, whether to include cluster assignments (default: True)
            - include_features: bool, whether to include feature columns (default: True)
            - include_metrics: bool, whether to include evaluation metrics (default: False)
            - model_name: str, specific model to include results for (default: None, includes all)
            
        Returns:
        --------
        pd.DataFrame
            DataFrame representation of the analysis results
            
        Raises:
        -------
        ValueError
            If no analysis has been performed
        """
        if self.data is None:
            raise ValueError("No data available. Run analysis first.")
        
        # Get parameters
        include_clusters = kwargs.get('include_clusters', True)
        include_features = kwargs.get('include_features', True)
        include_metrics = kwargs.get('include_metrics', False)
        model_name = kwargs.get('model_name', None)
        
        # Start with the original data
        result_df = self.data.copy()
        
        # Add cluster assignments if requested
        if include_clusters and self.cluster_assignments:
            if model_name:
                if model_name in self.cluster_assignments:
                    cluster_col = self.cluster_assignments[model_name]['cluster_column']
                    if cluster_col in result_df.columns:
                        # Already included in data
                        pass
                    else:
                        result_df[cluster_col] = self.cluster_assignments[model_name]['labels']
            else:
                # Add all cluster assignments
                for name, assignment in self.cluster_assignments.items():
                    cluster_col = assignment['cluster_column']
                    if cluster_col not in result_df.columns:
                        result_df[cluster_col] = assignment['labels']
        
        # Add evaluation metrics if requested
        if include_metrics and self.evaluation_metrics:
            metrics_data = {}
            if model_name:
                if model_name in self.evaluation_metrics:
                    metrics = self.evaluation_metrics[model_name]
                    for metric_name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            metrics_data[f'{model_name}_{metric_name}'] = [value] * len(result_df)
            else:
                # Add all metrics
                for name, metrics in self.evaluation_metrics.items():
                    for metric_name, value in metrics.items():
                        if isinstance(value, (int, float)):
                            metrics_data[f'{name}_{metric_name}'] = [value] * len(result_df)
            
            # Add metrics as columns
            for col_name, values in metrics_data.items():
                result_df[col_name] = values
        
        # Filter feature columns if requested
        if not include_features and self.feature_columns:
            # Remove feature columns but keep cluster assignments and metrics
            feature_cols_to_remove = [col for col in self.feature_columns if col in result_df.columns]
            result_df = result_df.drop(columns=feature_cols_to_remove)
        
        return result_df
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the K-means clustering analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in K-means clustering pipe)
            
        Returns:
        --------
        dict
            Summary of the K-means clustering analysis results
        """
        if not any([self.models, self.cluster_assignments, self.evaluation_metrics]):
            return {"error": "No K-means clustering analysis has been performed"}
        
        # Count analyses by type
        analysis_types = {
            'models': len(self.models),
            'cluster_assignments': len(self.cluster_assignments),
            'evaluation_metrics': len(self.evaluation_metrics),
            'cluster_profiles': len(self.cluster_profiles),
            'scalers': len(self.scalers),
            'dimensionality_reducers': len(self.dimensionality_reducers),
            'elbow_analysis': len(self.elbow_analysis),
            'silhouette_analysis': len(self.silhouette_analysis)
        }
        
        # Get model information
        models_info = {}
        for name, model_info in self.models.items():
            models_info[name] = {
                "type": model_info.get('type', 'unknown'),
                "n_clusters": model_info.get('config', {}).get('n_clusters', 'unknown'),
                "algorithm": model_info.get('config', {}).get('algorithm', 'unknown')
            }
        
        # Get evaluation metrics summary
        metrics_summary = {}
        for name, metrics in self.evaluation_metrics.items():
            metrics_summary[name] = {
                "silhouette_score": metrics.get('silhouette_score', None),
                "calinski_harabasz_score": metrics.get('calinski_harabasz_score', None),
                "davies_bouldin_score": metrics.get('davies_bouldin_score', None),
                "inertia": metrics.get('inertia', None),
                "n_clusters": metrics.get('n_clusters', None)
            }
        
        return {
            "total_analyses": sum(analysis_types.values()),
            "feature_columns": self.feature_columns,
            "analysis_types": analysis_types,
            "current_analysis": self.current_analysis,
            "available_models": list(self.models.keys()),
            "available_cluster_assignments": list(self.cluster_assignments.keys()),
            "available_evaluation_metrics": list(self.evaluation_metrics.keys()),
            "available_cluster_profiles": list(self.cluster_profiles.keys()),
            "available_scalers": list(self.scalers.keys()),
            "available_dimensionality_reducers": list(self.dimensionality_reducers.keys()),
            "available_elbow_analysis": list(self.elbow_analysis.keys()),
            "available_silhouette_analysis": list(self.silhouette_analysis.keys()),
            "models_info": models_info,
            "evaluation_metrics_summary": metrics_summary,
            "cluster_assignments_info": {name: {"n_clusters": len(np.unique(assignment.get('labels', [])))} 
                                       for name, assignment in self.cluster_assignments.items()},
            "scalers_info": {name: {"type": type(scaler).__name__} 
                           for name, scaler in self.scalers.items()},
            "dimensionality_reducers_info": {name: {"method": reducer.get('method', 'unknown'), 
                                                  "n_components": reducer.get('n_components', 'unknown')} 
                                           for name, reducer in self.dimensionality_reducers.items()}
        }


# Data Preparation Functions
def prepare_clustering_data(
    feature_columns: List[str],
    scaling_method: str = 'standard',
    handle_missing: str = 'drop',
    remove_outliers: bool = False,
    outlier_method: str = 'iqr',
    outlier_threshold: float = 3.0
):
    """
    Prepare data for K-means clustering
    
    Parameters:
    -----------
    feature_columns : List[str]
        Columns to use for clustering
    scaling_method : str
        Scaling method ('standard', 'minmax', 'robust', 'none')
    handle_missing : str
        How to handle missing values ('drop', 'mean', 'median', 'mode')
    remove_outliers : bool
        Whether to remove outliers
    outlier_method : str
        Outlier detection method ('iqr', 'zscore')
    outlier_threshold : float
        Threshold for outlier removal
        
    Returns:
    --------
    Callable
        Function that prepares clustering data from a KMeansPipe
    """
    def _prepare_clustering_data(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()
        
        # Validate feature columns exist
        missing_cols = [col for col in feature_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Columns not found in data: {missing_cols}")
        
        # Select feature columns and ensure they're numeric
        feature_data = df[feature_columns].copy()
        
        # Convert to numeric, coercing errors
        for col in feature_columns:
            feature_data[col] = pd.to_numeric(feature_data[col], errors='coerce')
        
        # Handle missing values
        if handle_missing == 'drop':
            feature_data = feature_data.dropna()
            df = df.loc[feature_data.index]
        elif handle_missing == 'mean':
            feature_data = feature_data.fillna(feature_data.mean())
        elif handle_missing == 'median':
            feature_data = feature_data.fillna(feature_data.median())
        elif handle_missing == 'mode':
            for col in feature_columns:
                mode_val = feature_data[col].mode()
                if not mode_val.empty:
                    feature_data[col] = feature_data[col].fillna(mode_val[0])
        
        # Remove outliers if requested
        if remove_outliers:
            # Filter out boolean columns for outlier detection
            numeric_columns = feature_data.select_dtypes(include=[np.number]).columns.tolist()
            boolean_columns = feature_data.select_dtypes(include=[bool]).columns.tolist()
            
            if len(numeric_columns) == 0:
                print("Warning: No numeric columns found for outlier detection. Skipping outlier removal.")
            else:
                numeric_data = feature_data[numeric_columns]
                
                if outlier_method == 'iqr':
                    Q1 = numeric_data.quantile(0.25)
                    Q3 = numeric_data.quantile(0.75)
                    IQR = Q3 - Q1
                    outlier_mask = ~((numeric_data < (Q1 - 1.5 * IQR)) | (numeric_data > (Q3 + 1.5 * IQR))).any(axis=1)
                elif outlier_method == 'zscore':
                    z_scores = np.abs((numeric_data - numeric_data.mean()) / numeric_data.std())
                    outlier_mask = (z_scores < outlier_threshold).all(axis=1)
                else:
                    raise ValueError(f"Unknown outlier method: {outlier_method}")
                
                feature_data = feature_data[outlier_mask]
                df = df.loc[feature_data.index]
                
                if boolean_columns:
                    print(f"Note: Boolean columns {boolean_columns} were excluded from outlier detection.")
        
        # Scale features
        if scaling_method == 'standard':
            scaler = StandardScaler()
        elif scaling_method == 'minmax':
            scaler = MinMaxScaler()
        elif scaling_method == 'robust':
            scaler = RobustScaler()
        elif scaling_method == 'none':
            scaler = None
        else:
            raise ValueError(f"Unknown scaling method: {scaling_method}")
        
        # Separate numeric and boolean columns for scaling
        numeric_columns = feature_data.select_dtypes(include=[np.number]).columns.tolist()
        boolean_columns = feature_data.select_dtypes(include=[bool]).columns.tolist()
        
        if scaler and len(numeric_columns) > 0:
            # Scale numeric columns
            numeric_data = feature_data[numeric_columns]
            scaled_numeric = scaler.fit_transform(numeric_data)
            scaled_df = pd.DataFrame(scaled_numeric, columns=numeric_columns, index=feature_data.index)
            new_pipe.scalers['features'] = scaler
            
            # Add boolean columns back without scaling
            if boolean_columns:
                scaled_df[boolean_columns] = feature_data[boolean_columns]
        else:
            scaled_df = feature_data
        
        # Update data and feature columns
        new_pipe.data = df.copy()
        new_pipe.data[feature_columns] = scaled_df
        new_pipe.feature_columns = feature_columns
        new_pipe.current_analysis = 'data_preparation'
        
        return new_pipe
    
    return _prepare_clustering_data


def engineer_clustering_features(
    interaction_features: bool = True,
    polynomial_features: Optional[List[str]] = None,
    ratio_features: Optional[List[Tuple[str, str]]] = None,
    aggregation_features: Optional[Dict[str, List[str]]] = None,
    binning_features: Optional[Dict[str, int]] = None
):
    """
    Engineer features specifically for clustering
    
    Parameters:
    -----------
    interaction_features : bool
        Whether to create pairwise interaction features
    polynomial_features : Optional[List[str]]
        Features to create polynomial terms for
    ratio_features : Optional[List[Tuple[str, str]]]
        Pairs of features to create ratios
    aggregation_features : Optional[Dict[str, List[str]]]
        Group-by aggregations for categorical columns
    binning_features : Optional[Dict[str, int]]
        Features to bin with number of bins
        
    Returns:
    --------
    Callable
        Function that engineers clustering features from a KMeansPipe
    """
    def _engineer_clustering_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data.copy()
        new_features = []
        
        # Create interaction features
        if interaction_features and len(new_pipe.feature_columns) >= 2:
            for i, col1 in enumerate(new_pipe.feature_columns):
                for col2 in new_pipe.feature_columns[i+1:]:
                    if pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2]):
                        interaction_name = f'{col1}_x_{col2}'
                        df[interaction_name] = df[col1] * df[col2]
                        new_features.append(interaction_name)
        
        # Create polynomial features
        if polynomial_features:
            for col in polynomial_features:
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    df[f'{col}_squared'] = df[col] ** 2
                    df[f'{col}_cubed'] = df[col] ** 3
                    df[f'{col}_sqrt'] = np.sqrt(np.abs(df[col]))
                    new_features.extend([f'{col}_squared', f'{col}_cubed', f'{col}_sqrt'])
        
        # Create ratio features
        if ratio_features:
            ratio_data = {}
            for col1, col2 in ratio_features:
                if col1 in df.columns and col2 in df.columns:
                    if pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2]):
                        ratio_name = f'{col1}_div_{col2}'
                        ratio_data[ratio_name] = df[col1] / (df[col2] + 1e-8)  # Avoid division by zero
                        new_features.append(ratio_name)
            
            # Add all ratio features at once to avoid fragmentation
            if ratio_data:
                ratio_df = pd.DataFrame(ratio_data, index=df.index)
                df = pd.concat([df, ratio_df], axis=1)
        
        # Create aggregation features
        if aggregation_features:
            agg_data = {}
            for group_col, agg_cols in aggregation_features.items():
                if group_col in df.columns:
                    for agg_col in agg_cols:
                        if agg_col in df.columns and pd.api.types.is_numeric_dtype(df[agg_col]):
                            group_stats = df.groupby(group_col)[agg_col].agg(['mean', 'std', 'min', 'max'])
                            # Create new columns for each aggregation
                            for stat in ['mean', 'std', 'min', 'max']:
                                col_name = f'{agg_col}_by_{group_col}_{stat}'
                                agg_data[col_name] = df[group_col].map(group_stats[stat])
                                new_features.append(col_name)
            
            # Add all aggregation features at once
            if agg_data:
                agg_df = pd.DataFrame(agg_data, index=df.index)
                df = pd.concat([df, agg_df], axis=1)
        
        # Create binning features
        if binning_features:
            bin_data = {}
            for col, n_bins in binning_features.items():
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    binned_name = f'{col}_binned'
                    bin_data[binned_name] = pd.cut(df[col], bins=n_bins, labels=False)
                    new_features.append(binned_name)
            
            # Add all binning features at once
            if bin_data:
                bin_df = pd.DataFrame(bin_data, index=df.index)
                df = pd.concat([df, bin_df], axis=1)
        
        # Update feature columns and data
        new_pipe.data = df
        new_pipe.feature_columns.extend(new_features)
        new_pipe.current_analysis = 'feature_engineering'
        
        return new_pipe
    
    return _engineer_clustering_features


def reduce_dimensions(
    method: str = 'pca',
    n_components: int = 2,
    random_state: int = 42,
    reducer_name: str = 'default'
):
    """
    Apply dimensionality reduction for visualization and clustering
    
    Parameters:
    -----------
    method : str
        Reduction method ('pca', 'tsne')
    n_components : int
        Number of dimensions to reduce to
    random_state : int
        Random seed
    reducer_name : str
        Name to store the reducer under
        
    Returns:
    --------
    Callable
        Function that reduces dimensions from a KMeansPipe
    """
    def _reduce_dimensions(pipe):
        if pipe.data is None or not pipe.feature_columns:
            raise ValueError("Data and features must be available.")
        
        new_pipe = pipe.copy()
        X = new_pipe.data[new_pipe.feature_columns]
        
        if method == 'pca':
            reducer = PCA(n_components=n_components, random_state=random_state)
        elif method == 'tsne':
            reducer = TSNE(n_components=n_components, random_state=random_state, perplexity=min(30, len(X)-1))
        else:
            raise ValueError(f"Unknown reduction method: {method}")
        
        reduced_data = reducer.fit_transform(X)
        
        # Create column names for reduced dimensions
        dim_columns = [f'{reducer_name}_dim_{i+1}' for i in range(n_components)]
        
        # Add reduced dimensions to dataframe
        for i, col in enumerate(dim_columns):
            new_pipe.data[col] = reduced_data[:, i]
        
        new_pipe.dimensionality_reducers[reducer_name] = {
            'reducer': reducer,
            'method': method,
            'n_components': n_components,
            'dimension_columns': dim_columns
        }
        
        new_pipe.current_analysis = f'dimensionality_reduction_{reducer_name}'
        
        return new_pipe
    
    return _reduce_dimensions


# K-means Configuration and Training Functions
def configure_kmeans(
    n_clusters: int = 8,
    init: str = 'k-means++',
    n_init: int = 10,
    max_iter: int = 300,
    tol: float = 1e-4,
    random_state: int = 42,
    algorithm: str = 'lloyd',
    model_name: str = 'kmeans_model'
):
    """
    Configure K-means clustering algorithm
    
    Parameters:
    -----------
    n_clusters : int
        Number of clusters
    init : str
        Initialization method ('k-means++', 'random')
    n_init : int
        Number of random initializations
    max_iter : int
        Maximum iterations
    tol : float
        Tolerance for convergence
    random_state : int
        Random seed
    algorithm : str
        Algorithm to use ('lloyd', 'elkan')
    model_name : str
        Name for the model
        
    Returns:
    --------
    Callable
        Function that configures K-means in a KMeansPipe
    """
    def _configure_kmeans(pipe):
        new_pipe = pipe.copy()
        
        model = KMeans(
            n_clusters=n_clusters,
            init=init,
            n_init=n_init,
            max_iter=max_iter,
            tol=tol,
            random_state=random_state,
            algorithm=algorithm
        )
        
        new_pipe.models[model_name] = {
            'model': model,
            'type': 'kmeans',
            'config': {
                'n_clusters': n_clusters,
                'init': init,
                'n_init': n_init,
                'max_iter': max_iter,
                'tol': tol,
                'algorithm': algorithm
            }
        }
        
        new_pipe.current_analysis = f'configure_{model_name}'
        
        return new_pipe
    
    return _configure_kmeans


def configure_minibatch_kmeans(
    n_clusters: int = 8,
    init: str = 'k-means++',
    max_iter: int = 100,
    batch_size: int = 1024,
    tol: float = 0.0,
    max_no_improvement: int = 10,
    random_state: int = 42,
    model_name: str = 'minibatch_kmeans_model'
):
    """
    Configure MiniBatch K-means for large datasets
    
    Parameters:
    -----------
    n_clusters : int
        Number of clusters
    init : str
        Initialization method
    max_iter : int
        Maximum iterations
    batch_size : int
        Size of mini-batches
    tol : float
        Tolerance for convergence
    max_no_improvement : int
        Maximum iterations without improvement
    random_state : int
        Random seed
    model_name : str
        Name for the model
        
    Returns:
    --------
    Callable
        Function that configures MiniBatch K-means in a KMeansPipe
    """
    def _configure_minibatch_kmeans(pipe):
        new_pipe = pipe.copy()
        
        model = MiniBatchKMeans(
            n_clusters=n_clusters,
            init=init,
            max_iter=max_iter,
            batch_size=batch_size,
            tol=tol,
            max_no_improvement=max_no_improvement,
            random_state=random_state
        )
        
        new_pipe.models[model_name] = {
            'model': model,
            'type': 'minibatch_kmeans',
            'config': {
                'n_clusters': n_clusters,
                'init': init,
                'max_iter': max_iter,
                'batch_size': batch_size,
                'tol': tol,
                'max_no_improvement': max_no_improvement
            }
        }
        
        new_pipe.current_analysis = f'configure_{model_name}'
        
        return new_pipe
    
    return _configure_minibatch_kmeans


def fit_kmeans(
    model_name: str,
    feature_subset: Optional[List[str]] = None
):
    """
    Fit K-means clustering model
    
    Parameters:
    -----------
    model_name : str
        Name of the model to fit
    feature_subset : Optional[List[str]]
        Subset of features to use for clustering
        
    Returns:
    --------
    Callable
        Function that fits K-means from a KMeansPipe
    """
    def _fit_kmeans(pipe):
        if pipe.data is None or not pipe.feature_columns:
            raise ValueError("Data and features must be available.")
        
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        new_pipe = pipe.copy()
        model_info = new_pipe.models[model_name]
        model = model_info['model']
        
        # Select features for clustering
        if feature_subset:
            clustering_features = feature_subset
        else:
            clustering_features = new_pipe.feature_columns
        
        X = new_pipe.data[clustering_features]
        
        # Fit the model
        model.fit(X)
        
        # Store cluster assignments
        cluster_labels = model.predict(X)
        new_pipe.data[f'{model_name}_cluster'] = cluster_labels
        
        new_pipe.cluster_assignments[model_name] = {
            'labels': cluster_labels,
            'features_used': clustering_features,
            'cluster_column': f'{model_name}_cluster'
        }
        
        new_pipe.current_analysis = f'fit_{model_name}'
        
        return new_pipe
    
    return _fit_kmeans


# Analysis and Evaluation Functions
def evaluate_clustering(
    model_name: str,
    metrics: List[str] = ['silhouette', 'calinski_harabasz', 'davies_bouldin', 'inertia']
):
    """
    Evaluate clustering performance
    
    Parameters:
    -----------
    model_name : str
        Name of the fitted model
    metrics : List[str]
        Metrics to calculate
        
    Returns:
    --------
    Callable
        Function that evaluates clustering from a KMeansPipe
    """
    def _evaluate_clustering(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        if model_name not in pipe.cluster_assignments:
            raise ValueError(f"Model '{model_name}' has not been fitted.")
        
        new_pipe = pipe.copy()
        model = new_pipe.models[model_name]['model']
        assignment_info = new_pipe.cluster_assignments[model_name]
        
        X = new_pipe.data[assignment_info['features_used']]
        labels = assignment_info['labels']
        
        evaluation_results = {}
        
        # Calculate requested metrics
        if 'silhouette' in metrics and len(np.unique(labels)) > 1:
            evaluation_results['silhouette_score'] = silhouette_score(X, labels)
        
        if 'calinski_harabasz' in metrics and len(np.unique(labels)) > 1:
            evaluation_results['calinski_harabasz_score'] = calinski_harabasz_score(X, labels)
        
        if 'davies_bouldin' in metrics and len(np.unique(labels)) > 1:
            evaluation_results['davies_bouldin_score'] = davies_bouldin_score(X, labels)
        
        if 'inertia' in metrics:
            evaluation_results['inertia'] = model.inertia_
        
        # Add cluster statistics
        evaluation_results['n_clusters'] = len(np.unique(labels))
        evaluation_results['cluster_sizes'] = pd.Series(labels).value_counts().sort_index().values
        evaluation_results['largest_cluster_size'] = max(evaluation_results['cluster_sizes'])
        evaluation_results['smallest_cluster_size'] = min(evaluation_results['cluster_sizes'])
        
        new_pipe.evaluation_metrics[model_name] = evaluation_results
        new_pipe.current_analysis = f'evaluate_{model_name}'
        
        return new_pipe
    
    return _evaluate_clustering


def profile_clusters(
    model_name: str,
    profile_columns: Optional[List[str]] = None,
    include_categorical: bool = True
):
    """
    Create detailed cluster profiles
    
    Parameters:
    -----------
    model_name : str
        Name of the fitted model
    profile_columns : Optional[List[str]]
        Columns to include in profiling
    include_categorical : bool
        Whether to profile categorical variables
        
    Returns:
    --------
    Callable
        Function that profiles clusters from a KMeansPipe
    """
    def _profile_clusters(pipe):
        if model_name not in pipe.cluster_assignments:
            raise ValueError(f"Model '{model_name}' has not been fitted.")
        
        new_pipe = pipe.copy()
        cluster_col = new_pipe.cluster_assignments[model_name]['cluster_column']
        
        # Determine columns to profile
        if profile_columns:
            columns_to_profile = profile_columns
        else:
            columns_to_profile = new_pipe.feature_columns
        
        profiles = {}
        
        # Numerical profiles
        numerical_cols = [col for col in columns_to_profile 
                         if col in new_pipe.data.columns and 
                         pd.api.types.is_numeric_dtype(new_pipe.data[col])]
        
        if numerical_cols:
            profiles['numerical'] = new_pipe.data.groupby(cluster_col)[numerical_cols].agg([
                'count', 'mean', 'std', 'min', 'median', 'max'
            ])
        
        # Categorical profiles
        if include_categorical:
            categorical_cols = [col for col in columns_to_profile 
                               if col in new_pipe.data.columns and 
                               not pd.api.types.is_numeric_dtype(new_pipe.data[col])]
            
            profiles['categorical'] = {}
            for col in categorical_cols:
                profiles['categorical'][col] = pd.crosstab(
                    new_pipe.data[cluster_col], 
                    new_pipe.data[col], 
                    normalize='index'
                ) * 100  # Convert to percentages
        
        # Cluster sizes
        profiles['cluster_sizes'] = new_pipe.data[cluster_col].value_counts().sort_index()
        
        # Cluster centroids
        if model_name in new_pipe.models:
            model = new_pipe.models[model_name]['model']
            features_used = new_pipe.cluster_assignments[model_name]['features_used']
            centroids_df = pd.DataFrame(
                model.cluster_centers_,
                columns=features_used,
                index=[f'Cluster_{i}' for i in range(len(model.cluster_centers_))]
            )
            profiles['centroids'] = centroids_df
        
        new_pipe.cluster_profiles[model_name] = profiles
        new_pipe.current_analysis = f'profile_{model_name}'
        
        return new_pipe
    
    return _profile_clusters


def find_optimal_k(
    k_range: Tuple[int, int] = (2, 15),
    method: str = 'elbow',
    n_init: int = 10,
    random_state: int = 42,
    analysis_name: str = 'optimal_k'
):
    """
    Find optimal number of clusters using elbow method or silhouette analysis
    
    Parameters:
    -----------
    k_range : Tuple[int, int]
        Range of k values to test
    method : str
        Method to use ('elbow', 'silhouette', 'both')
    n_init : int
        Number of initializations for each k
    random_state : int
        Random seed
    analysis_name : str
        Name for the analysis
        
    Returns:
    --------
    Callable
        Function that finds optimal k from a KMeansPipe
    """
    def _find_optimal_k(pipe):
        if pipe.data is None or not pipe.feature_columns:
            raise ValueError("Data and features must be available.")
        
        new_pipe = pipe.copy()
        X = new_pipe.data[new_pipe.feature_columns]
        
        k_min, k_max = k_range
        k_values = list(range(k_min, k_max + 1))
        
        results = {
            'k_values': k_values,
            'inertias': [],
            'silhouette_scores': []
        }
        
        for k in k_values:
            # Fit K-means with k clusters
            kmeans = KMeans(n_clusters=k, n_init=n_init, random_state=random_state)
            cluster_labels = kmeans.fit_predict(X)
            
            # Calculate inertia (for elbow method)
            results['inertias'].append(kmeans.inertia_)
            
            # Calculate silhouette score (if k > 1)
            if k > 1:
                silhouette_avg = silhouette_score(X, cluster_labels)
                results['silhouette_scores'].append(silhouette_avg)
            else:
                results['silhouette_scores'].append(0)  # Silhouette undefined for k=1
        
        # Find optimal k
        if method in ['elbow', 'both']:
            # Calculate elbow using the "kneedle" method (simplified)
            inertias = np.array(results['inertias'])
            # Find the point with maximum distance to the line connecting first and last points
            n_points = len(inertias)
            line_start = np.array([0, inertias[0]])
            line_end = np.array([n_points-1, inertias[-1]])
            
            distances = []
            for i in range(n_points):
                point = np.array([i, inertias[i]])
                # Distance from point to line
                distance = np.abs(np.cross(line_end - line_start, line_start - point)) / np.linalg.norm(line_end - line_start)
                distances.append(distance)
            
            elbow_k = k_values[np.argmax(distances)]
            results['optimal_k_elbow'] = elbow_k
        
        if method in ['silhouette', 'both']:
            # Find k with highest silhouette score
            valid_silhouettes = [(k, score) for k, score in zip(k_values[1:], results['silhouette_scores'][1:]) if score > 0]
            if valid_silhouettes:
                optimal_k_silhouette = max(valid_silhouettes, key=lambda x: x[1])[0]
                results['optimal_k_silhouette'] = optimal_k_silhouette
        
        if method == 'elbow':
            new_pipe.elbow_analysis[analysis_name] = results
        elif method == 'silhouette':
            new_pipe.silhouette_analysis[analysis_name] = results
        else:  # both
            new_pipe.elbow_analysis[analysis_name] = results
            new_pipe.silhouette_analysis[analysis_name] = results
        
        new_pipe.current_analysis = f'optimal_k_{analysis_name}'
        
        return new_pipe
    
    return _find_optimal_k


# Visualization Functions
def plot_clusters_2d(
    model_name: str,
    x_feature: str,
    y_feature: str,
    figsize: Tuple[int, int] = (10, 8),
    show_centers: bool = True
):
    """
    Plot 2D cluster visualization
    
    Parameters:
    -----------
    model_name : str
        Name of the fitted model
    x_feature : str
        Feature for x-axis
    y_feature : str
        Feature for y-axis
    figsize : Tuple[int, int]
        Figure size
    show_centers : bool
        Whether to show cluster centers
        
    Returns:
    --------
    Callable
        Function that plots 2D clusters from a KMeansPipe
    """
    def _plot_clusters_2d(pipe):
        if model_name not in pipe.cluster_assignments:
            raise ValueError(f"Model '{model_name}' has not been fitted.")
        
        cluster_col = pipe.cluster_assignments[model_name]['cluster_column']
        df = pipe.data
        
        # Check if requested features exist in the data
        missing_features = []
        if x_feature not in df.columns:
            missing_features.append(x_feature)
        if y_feature not in df.columns:
            missing_features.append(y_feature)
        
        if missing_features:
            print(f"Warning: Features {missing_features} not found in data. Available columns: {list(df.columns)}")
            return pipe
        
        plt.figure(figsize=figsize)
        
        # Create scatter plot
        unique_clusters = sorted(df[cluster_col].unique())
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_clusters)))
        
        for i, cluster in enumerate(unique_clusters):
            cluster_data = df[df[cluster_col] == cluster]
            plt.scatter(
                cluster_data[x_feature], 
                cluster_data[y_feature],
                c=[colors[i]], 
                label=f'Cluster {cluster}',
                alpha=0.7,
                s=50
            )
        
        # Show cluster centers if available and requested
        if show_centers and model_name in pipe.models:
            model = pipe.models[model_name]['model']
            features_used = pipe.cluster_assignments[model_name]['features_used']
            
            if x_feature in features_used and y_feature in features_used:
                x_idx = features_used.index(x_feature)
                y_idx = features_used.index(y_feature)
                
                centers_x = model.cluster_centers_[:, x_idx]
                centers_y = model.cluster_centers_[:, y_idx]
                
                plt.scatter(centers_x, centers_y, 
                          marker='x', s=200, linewidths=3, c='red', label='Centroids')
        
        plt.xlabel(x_feature)
        plt.ylabel(y_feature)
        plt.title(f'Cluster Visualization: {model_name}')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_clusters_2d


def plot_cluster_profiles(
    model_name: str,
    profile_type: str = 'numerical',
    top_k_features: int = 10,
    figsize: Tuple[int, int] = (15, 10)
):
    """
    Plot cluster profile heatmaps
    
    Parameters:
    -----------
    model_name : str
        Name of the model with profiles
    profile_type : str
        Type of profile to plot ('numerical', 'categorical')
    top_k_features : int
        Number of top features to display
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots cluster profiles from a KMeansPipe
    """
    def _plot_cluster_profiles(pipe):
        if model_name not in pipe.cluster_profiles:
            raise ValueError(f"Cluster profiles for '{model_name}' not found. Run profile_clusters first.")
        
        profiles = pipe.cluster_profiles[model_name]
        
        if profile_type == 'numerical' and 'numerical' in profiles:
            # Plot numerical feature means
            numerical_profiles = profiles['numerical']
            
            if numerical_profiles is not None and not numerical_profiles.empty:
                # Handle multi-level columns from agg() operation
                if isinstance(numerical_profiles.columns, pd.MultiIndex):
                    # Extract mean values from multi-level columns
                    # The structure is typically (feature, agg_func) where agg_func is the first level
                    if 'mean' in numerical_profiles.columns.get_level_values(0):
                        means_data = numerical_profiles.xs('mean', level=0, axis=1).T
                    else:
                        # Fallback: use the first aggregation function available
                        first_agg = numerical_profiles.columns.get_level_values(0)[0]
                        means_data = numerical_profiles.xs(first_agg, level=0, axis=1).T
                else:
                    # Fallback for single-level columns
                    means_data = numerical_profiles.T
                
                # Check if we have valid data to plot
                if means_data is not None and not means_data.empty and len(means_data) > 0:
                    # Select top k features by variance across clusters
                    if len(means_data) > top_k_features:
                        feature_variance = means_data.var(axis=1)
                        top_features = feature_variance.nlargest(top_k_features).index
                        means_data = means_data.loc[top_features]
                    
                    plt.figure(figsize=figsize)
                    sns.heatmap(means_data, annot=True, cmap='RdYlBu_r', center=0, fmt='.2f')
                    plt.title(f'Cluster Profile Heatmap - {model_name}')
                    plt.ylabel('Features')
                    plt.xlabel('Clusters')
                    plt.tight_layout()
                    plt.show()
                else:
                    print(f"No valid numerical data to plot for {model_name}")
            else:
                print(f"No numerical profiles available for {model_name}")
            
        elif profile_type == 'categorical' and 'categorical' in profiles:
            # Plot categorical feature distributions
            cat_profiles = profiles['categorical']
            n_features = min(len(cat_profiles), top_k_features)
            
            if n_features > 0:
                fig, axes = plt.subplots(2, (n_features + 1) // 2, figsize=figsize)
                if n_features == 1:
                    axes = [axes]
                axes = axes.flatten() if n_features > 1 else axes
                
                for i, (feature, profile_data) in enumerate(list(cat_profiles.items())[:n_features]):
                    sns.heatmap(profile_data.T, annot=True, cmap='Blues', fmt='.1f', ax=axes[i])
                    axes[i].set_title(f'{feature} Distribution by Cluster')
                    axes[i].set_xlabel('Clusters')
                
                # Hide unused subplots
                for j in range(n_features, len(axes)):
                    axes[j].set_visible(False)
                
                plt.tight_layout()
                plt.show()
        
        return pipe
    
    return _plot_cluster_profiles


def plot_elbow_curve(
    analysis_name: str = 'optimal_k',
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot elbow curve for optimal k selection
    
    Parameters:
    -----------
    analysis_name : str
        Name of the elbow analysis
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots elbow curve from a KMeansPipe
    """
    def _plot_elbow_curve(pipe):
        if analysis_name not in pipe.elbow_analysis:
            raise ValueError(f"Elbow analysis '{analysis_name}' not found. Run find_optimal_k first.")
        
        results = pipe.elbow_analysis[analysis_name]
        
        plt.figure(figsize=figsize)
        plt.plot(results['k_values'], results['inertias'], 'bo-', linewidth=2, markersize=8)
        
        # Highlight optimal k if available
        if 'optimal_k_elbow' in results:
            optimal_k = results['optimal_k_elbow']
            optimal_inertia = results['inertias'][results['k_values'].index(optimal_k)]
            plt.axvline(x=optimal_k, color='red', linestyle='--', alpha=0.7)
            plt.plot(optimal_k, optimal_inertia, 'ro', markersize=12, label=f'Optimal k = {optimal_k}')
            plt.legend()
        
        plt.xlabel('Number of Clusters (k)')
        plt.ylabel('Inertia (Within-cluster Sum of Squares)')
        plt.title('Elbow Method for Optimal k')
        plt.grid(True, alpha=0.3)
        plt.xticks(results['k_values'])
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_elbow_curve


def plot_silhouette_scores(
    analysis_name: str = 'optimal_k',
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot silhouette scores for different k values
    
    Parameters:
    -----------
    analysis_name : str
        Name of the silhouette analysis
    figsize : Tuple[int, int]
        Figure size
        
    Returns:
    --------
    Callable
        Function that plots silhouette scores from a KMeansPipe
    """
    def _plot_silhouette_scores(pipe):
        if analysis_name not in pipe.silhouette_analysis:
            raise ValueError(f"Silhouette analysis '{analysis_name}' not found. Run find_optimal_k first.")
        
        results = pipe.silhouette_analysis[analysis_name]
        
        plt.figure(figsize=figsize)
        
        # Filter out k=1 (silhouette score is undefined)
        valid_k = [k for k, score in zip(results['k_values'], results['silhouette_scores']) if k > 1]
        valid_scores = [score for k, score in zip(results['k_values'], results['silhouette_scores']) if k > 1]
        
        plt.plot(valid_k, valid_scores, 'go-', linewidth=2, markersize=8)
        
        # Highlight optimal k if available
        if 'optimal_k_silhouette' in results:
            optimal_k = results['optimal_k_silhouette']
            optimal_score = results['silhouette_scores'][results['k_values'].index(optimal_k)]
            plt.axvline(x=optimal_k, color='red', linestyle='--', alpha=0.7)
            plt.plot(optimal_k, optimal_score, 'ro', markersize=12, label=f'Optimal k = {optimal_k}')
            plt.legend()
        
        plt.xlabel('Number of Clusters (k)')
        plt.ylabel('Average Silhouette Score')
        plt.title('Silhouette Analysis for Optimal k')
        plt.grid(True, alpha=0.3)
        plt.xticks(valid_k)
        plt.tight_layout()
        plt.show()
        
        return pipe
    
    return _plot_silhouette_scores


# Model Management Functions
def save_kmeans_model(
    model_name: str,
    filepath: Optional[str] = None,
    include_preprocessing: bool = True
):
    """
    Save K-means model with preprocessing pipeline
    
    Parameters:
    -----------
    model_name : str
        Name of the model to save
    filepath : Optional[str]
        Path to save the model
    include_preprocessing : bool
        Whether to include scalers and reducers
        
    Returns:
    --------
    Callable
        Function that saves K-means model from a KMeansPipe
    """
    def _save_kmeans_model(pipe):
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
            'cluster_assignments': pipe.cluster_assignments.get(model_name, {}),
            'evaluation_metrics': pipe.evaluation_metrics.get(model_name, {}),
            'cluster_profiles': pipe.cluster_profiles.get(model_name, {})
        }
        
        if include_preprocessing:
            model_package.update({
                'scalers': pipe.scalers,
                'dimensionality_reducers': pipe.dimensionality_reducers
            })
        
        joblib.dump(model_package, save_path)
        print(f"K-means model saved to: {save_path}")
        
        return pipe
    
    return _save_kmeans_model


def print_cluster_summary(
    model_name: str
):
    """
    Print comprehensive clustering summary
    
    Parameters:
    -----------
    model_name : str
        Name of the model to summarize
        
    Returns:
    --------
    Callable
        Function that prints cluster summary from a KMeansPipe
    """
    def _print_cluster_summary(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found.")
        
        print(f"\n=== Clustering Summary for {model_name} ===")
        
        # Model configuration
        config = pipe.models[model_name]['config']
        print(f"Algorithm: {pipe.models[model_name]['type']}")
        print(f"Number of clusters: {config['n_clusters']}")
        
        # Evaluation metrics
        if model_name in pipe.evaluation_metrics:
            metrics = pipe.evaluation_metrics[model_name]
            print(f"\nEvaluation Metrics:")
            if 'silhouette_score' in metrics:
                print(f"  Silhouette Score: {metrics['silhouette_score']:.4f}")
            if 'calinski_harabasz_score' in metrics:
                print(f"  Calinski-Harabasz Score: {metrics['calinski_harabasz_score']:.4f}")
            if 'davies_bouldin_score' in metrics:
                print(f"  Davies-Bouldin Score: {metrics['davies_bouldin_score']:.4f}")
            if 'inertia' in metrics:
                print(f"  Inertia: {metrics['inertia']:.4f}")
            
            print(f"\nCluster Sizes:")
            for i, size in enumerate(metrics['cluster_sizes']):
                print(f"  Cluster {i}: {size} points")
        
        # Cluster profiles summary
        if model_name in pipe.cluster_profiles:
            profiles = pipe.cluster_profiles[model_name]
            if 'numerical' in profiles and profiles['numerical'] is not None:
                numerical_profiles = profiles['numerical']
                if not numerical_profiles.empty:
                    print(f"\nTop 5 Discriminating Features (by variance across clusters):")
                    try:
                        # Handle multi-level DataFrame structure
                        if isinstance(numerical_profiles.columns, pd.MultiIndex):
                            # Multi-level columns (count, mean, std, etc.)
                            if 'mean' in numerical_profiles.columns.get_level_values(0):
                                means_data = numerical_profiles['mean'].T
                                feature_variance = means_data.var(axis=1)
                                top_features = feature_variance.nlargest(5)
                                for feature, variance in top_features.items():
                                    print(f"  {feature}: {variance:.4f}")
                            else:
                                print("  No mean values available in numerical profiles")
                        else:
                            # Single-level columns, assume it's already the mean
                            feature_variance = numerical_profiles.var(axis=0)
                            top_features = feature_variance.nlargest(5)
                            for feature, variance in top_features.items():
                                print(f"  {feature}: {variance:.4f}")
                    except Exception as e:
                        print(f"  Error calculating feature variance: {e}")
                else:
                    print("  No numerical profiles available")
            else:
                print("  No numerical profiles found")
        
        return pipe
    
    return _print_cluster_summary


def load_kmeans_model(
    filepath: str,
    model_name: str = 'loaded_model'
):
    """
    Load a previously saved K-means clustering model
    
    Parameters:
    -----------
    filepath : str
        Path to the saved model file
    model_name : str
        Name for the loaded model
        
    Returns:
    --------
    Callable
        Function that loads K-means models into a KMeansPipe
    """
    def _load_kmeans_model(pipe):
        try:
            model_package = joblib.load(filepath)
            
            new_pipe = pipe.copy()
            
            # Restore model
            new_pipe.models[model_name] = {
                'model': model_package['model'],
                'type': model_package['model_type'],
                'config': model_package['config']
            }
            
            # Restore feature columns
            if 'feature_columns' in model_package:
                new_pipe.feature_columns = model_package['feature_columns']
            
            # Restore cluster assignments
            if 'cluster_assignments' in model_package:
                new_pipe.cluster_assignments[model_name] = model_package['cluster_assignments']
            
            # Restore evaluation metrics
            if 'evaluation_metrics' in model_package:
                new_pipe.evaluation_metrics[model_name] = model_package['evaluation_metrics']
            
            # Restore cluster profiles
            if 'cluster_profiles' in model_package:
                new_pipe.cluster_profiles[model_name] = model_package['cluster_profiles']
            
            # Restore preprocessing components
            if 'scalers' in model_package:
                new_pipe.scalers = model_package['scalers']
            
            if 'dimensionality_reducers' in model_package:
                new_pipe.dimensionality_reducers = model_package['dimensionality_reducers']
            
            new_pipe.current_analysis = f'loaded_model_{model_name}'
            
            print(f"Successfully loaded K-means model from: {filepath}")
            print(f"Model type: {model_package['model_type']}")
            print(f"Number of clusters: {model_package['config']['n_clusters']}")
            print(f"Number of features: {len(model_package.get('feature_columns', []))}")
            
            return new_pipe
            
        except Exception as e:
            raise ValueError(f"Failed to load model from {filepath}: {str(e)}")
    
    return _load_kmeans_model


def add_features(
    feature_columns: List[str],
    feature_type: str = 'clustering',
    feature_name: str = 'additional_features'
):
    """
    Add new features to the K-means clustering pipeline
    
    Parameters:
    -----------
    feature_columns : List[str]
        List of new feature column names to add
    feature_type : str
        Type of features ('clustering', 'auxiliary', 'derived')
    feature_name : str
        Name for the feature addition operation
        
    Returns:
    --------
    Callable
        Function that adds features to a KMeansPipe
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
        if feature_type == 'clustering':
            # Add to clustering feature columns
            new_pipe.feature_columns.extend(feature_columns)
            print(f"Added {len(feature_columns)} clustering features: {feature_columns}")
            
        elif feature_type == 'auxiliary':
            # Store auxiliary features (not used for clustering but available for analysis)
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


def retrain_kmeans_model(
    model_name: str,
    new_data: Optional[pd.DataFrame] = None,
    feature_subset: Optional[List[str]] = None,
    update_config: Optional[Dict] = None,
    retrain_name: str = 'retrained_model'
):
    """
    Retrain a K-means model with new data or updated configuration
    
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
        Function that retrains K-means models from a KMeansPipe
    """
    def _retrain_kmeans_model(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for retraining.")
        
        new_pipe = pipe.copy()
        
        # Get the original model configuration
        original_config = new_pipe.models[model_name]['config'].copy()
        
        # Update configuration if provided
        if update_config:
            original_config.update(update_config)
        
        # Determine data to use for retraining
        if new_data is not None:
            retrain_data = new_data.copy()
            # Ensure feature columns exist in new data
            if not feature_subset:
                feature_subset = new_pipe.feature_columns
            
            missing_features = [col for col in feature_subset if col not in retrain_data.columns]
            if missing_features:
                raise ValueError(f"Missing features in new data: {missing_features}")
        else:
            retrain_data = new_pipe.data
            if retrain_data is None:
                raise ValueError("No data available for retraining.")
        
        # Select features for retraining
        if feature_subset:
            clustering_features = feature_subset
        else:
            clustering_features = new_pipe.feature_columns
        
        # Validate features exist in data
        missing_features = [col for col in clustering_features if col not in retrain_data.columns]
        if missing_features:
            raise ValueError(f"Missing features in data: {missing_features}")
        
        X = retrain_data[clustering_features]
        
        # Create new model with updated configuration
        if new_pipe.models[model_name]['type'] == 'kmeans':
            from sklearn.cluster import KMeans
            retrained_model = KMeans(
                n_clusters=original_config['n_clusters'],
                init=original_config.get('init', 'k-means++'),
                n_init=original_config.get('n_init', 10),
                max_iter=original_config.get('max_iter', 300),
                tol=original_config.get('tol', 1e-4),
                random_state=original_config.get('random_state', 42),
                algorithm=original_config.get('algorithm', 'lloyd')
            )
        elif new_pipe.models[model_name]['type'] == 'minibatch_kmeans':
            from sklearn.cluster import MiniBatchKMeans
            retrained_model = MiniBatchKMeans(
                n_clusters=original_config['n_clusters'],
                init=original_config.get('init', 'k-means++'),
                max_iter=original_config.get('max_iter', 100),
                batch_size=original_config.get('batch_size', 1024),
                tol=original_config.get('tol', 0.0),
                max_no_improvement=original_config.get('max_no_improvement', 10),
                random_state=original_config.get('random_state', 42)
            )
        else:
            raise ValueError(f"Unknown model type: {new_pipe.models[model_name]['type']}")
        
        # Fit the retrained model
        retrained_model.fit(X)
        
        # Store the retrained model
        new_pipe.models[retrain_name] = {
            'model': retrained_model,
            'type': new_pipe.models[model_name]['type'],
            'config': original_config
        }
        
        # Generate cluster assignments for retrained model
        cluster_labels = retrained_model.predict(X)
        retrain_data[f'{retrain_name}_cluster'] = cluster_labels
        
        new_pipe.cluster_assignments[retrain_name] = {
            'labels': cluster_labels,
            'features_used': clustering_features,
            'cluster_column': f'{retrain_name}_cluster'
        }
        
        # Update data if using new data
        if new_data is not None:
            new_pipe.data = retrain_data
        
        new_pipe.current_analysis = f'retrain_{retrain_name}'
        
        print(f"Successfully retrained model '{model_name}' as '{retrain_name}'")
        print(f"Model type: {new_pipe.models[model_name]['type']}")
        print(f"Number of clusters: {original_config['n_clusters']}")
        print(f"Features used: {len(clustering_features)}")
        print(f"Data points: {len(X)}")
        
        return new_pipe
    
    return _retrain_kmeans_model


def predict_clusters(
    model_name: str,
    new_data: pd.DataFrame,
    feature_subset: Optional[List[str]] = None,
    prediction_name: str = 'cluster_predictions'
):
    """
    Predict cluster assignments for new data using a trained K-means model
    
    Parameters:
    -----------
    model_name : str
        Name of the trained model to use for prediction
    new_data : pd.DataFrame
        New data to predict clusters for
    feature_subset : Optional[List[str]]
        Subset of features to use for prediction
    prediction_name : str
        Name for the prediction results
        
    Returns:
    --------
    Callable
        Function that predicts clusters from a KMeansPipe
    """
    def _predict_clusters(pipe):
        if model_name not in pipe.models:
            raise ValueError(f"Model '{model_name}' not found for prediction.")
        
        new_pipe = pipe.copy()
        
        # Select features for prediction
        if feature_subset:
            prediction_features = feature_subset
        else:
            prediction_features = new_pipe.feature_columns
        
        # Validate features exist in new data
        missing_features = [col for col in prediction_features if col not in new_data.columns]
        if missing_features:
            raise ValueError(f"Missing features in new data: {missing_features}")
        
        # Get the model
        model = new_pipe.models[model_name]['model']
        
        # Prepare data for prediction
        X_new = new_data[prediction_features]
        
        # Make predictions
        cluster_predictions = model.predict(X_new)
        
        # Calculate distances to cluster centers
        cluster_distances = model.transform(X_new)
        
        # Create results DataFrame
        results_df = new_data.copy()
        results_df[f'{prediction_name}_cluster'] = cluster_predictions
        results_df[f'{prediction_name}_distance_to_center'] = np.min(cluster_distances, axis=1)
        
        # Add confidence scores (inverse of distance to center)
        max_distance = np.max(cluster_distances)
        results_df[f'{prediction_name}_confidence'] = 1 - (np.min(cluster_distances, axis=1) / max_distance)
        
        # Store prediction results
        if not hasattr(new_pipe, 'predictions'):
            new_pipe.predictions = {}
        
        new_pipe.predictions[prediction_name] = {
            'data': results_df,
            'cluster_assignments': cluster_predictions,
            'distances_to_centers': cluster_distances,
            'features_used': prediction_features,
            'model_used': model_name
        }
        
        new_pipe.current_analysis = f'prediction_{prediction_name}'
        
        print(f"Successfully predicted clusters for {len(new_data)} data points")
        print(f"Model used: {model_name}")
        print(f"Features used: {len(prediction_features)}")
        print(f"Cluster distribution: {dict(pd.Series(cluster_predictions).value_counts().sort_index())}")
        
        return new_pipe
    
    return _predict_clusters


def get_prediction_results(
    prediction_name: Optional[str] = None
):
    """
    Get prediction results from the pipeline
    
    Parameters:
    -----------
    prediction_name : Optional[str]
        Specific prediction to retrieve (if None, returns all)
        
    Returns:
    --------
    Callable
        Function that retrieves prediction results from a KMeansPipe
    """
    def _get_prediction_results(pipe):
        if not hasattr(pipe, 'predictions') or not pipe.predictions:
            return {"error": "No prediction results found. Run predict_clusters first."}
        
        if prediction_name:
            if prediction_name in pipe.predictions:
                return pipe.predictions[prediction_name]
            else:
                return {"error": f"Prediction '{prediction_name}' not found"}
        
        return pipe.predictions
    
    return _get_prediction_results