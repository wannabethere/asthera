import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.metrics import silhouette_score
import warnings
from typing import List, Dict, Union, Optional, Any, Tuple, Callable


class SegmentationPipe:
    """
    A pipeline-style segmentation tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def __init__(self, data=None):
        """Initialize with optional data"""
        self.data = data 
        self.features = None
        self.feature_columns = None
        self.scaled_features = None
        self.segments = {}
        self.segmentation_results = {}
        self.current_analysis = None
    
    def __or__(self, other):
        """Enable the | (pipe) operator for function composition"""
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe SegmentationPipe to {type(other)}")
    
    def copy(self):
        """Create a copy with deep copy of data"""
        new_pipe = SegmentationPipe()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        if self.features is not None:
            new_pipe.features = self.features.copy()
        new_pipe.feature_columns = self.feature_columns
        if self.scaled_features is not None:
            new_pipe.scaled_features = self.scaled_features.copy()
        new_pipe.segments = self.segments.copy()
        new_pipe.segmentation_results = self.segmentation_results.copy()
        new_pipe.current_analysis = self.current_analysis
        return new_pipe
    
    @classmethod
    def from_dataframe(cls, df):
        """Create a SegmentationPipe from a dataframe"""
        pipe = cls()
        pipe.data = df.copy()
        return pipe


def get_features(
    columns: Optional[List[str]] = None,
    id_column: Optional[str] = None,
    handle_missing: bool = True,
    scale_features: bool = True
):
    """
    Extract features from dataframe for segmentation
    
    Parameters:
    -----------
    columns : List[str], optional
        List of column names to use as features
        If None, all numeric columns will be used
    id_column : str, optional
        Column containing IDs to exclude from features
    handle_missing : bool, default=True
        Whether to handle missing values
    scale_features : bool, default=True
        Whether to scale features
        
    Returns:
    --------
    Callable
        Function that extracts features from a SegmentationPipe
    """
    def _get_features(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Determine feature columns
        if columns is not None:
            feature_cols = columns
            # Check if columns exist
            missing_cols = [col for col in feature_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Columns not found in data: {missing_cols}")
        else:
            # Use all numeric columns except the ID column
            feature_cols = df.select_dtypes(include=np.number).columns.tolist()
            if id_column and id_column in feature_cols:
                feature_cols.remove(id_column)
        
        # Handle missing values if requested
        if handle_missing:
            for col in feature_cols:
                if df[col].isnull().sum() > 0:
                    df[col] = df[col].fillna(df[col].mean())
        
        # Extract features
        features = df[feature_cols].values
        
        # Scale features if requested
        if scale_features:
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)
            new_pipe.scaled_features = scaled_features
        
        # Store results
        new_pipe.features = features
        new_pipe.feature_columns = feature_cols
        
        return new_pipe
    
    return _get_features


def run_kmeans(
    n_clusters: int = 5,
    max_clusters: int = 10,
    find_optimal: bool = False,
    random_state: int = 42,
    segment_name: str = 'kmeans'
):
    """
    Run KMeans clustering for segmentation
    
    Parameters:
    -----------
    n_clusters : int, default=5
        Number of clusters
    max_clusters : int, default=10
        Maximum number of clusters to try if find_optimal=True
    find_optimal : bool, default=False
        Whether to find the optimal number of clusters using silhouette score
    random_state : int, default=42
        Random state for reproducibility
    segment_name : str, default='kmeans'
        Name to use for this segmentation
        
    Returns:
    --------
    Callable
        Function that performs KMeans segmentation in a SegmentationPipe
    """
    def _run_kmeans(pipe):
        features = pipe.scaled_features if pipe.scaled_features is not None else pipe.features
        if features is None:
            raise ValueError("No features found. Call get_features() first.")
        
        new_pipe = pipe.copy()
        
        # Use a local variable for n_clusters to avoid modifying the outer variable
        num_clusters = n_clusters
        
        # Find optimal number of clusters if requested
        if find_optimal:
            silhouette_scores = []
            inertia_values = []
            
            for k in range(2, min(max_clusters + 1, features.shape[0])):
                kmeans = KMeans(n_clusters=k, random_state=random_state)
                labels = kmeans.fit_predict(features)
                
                if len(np.unique(labels)) > 1:
                    score = silhouette_score(features, labels)
                    silhouette_scores.append(score)
                else:
                    silhouette_scores.append(-1)
                
                inertia_values.append(kmeans.inertia_)
            
            if silhouette_scores:
                optimal_k = np.argmax(silhouette_scores) + 2  # +2 because we start from k=2
                num_clusters = optimal_k  # Use the local variable, not the parameter
        
        # Run KMeans with the selected/optimal number of clusters
        kmeans = KMeans(n_clusters=num_clusters, random_state=random_state)
        labels = kmeans.fit_predict(features)
        
        # Add segment labels to dataframe
        new_pipe.data[f'segment_{segment_name}'] = labels
        
        # Store results
        silhouette = silhouette_score(features, labels) if len(np.unique(labels)) > 1 else -1
        
        result = {
            'algorithm': 'kmeans',
            'n_clusters': num_clusters,  # Use the local variable
            'labels': labels,
            'silhouette_score': silhouette,
            'inertia': kmeans.inertia_,
            'cluster_centers': kmeans.cluster_centers_
        }
        
        new_pipe.segments[segment_name] = labels
        new_pipe.segmentation_results[segment_name] = result
        new_pipe.current_analysis = segment_name
        
        return new_pipe
    
    return _run_kmeans

def run_dbscan(
    eps: float = 0.5,
    min_samples: int = 5,
    segment_name: str = 'dbscan'
):
    """
    Run DBSCAN clustering for segmentation
    
    Parameters:
    -----------
    eps : float, default=0.5
        The maximum distance between two samples for one to be considered as neighbors
    min_samples : int, default=5
        The number of samples in a neighborhood for a point to be considered a core point
    segment_name : str, default='dbscan'
        Name to use for this segmentation
        
    Returns:
    --------
    Callable
        Function that performs DBSCAN segmentation in a SegmentationPipe
    """
    def _run_dbscan(pipe):
        features = pipe.scaled_features if pipe.scaled_features is not None else pipe.features
        if features is None:
            raise ValueError("No features found. Call get_features() first.")
        
        new_pipe = pipe.copy()
        
        # Run DBSCAN
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        labels = dbscan.fit_predict(features)
        
        # Add segment labels to dataframe
        new_pipe.data[f'segment_{segment_name}'] = labels
        
        # Store results
        n_clusters = len(np.unique(labels[labels >= 0]))
        silhouette = silhouette_score(features, labels) if n_clusters > 1 and len(np.unique(labels)) > 1 else -1
        
        result = {
            'algorithm': 'dbscan',
            'eps': eps,
            'min_samples': min_samples,
            'n_clusters': n_clusters,
            'labels': labels,
            'silhouette_score': silhouette,
            'noise_points': sum(labels == -1),
            'noise_percentage': sum(labels == -1) / len(labels) * 100
        }
        
        new_pipe.segments[segment_name] = labels
        new_pipe.segmentation_results[segment_name] = result
        new_pipe.current_analysis = segment_name
        
        return new_pipe
    
    return _run_dbscan


def run_hierarchical(
    n_clusters: int = 5,
    linkage: str = 'ward',
    segment_name: str = 'hierarchical'
):
    """
    Run Hierarchical (Agglomerative) clustering for segmentation
    
    Parameters:
    -----------
    n_clusters : int, default=5
        Number of clusters
    linkage : str, default='ward'
        Linkage method ('ward', 'complete', 'average', 'single')
    segment_name : str, default='hierarchical'
        Name to use for this segmentation
        
    Returns:
    --------
    Callable
        Function that performs hierarchical segmentation in a SegmentationPipe
    """
    def _run_hierarchical(pipe):
        features = pipe.scaled_features if pipe.scaled_features is not None else pipe.features
        if features is None:
            raise ValueError("No features found. Call get_features() first.")
        
        new_pipe = pipe.copy()
        
        # Run Agglomerative Clustering
        agg = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage)
        labels = agg.fit_predict(features)
        
        # Add segment labels to dataframe
        new_pipe.data[f'segment_{segment_name}'] = labels
        
        # Store results
        silhouette = silhouette_score(features, labels) if len(np.unique(labels)) > 1 else -1
        
        result = {
            'algorithm': 'hierarchical',
            'linkage': linkage,
            'n_clusters': n_clusters,
            'labels': labels,
            'silhouette_score': silhouette
        }
        
        new_pipe.segments[segment_name] = labels
        new_pipe.segmentation_results[segment_name] = result
        new_pipe.current_analysis = segment_name
        
        return new_pipe
    
    return _run_hierarchical


def run_rule_based(
    rules: Dict[str, Dict],
    segment_name: str = 'rule_based'
):
    """
    Run rule-based segmentation
    
    Parameters:
    -----------
    rules : Dict[str, Dict]
        Dictionary with segment names as keys and rule conditions as values
        Example: {
            'high_value': {'spending': ('>', 100), 'frequency': ('>', 10)},
            'medium_value': {'spending': ('between', 50, 100)}
        }
    segment_name : str, default='rule_based'
        Name to use for this segmentation
        
    Returns:
    --------
    Callable
        Function that performs rule-based segmentation in a SegmentationPipe
    """
    def _run_rule_based(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Initialize with default 'Other' segment
        df[f'segment_{segment_name}'] = 'Other'
        
        # Apply each rule
        for segment_label, conditions in rules.items():
            mask = pd.Series(True, index=df.index)
            
            for col, condition in conditions.items():
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found in data")
                
                if condition[0] == '>':
                    mask &= (df[col] > condition[1])
                elif condition[0] == '>=':
                    mask &= (df[col] >= condition[1])
                elif condition[0] == '<':
                    mask &= (df[col] < condition[1])
                elif condition[0] == '<=':
                    mask &= (df[col] <= condition[1])
                elif condition[0] == '==':
                    mask &= (df[col] == condition[1])
                elif condition[0] == '!=':
                    mask &= (df[col] != condition[1])
                elif condition[0] == 'in':
                    mask &= (df[col].isin(condition[1]))
                elif condition[0] == 'not in':
                    mask &= (~df[col].isin(condition[1]))
                elif condition[0] == 'between':
                    if len(condition) != 3:
                        raise ValueError("'between' operator requires two values")
                    mask &= (df[col] >= condition[1]) & (df[col] <= condition[2])
                elif condition[0] == 'contains':
                    mask &= (df[col].astype(str).str.contains(condition[1]))
                else:
                    raise ValueError(f"Unknown operator: {condition[0]}")
            
            # Apply the rule
            df.loc[mask, f'segment_{segment_name}'] = segment_label
        
        # Create numeric labels
        unique_segments = df[f'segment_{segment_name}'].unique()
        segment_mapping = {segment: i for i, segment in enumerate(unique_segments)}
        df[f'segment_{segment_name}_encoded'] = df[f'segment_{segment_name}'].map(segment_mapping)
        
        # Store results
        result = {
            'algorithm': 'rule_based',
            'segments': unique_segments,
            'segment_mapping': segment_mapping,
            'n_segments': len(unique_segments),
            'rules': rules
        }
        
        new_pipe.segments[segment_name] = df[f'segment_{segment_name}']
        new_pipe.segmentation_results[segment_name] = result
        new_pipe.current_analysis = segment_name
        
        return new_pipe
    
    return _run_rule_based


def generate_summary(algorithm: Optional[str] = None):
    """
    Generate summary statistics for segments
    
    Parameters:
    -----------
    algorithm : str, optional
        Name of the segmentation algorithm to summarize
        If None, uses the current analysis
        
    Returns:
    --------
    Callable
        Function that generates summary statistics in a SegmentationPipe
    """
    def _generate_summary(pipe):
        if not pipe.segmentation_results:
            raise ValueError("No segmentation results found. Run a segmentation algorithm first.")
        
        # Determine which algorithm to summarize
        algorithm_name = algorithm
        if algorithm_name is None:
            algorithm_name = pipe.current_analysis
            if algorithm_name is None:
                # Use the first algorithm if none specified
                algorithm_name = next(iter(pipe.segmentation_results))
        
        if algorithm_name not in pipe.segmentation_results:
            raise ValueError(f"Algorithm '{algorithm_name}' not found in segmentation results")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        result = new_pipe.segmentation_results[algorithm_name]
        
        # Get segment column name
        segment_col = f'segment_{algorithm_name}'
        
        # Create summary statistics by segment
        if result['algorithm'] == 'rule_based':
            # For rule-based segmentation, use string segment names
            segment_col_for_grouping = segment_col
        else:
            # For other algorithms, use numeric labels
            segment_col_for_grouping = segment_col
        
        # Get summary statistics for each numeric column by segment
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        if segment_col_for_grouping in numeric_cols:
            numeric_cols.remove(segment_col_for_grouping)
        
        segment_stats = df.groupby(segment_col_for_grouping)[numeric_cols].agg(['mean', 'median', 'std', 'min', 'max'])
        
        # Get segment sizes
        segment_sizes = df[segment_col_for_grouping].value_counts().sort_index()
        segment_percentages = (segment_sizes / len(df) * 100).round(2)
        
        # Calculate feature importance (how distinctive each feature is for each segment)
        feature_importance = {}
        
        if pipe.feature_columns:
            # Calculate z-scores (standard deviations from overall mean)
            overall_means = df[pipe.feature_columns].mean()
            overall_stds = df[pipe.feature_columns].std()
            
            for segment in pd.unique(df[segment_col_for_grouping]):
                segment_means = df[df[segment_col_for_grouping] == segment][pipe.feature_columns].mean()
                # Calculate absolute z-scores
                z_scores = np.abs((segment_means - overall_means) / overall_stds)
                # Sort features by importance
                feature_importance[segment] = z_scores.sort_values(ascending=False)
        
        # Create segment profiles (short descriptions based on most distinctive features)
        segment_profiles = {}
        
        if feature_importance:
            for segment, importance in feature_importance.items():
                # Take top features
                top_features = importance.head(3)
                
                profile = f"Segment {segment}: "
                for feature, score in top_features.items():
                    segment_mean = df[df[segment_col_for_grouping] == segment][feature].mean()
                    overall_mean = overall_means[feature]
                    direction = "higher" if segment_mean > overall_mean else "lower"
                    profile += f"{feature} {direction} ({abs(segment_mean/overall_mean - 1):.1%} diff), "
                
                segment_profiles[segment] = profile.rstrip(", ")
        
        # Store summary results
        summary = {
            'algorithm': algorithm_name,
            'segment_stats': segment_stats,
            'segment_sizes': segment_sizes,
            'segment_percentages': segment_percentages,
            'feature_importance': feature_importance,
            'segment_profiles': segment_profiles
        }
        
        new_pipe.segmentation_results[f"{algorithm_name}_summary"] = summary
        
        return summary
    
    return _generate_summary


def get_segment_data(segment_id, algorithm=None):
    """
    Get data for a specific segment
    
    Parameters:
    -----------
    segment_id : Any
        ID of the segment to extract
    algorithm : str, optional
        Name of the segmentation algorithm to use
        If None, uses the current analysis
        
    Returns:
    --------
    Callable
        Function that extracts segment data from a SegmentationPipe
    """
    def _get_segment_data(pipe):
        if not pipe.segmentation_results:
            raise ValueError("No segmentation results found. Run a segmentation algorithm first.")
        
        # Determine which algorithm to use
        algorithm_name = algorithm
        if algorithm_name is None:
            algorithm_name = pipe.current_analysis
            if algorithm_name is None:
                # Use the first algorithm if none specified
                algorithm_name = next(iter(pipe.segmentation_results))
        
        if algorithm_name not in pipe.segmentation_results:
            raise ValueError(f"Algorithm '{algorithm_name}' not found in segmentation results")
        
        df = pipe.data
        
        # Get segment column name
        segment_col = f'segment_{algorithm_name}'
        
        # Extract data for the specified segment
        segment_data = df[df[segment_col] == segment_id].copy()
        
        return segment_data
    
    return _get_segment_data


def compare_algorithms():
    """
    Compare all segmentation algorithms
    
    Returns:
    --------
    Callable
        Function that compares segmentation algorithms in a SegmentationPipe
    """
    def _compare_algorithms(pipe):
        if not pipe.segmentation_results:
            raise ValueError("No segmentation results found. Run a segmentation algorithm first.")
        
        comparison = []
        
        for name, result in pipe.segmentation_results.items():
            # Skip summary results
            if name.endswith('_summary'):
                continue
            
            row = {
                'algorithm': name,
                'method': result['algorithm'],
                'n_segments': result['n_clusters'] if 'n_clusters' in result else result.get('n_segments', 0)
            }
            
            # Add algorithm-specific metrics
            if 'silhouette_score' in result:
                row['silhouette_score'] = result['silhouette_score']
            
            if result['algorithm'] == 'kmeans':
                row['inertia'] = result['inertia']
            
            if result['algorithm'] in ['dbscan']:
                row['noise_points'] = result['noise_points']
                row['noise_percentage'] = result['noise_percentage']
            
            comparison.append(row)
        
        return pd.DataFrame(comparison)
    
    return _compare_algorithms


def custom_calculation(func: Callable):
    """
    Apply a custom calculation or transformation to the dataframe
    
    Parameters:
    -----------
    func : Callable
        A function that takes a DataFrame and returns a DataFrame
        
    Returns:
    --------
    Callable
        Function that applies the custom calculation in a SegmentationPipe
    """
    def _custom_calculation(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Apply the custom function to the dataframe
        new_pipe.data = func(df)
        
        return new_pipe
    
    return _custom_calculation