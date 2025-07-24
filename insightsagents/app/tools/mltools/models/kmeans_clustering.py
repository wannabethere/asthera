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


class KMeansPipe:
    """
    A pipeline-style K-means clustering tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data
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
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe KMeansPipe to {type(other)}")
    
    def copy(self):
        """Create a shallow copy with deep copy of data"""
        new_pipe = KMeansPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        if self.original_data is not None:
            new_pipe.original_data = self.original_data.copy()
        new_pipe.feature_columns = self.feature_columns.copy()
        new_pipe.models = self.models.copy()
        new_pipe.cluster_assignments = self.cluster_assignments.copy()
        new_pipe.cluster_profiles = self.cluster_profiles.copy()
        new_pipe.evaluation_metrics = self.evaluation_metrics.copy()
        new_pipe.scalers = self.scalers.copy()
        new_pipe.dimensionality_reducers = self.dimensionality_reducers.copy()
        new_pipe.elbow_analysis = self.elbow_analysis.copy()
        new_pipe.silhouette_analysis = self.silhouette_analysis.copy()
        new_pipe.current_analysis = self.current_analysis
        new_pipe.visualization_data = self.visualization_data.copy()
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a KMeansPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        pipe.original_data = df.copy()
        return pipe


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
            if outlier_method == 'iqr':
                Q1 = feature_data.quantile(0.25)
                Q3 = feature_data.quantile(0.75)
                IQR = Q3 - Q1
                outlier_mask = ~((feature_data < (Q1 - 1.5 * IQR)) | (feature_data > (Q3 + 1.5 * IQR))).any(axis=1)
            elif outlier_method == 'zscore':
                z_scores = np.abs((feature_data - feature_data.mean()) / feature_data.std())
                outlier_mask = (z_scores < outlier_threshold).all(axis=1)
            else:
                raise ValueError(f"Unknown outlier method: {outlier_method}")
            
            feature_data = feature_data[outlier_mask]
            df = df.loc[feature_data.index]
        
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
        
        if scaler:
            scaled_features = scaler.fit_transform(feature_data)
            scaled_df = pd.DataFrame(scaled_features, columns=feature_columns, index=feature_data.index)
            new_pipe.scalers['features'] = scaler
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
            for col1, col2 in ratio_features:
                if col1 in df.columns and col2 in df.columns:
                    if pd.api.types.is_numeric_dtype(df[col1]) and pd.api.types.is_numeric_dtype(df[col2]):
                        ratio_name = f'{col1}_div_{col2}'
                        df[ratio_name] = df[col1] / (df[col2] + 1e-8)  # Avoid division by zero
                        new_features.append(ratio_name)
        
        # Create aggregation features
        if aggregation_features:
            for group_col, agg_cols in aggregation_features.items():
                if group_col in df.columns:
                    for agg_col in agg_cols:
                        if agg_col in df.columns and pd.api.types.is_numeric_dtype(df[agg_col]):
                            group_stats = df.groupby(group_col)[agg_col].agg(['mean', 'std', 'min', 'max'])
                            df = df.merge(
                                group_stats.add_prefix(f'{agg_col}_by_{group_col}_'),
                                left_on=group_col,
                                right_index=True,
                                how='left'
                            )
                            new_features.extend([
                                f'{agg_col}_by_{group_col}_mean',
                                f'{agg_col}_by_{group_col}_std',
                                f'{agg_col}_by_{group_col}_min',
                                f'{agg_col}_by_{group_col}_max'
                            ])
        
        # Create binning features
        if binning_features:
            for col, n_bins in binning_features.items():
                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                    binned_name = f'{col}_binned'
                    df[binned_name] = pd.cut(df[col], bins=n_bins, labels=False)
                    new_features.append(binned_name)
        
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
        dim_columns = [f'{method}_dim_{i+1}' for i in range(n_components)]
        
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
            means_data = profiles['numerical']['mean'].T
            
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
            if 'numerical' in profiles:
                print(f"\nTop 5 Discriminating Features (by variance across clusters):")
                means_data = profiles['numerical']['mean'].T
                feature_variance = means_data.var(axis=1)
                top_features = feature_variance.nlargest(5)
                for feature, variance in top_features.items():
                    print(f"  {feature}: {variance:.4f}")
        
        return pipe
    
    return _print_cluster_summary