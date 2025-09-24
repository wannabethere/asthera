import numpy as np
import pandas as pd
from typing import List, Dict, Union, Optional, Any, Tuple, Callable
import warnings
from .base_pipe import BasePipe

class MetricsPipe(BasePipe):
    """
    A pipeline-style metrics analysis tool that enables functional composition
    with a meterstick-like interface.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for metrics analysis"""
        self.metrics = {}
        self.pivot_tables = {}
        self.current_metric = None
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'metrics'):
            self.metrics = source_pipe.metrics.copy()
        if hasattr(source_pipe, 'pivot_tables'):
            self.pivot_tables = source_pipe.pivot_tables.copy()
        if hasattr(source_pipe, 'current_metric'):
            self.current_metric = source_pipe.current_metric
    
    def merge_to_df(self, base_df: pd.DataFrame, include_metadata: bool = False, include_pivot_tables: bool = True, **kwargs) -> pd.DataFrame:
        """
        Merge metrics results into the base dataframe as new columns.
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge results into
        include_metadata : bool, default=False
            Whether to include metadata columns in the output DataFrame
        include_pivot_tables : bool, default=True
            Whether to include pivot table information in the output DataFrame
        **kwargs : dict
            Additional arguments (unused for this pipeline)
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with metrics results merged as new columns
        """
        result_df = base_df.copy()
        
        # Add pipeline identification
        result_df['pipeline_type'] = 'metrics'
        result_df['pipeline_has_results'] = len(self.metrics) > 0 or len(self.pivot_tables) > 0
        
        # Add metrics as new columns
        for metric_name, metric_value in self.metrics.items():
            result_df[f'metrics_{metric_name}'] = metric_value
            
            if include_metadata:
                result_df[f'metrics_{metric_name}_type'] = 'metric'
                result_df[f'metrics_{metric_name}_metadata'] = f"Calculated metric: {metric_name}"
        
        # Add pivot table information
        if include_pivot_tables and self.pivot_tables:
            for i, (pivot_name, pivot_table) in enumerate(self.pivot_tables.items()):
                # Add summary information about the pivot table
                result_df[f'metrics_pivot_{pivot_name}_shape'] = f"{pivot_table.shape[0]}x{pivot_table.shape[1]}"
                result_df[f'metrics_pivot_{pivot_name}_has_data'] = not pivot_table.empty
                
                if include_metadata:
                    result_df[f'metrics_pivot_{pivot_name}_index_cols'] = ', '.join(pivot_table.index.names) if pivot_table.index.names != [None] else 'none'
                    result_df[f'metrics_pivot_{pivot_name}_value_cols'] = ', '.join(pivot_table.columns.astype(str))
        
        # Add summary metadata
        if include_metadata:
            result_df['metrics_total_metrics'] = len(self.metrics)
            result_df['metrics_total_pivot_tables'] = len(self.pivot_tables)
            result_df['metrics_available_metrics'] = ', '.join(self.metrics.keys()) if self.metrics else 'none'
            result_df['metrics_available_pivot_tables'] = ', '.join(self.pivot_tables.keys()) if self.pivot_tables else 'none'
        
        return result_df
    
    def _has_results(self) -> bool:
        """
        Check if the pipeline has any metrics results.
        
        Returns:
        --------
        bool
            True if the pipeline has metrics results, False otherwise
        """
        return len(self.metrics) > 0 or len(self.pivot_tables) > 0
    
    def get_metrics_df(self, include_metadata: bool = False):
        """
        Get a DataFrame containing only the calculated metrics
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with metrics only
        """
        if not self.metrics:
            return pd.DataFrame()
        
        metrics_data = []
        for metric_name, metric_value in self.metrics.items():
            row = {
                'metric_name': metric_name,
                'value': metric_value,
                'data_type': type(metric_value).__name__
            }
            
            if include_metadata:
                row['metadata'] = f"Calculated metric: {metric_name}"
            
            metrics_data.append(row)
        
        return pd.DataFrame(metrics_data)
    
    def get_pivot_tables_dict(self):
        """
        Get a dictionary of all pivot tables
        
        Returns:
        --------
        Dict[str, pd.DataFrame]
            Dictionary mapping pivot table names to their DataFrames
        """
        return self.pivot_tables.copy()
    
    def get_current_result(self):
        """
        Get the current metric or pivot table result
        
        Returns:
        --------
        Any
            The current metric value or pivot table DataFrame
        """
        if self.current_metric is None:
            return None
        
        if self.current_metric in self.metrics:
            return self.metrics[self.current_metric]
        elif self.current_metric in self.pivot_tables:
            return self.pivot_tables[self.current_metric]
        else:
            return None
    
    def get_summary_df(self, include_metadata: bool = False):
        """
        Get a summary DataFrame of all calculated metrics and pivot tables
        
        Parameters:
        -----------
        include_metadata : bool, default=False
            Whether to include metadata columns
            
        Returns:
        --------
        pd.DataFrame
            Summary DataFrame with statistics about metrics and pivot tables
        """
        summary_data = []
        
        # Summary of metrics
        if self.metrics:
            metrics_count = len(self.metrics)
            numeric_metrics = [v for v in self.metrics.values() if isinstance(v, (int, float)) and not pd.isna(v)]
            
            summary_data.append({
                'type': 'metrics',
                'count': metrics_count,
                'numeric_count': len(numeric_metrics),
                'current_metric': self.current_metric if self.current_metric in self.metrics else None
            })
            
            if include_metadata and numeric_metrics:
                summary_data[-1].update({
                    'min_value': min(numeric_metrics),
                    'max_value': max(numeric_metrics),
                    'avg_value': sum(numeric_metrics) / len(numeric_metrics)
                })
        
        # Summary of pivot tables
        if self.pivot_tables:
            pivot_count = len(self.pivot_tables)
            pivot_shapes = [f"{pivot.shape[0]}x{pivot.shape[1]}" for pivot in self.pivot_tables.values()]
            
            summary_data.append({
                'type': 'pivot_tables',
                'count': pivot_count,
                'shapes': ', '.join(pivot_shapes),
                'current_pivot': self.current_metric if self.current_metric in self.pivot_tables else None
            })
        
        return pd.DataFrame(summary_data)
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the metrics analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in metrics pipe)
            
        Returns:
        --------
        dict
            Summary of the metrics analysis results
        """
        if not self.metrics and not self.pivot_tables:
            return {"error": "No metrics or pivot tables have been calculated"}
        
        # Get summary DataFrame
        summary_df = self.get_summary_df()
        
        return {
            "total_metrics": len(self.metrics),
            "total_pivot_tables": len(self.pivot_tables),
            "available_metrics": list(self.metrics.keys()),
            "available_pivot_tables": list(self.pivot_tables.keys()),
            "current_metric": self.current_metric,
            "summary_dataframe": summary_df.to_dict('records') if not summary_df.empty else [],
            "metrics_values": self.metrics,
            "pivot_tables_info": {name: {"shape": table.shape, "columns": list(table.columns)} 
                                for name, table in self.pivot_tables.items()}
        }


# Basic Metrics Functions
def Count(variable: str, output_name: Optional[str] = None):
    """
    Count the number of non-null entries in a column
    
    Parameters:
    -----------
    variable : str
        Column name to count
    output_name : str, optional
        Name for the output metric, defaults to 'count_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates count from a MetricsPipe
    """
    def _count(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the count
        result = df[variable].count()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"count_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _count


def Sum(variable: str, output_name: Optional[str] = None):
    """
    Calculate the sum of a column
    
    Parameters:
    -----------
    variable : str
        Column name to sum
    output_name : str, optional
        Name for the output metric, defaults to 'sum_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates sum from a MetricsPipe
    """
    def _sum(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the sum
        result = df[variable].sum()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"sum_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _sum


def Max(variable: str, output_name: Optional[str] = None):
    """
    Calculate the maximum value of a column
    
    Parameters:
    -----------
    variable : str
        Column name to find maximum
    output_name : str, optional
        Name for the output metric, defaults to 'max_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates maximum from a MetricsPipe
    """
    def _max(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the maximum
        result = df[variable].max()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"max_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _max


def Min(variable: str, output_name: Optional[str] = None):
    """
    Calculate the minimum value of a column
    
    Parameters:
    -----------
    variable : str
        Column name to find minimum
    output_name : str, optional
        Name for the output metric, defaults to 'min_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates minimum from a MetricsPipe
    """
    def _min(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the minimum
        result = df[variable].min()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"min_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _min


def Ratio(numerator: str, denominator: str, output_name: Optional[str] = None):
    """
    Calculate the ratio of sums of two columns
    
    Parameters:
    -----------
    numerator : str
        Column name for numerator
    denominator : str
        Column name for denominator
    output_name : str, optional
        Name for the output metric, defaults to 'ratio_{numerator}_{denominator}'
        
    Returns:
    --------
    Callable
        Function that calculates ratio from a MetricsPipe
    """
    def _ratio(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the sum of numerator and denominator
        num_sum = df[numerator].sum()
        denom_sum = df[denominator].sum()
        
        # Calculate the ratio, handling division by zero
        if denom_sum == 0:
            warnings.warn(f"Division by zero encountered in ratio calculation. Denominator '{denominator}' sum is zero.")
            result = float('nan')
        else:
            result = num_sum / denom_sum
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"ratio_{numerator}_{denominator}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _ratio


def Dot(variable1: str, variable2: str, normalize: bool = False, output_name: Optional[str] = None):
    """
    Calculate the dot product between two columns
    
    Parameters:
    -----------
    variable1 : str
        First column name
    variable2 : str
        Second column name
    normalize : bool, default=False
        Whether to normalize the dot product using the lengths
    output_name : str, optional
        Name for the output metric, defaults to 'dot_{variable1}_{variable2}'
        
    Returns:
    --------
    Callable
        Function that calculates dot product from a MetricsPipe
    """
    def _dot(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the dot product
        dot_product = (df[variable1] * df[variable2]).sum()
        
        if normalize:
            # Calculate the lengths
            length1 = np.sqrt((df[variable1] ** 2).sum())
            length2 = np.sqrt((df[variable2] ** 2).sum())
            
            # Normalize the dot product, handling division by zero
            if length1 == 0 or length2 == 0:
                warnings.warn("Division by zero encountered in normalized dot product calculation.")
                result = float('nan')
            else:
                result = dot_product / (length1 * length2)
        else:
            result = dot_product
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"dot_{variable1}_{variable2}"
        if normalize:
            metric_name = f"normalized_{metric_name}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _dot


def Nth(variable: str, n: int, sort_by: str, ascending: bool = True, dropna: bool = False, output_name: Optional[str] = None):
    """
    Get the nth value of a column after sorting by another column
    
    Parameters:
    -----------
    variable : str
        Column to get the value from
    n : int
        Index of the value to retrieve (0-based)
    sort_by : str
        Column to sort by
    ascending : bool, default=True
        Whether to sort in ascending order
    dropna : bool, default=False
        Whether to drop NaN values before finding the nth value
    output_name : str, optional
        Name for the output metric, defaults to 'nth_{n}_{variable}_by_{sort_by}'
        
    Returns:
    --------
    Callable
        Function that retrieves the nth value from a MetricsPipe
    """
    def _nth(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Sort the dataframe
        sorted_df = df.sort_values(by=sort_by, ascending=ascending)
        
        # Drop NaN values if requested
        if dropna:
            sorted_df = sorted_df.dropna(subset=[variable])
        
        # Get the nth value
        try:
            result = sorted_df.iloc[n][variable]
        except IndexError:
            warnings.warn(f"Index {n} out of bounds for variable '{variable}'.")
            result = None
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"nth_{n}_{variable}_by_{sort_by}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _nth


# Statistical Metrics Functions
def Variance(variable: str, unbiased: bool = True, output_name: Optional[str] = None):
    """
    Calculate the variance of a column
    
    Parameters:
    -----------
    variable : str
        Column to calculate variance for
    unbiased : bool, default=True
        Whether to use the unbiased (sample) estimator
    output_name : str, optional
        Name for the output metric, defaults to 'var_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates variance from a MetricsPipe
    """
    def _variance(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the variance
        result = df[variable].var(ddof=1 if unbiased else 0)
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"var_{variable}"
        if not unbiased:
            metric_name = f"pop_{metric_name}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _variance


def StandardDeviation(variable: str, unbiased: bool = True, output_name: Optional[str] = None):
    """
    Calculate the standard deviation of a column
    
    Parameters:
    -----------
    variable : str
        Column to calculate standard deviation for
    unbiased : bool, default=True
        Whether to use the unbiased (sample) estimator
    output_name : str, optional
        Name for the output metric, defaults to 'std_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates standard deviation from a MetricsPipe
    """
    def _std_dev(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the standard deviation
        result = df[variable].std(ddof=1 if unbiased else 0)
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"std_{variable}"
        if not unbiased:
            metric_name = f"pop_{metric_name}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _std_dev


def CV(variable: str, unbiased: bool = True, output_name: Optional[str] = None):
    """
    Calculate the coefficient of variation of a column
    
    Parameters:
    -----------
    variable : str
        Column to calculate coefficient of variation for
    unbiased : bool, default=True
        Whether to use the unbiased standard deviation
    output_name : str, optional
        Name for the output metric, defaults to 'cv_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates coefficient of variation from a MetricsPipe
    """
    def _cv(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the mean and standard deviation
        mean = df[variable].mean()
        std = df[variable].std(ddof=1 if unbiased else 0)
        
        # Calculate the coefficient of variation, handling division by zero
        if mean == 0:
            warnings.warn(f"Division by zero encountered in CV calculation. Mean of '{variable}' is zero.")
            result = float('nan')
        else:
            result = std / mean
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"cv_{variable}"
        if not unbiased:
            metric_name = f"pop_{metric_name}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _cv


def Correlation(variable1: str, variable2: str, output_name: Optional[str] = None):
    """
    Calculate the Pearson correlation between two columns
    
    Parameters:
    -----------
    variable1 : str
        First column name
    variable2 : str
        Second column name
    output_name : str, optional
        Name for the output metric, defaults to 'corr_{variable1}_{variable2}'
        
    Returns:
    --------
    Callable
        Function that calculates correlation from a MetricsPipe
    """
    def _correlation(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the correlation
        result = df[variable1].corr(df[variable2])
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"corr_{variable1}_{variable2}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _correlation


def Cov(variable1: str, variable2: str, output_name: Optional[str] = None):
    """
    Calculate the covariance between two columns
    
    Parameters:
    -----------
    variable1 : str
        First column name
    variable2 : str
        Second column name
    output_name : str, optional
        Name for the output metric, defaults to 'cov_{variable1}_{variable2}'
        
    Returns:
    --------
    Callable
        Function that calculates covariance from a MetricsPipe
    """
    def _covariance(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the covariance
        result = df[variable1].cov(df[variable2])
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"cov_{variable1}_{variable2}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _covariance


# Additional aggregate functions
def Mean(variable: str, output_name: Optional[str] = None):
    """
    Calculate the mean of a column
    
    Parameters:
    -----------
    variable : str
        Column name to calculate mean for
    output_name : str, optional
        Name for the output metric, defaults to 'mean_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates mean from a MetricsPipe
    """
    def _mean(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the mean
        result = df[variable].mean()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"mean_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _mean


def Median(variable: str, output_name: Optional[str] = None):
    """
    Calculate the median of a column
    
    Parameters:
    -----------
    variable : str
        Column name to calculate median for
    output_name : str, optional
        Name for the output metric, defaults to 'median_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates median from a MetricsPipe
    """
    def _median(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the median
        result = df[variable].median()
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"median_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _median


def Percentile(variable: str, q: float, output_name: Optional[str] = None):
    """
    Calculate the specified percentile of a column
    
    Parameters:
    -----------
    variable : str
        Column name to calculate percentile for
    q : float
        Percentile to calculate (0-100)
    output_name : str, optional
        Name for the output metric, defaults to 'pct{q}_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates percentile from a MetricsPipe
    """
    def _percentile(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Calculate the percentile
        result = df[variable].quantile(q/100)
        
        # Generate output name if not provided
        metric_name = output_name if output_name else f"pct{q}_{variable}"
        
        # Store the metric
        new_pipe.metrics[metric_name] = result
        new_pipe.current_metric = metric_name
        
        return new_pipe
    
    return _percentile


# Pivot Table Functions
def PivotTable(
    index: Union[str, List[str]],
    columns: Optional[Union[str, List[str]]] = None,
    values: Optional[Union[str, List[str]]] = None,
    aggfunc: str = 'mean',
    fill_value: Optional[Any] = None,
    output_name: Optional[str] = None
):
    """
    Create a pivot table from the data
    
    Parameters:
    -----------
    index : str or List[str]
        Column(s) to use as index
    columns : str or List[str], optional
        Column(s) to use as columns
    values : str or List[str], optional
        Column(s) to aggregate
    aggfunc : str or Dict, default='mean'
        Aggregation function to use ('mean', 'sum', 'count', etc.)
    fill_value : Any, optional
        Value to replace missing values with
    output_name : str, optional
        Name for the output pivot table
        
    Returns:
    --------
    Callable
        Function that creates a pivot table from a MetricsPipe
    """
    def _pivot_table(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Create the pivot table
        pivot = pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
            fill_value=fill_value
        )
        
        # Generate output name if not provided
        if output_name:
            pivot_name = output_name
        else:
            index_str = '_'.join(index) if isinstance(index, list) else index
            if columns:
                columns_str = '_'.join(columns) if isinstance(columns, list) else columns
                pivot_name = f"pivot_{index_str}_by_{columns_str}"
            else:
                pivot_name = f"pivot_{index_str}"
        
        # Store the pivot table
        new_pipe.pivot_tables[pivot_name] = pivot
        new_pipe.current_metric = pivot_name
        
        return new_pipe
    
    return _pivot_table


def GroupBy(
    by: Union[str, List[str]],
    agg_dict: Dict[str, Union[str, List[str]]],
    output_name: Optional[str] = None
):
    """
    Group the data and apply aggregation functions
    
    Parameters:
    -----------
    by : str or List[str]
        Column(s) to group by
    agg_dict : Dict[str, Union[str, List[str]]]
        Dictionary mapping columns to aggregation functions
    output_name : str, optional
        Name for the output grouped data
        
    Returns:
    --------
    Callable
        Function that groups data from a MetricsPipe
    """
    def _group_by(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Group the data and apply aggregations
        grouped = df.groupby(by).agg(agg_dict).reset_index()
        
        # Generate output name if not provided
        if output_name:
            group_name = output_name
        else:
            by_str = '_'.join(by) if isinstance(by, list) else by
            group_name = f"grouped_by_{by_str}"
        
        # Store the result as a pivot table and update the data
        new_pipe.pivot_tables[group_name] = grouped
        new_pipe.data = grouped  # Update the data for subsequent operations
        new_pipe.current_metric = group_name
        
        return new_pipe
    
    return _group_by


def Filter(condition: Callable[[pd.DataFrame], pd.Series], output_name: Optional[str] = None):
    """
    Filter the dataframe based on a condition
    
    Parameters:
    -----------
    condition : Callable
        Function that takes a dataframe and returns a boolean mask
    output_name : str, optional
        Name for the output filtered data
        
    Returns:
    --------
    Callable
        Function that filters data from a MetricsPipe
    """
    def _filter(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Apply the filter condition
        mask = condition(df)
        filtered_df = df[mask]
        
        # Generate output name if not provided
        filter_name = output_name if output_name else "filtered_data"
        
        # Store the result as a pivot table and update the data
        new_pipe.pivot_tables[filter_name] = filtered_df
        new_pipe.data = filtered_df  # Update the data for subsequent operations
        new_pipe.current_metric = filter_name
        
        return new_pipe
    
    return _filter


# Helper functions for creating combined metrics
def CumulativeSum(variable: str, output_column: Optional[str] = None):
    """
    Calculate the cumulative sum of a column
    
    Parameters:
    -----------
    variable : str
        Column to calculate cumulative sum for
    output_column : str, optional
        Name for the output column, defaults to 'cum_sum_{variable}'
        
    Returns:
    --------
    Callable
        Function that calculates cumulative sum from a MetricsPipe
    """
    def _cumulative_sum(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Generate output column name if not provided
        col_name = output_column if output_column else f"cum_sum_{variable}"
        
        # Calculate the cumulative sum
        df[col_name] = df[variable].cumsum()
        
        # Store the result as a pivot table and update the data
        new_pipe.pivot_tables[col_name] = df
        new_pipe.data = df  # Update the data for subsequent operations
        new_pipe.current_metric = col_name
        
        return new_pipe
    
    return _cumulative_sum


def RollingMetric(
    variable: str,
    window: int,
    function: str = 'mean',
    min_periods: Optional[int] = None,
    center: bool = False,
    output_column: Optional[str] = None
):
    """
    Calculate a rolling metric on a column
    
    Parameters:
    -----------
    variable : str
        Column to calculate rolling metric for
    window : int
        Size of the rolling window
    function : str, default='mean'
        Function to apply to the rolling window ('mean', 'sum', 'std', etc.)
    min_periods : int, optional
        Minimum number of observations required
    center : bool, default=False
        Whether to set the labels at the center of the window
    output_column : str, optional
        Name for the output column
        
    Returns:
    --------
    Callable
        Function that calculates rolling metric from a MetricsPipe
    """
    def _rolling_metric(pipe):
        if pipe.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        new_pipe = pipe.copy()
        df = new_pipe.data
        
        # Create the rolling window
        rolling = df[variable].rolling(window=window, min_periods=min_periods, center=center)
        
        # Apply the specified function
        if function == 'mean':
            result = rolling.mean()
        elif function == 'sum':
            result = rolling.sum()
        elif function == 'std':
            result = rolling.std()
        elif function == 'var':
            result = rolling.var()
        elif function == 'min':
            result = rolling.min()
        elif function == 'max':
            result = rolling.max()
        elif function == 'median':
            result = rolling.median()
        elif function == 'count':
            result = rolling.count()
        else:
            raise ValueError(f"Unsupported rolling function: {function}")
        
        # Generate output column name if not provided
        col_name = output_column if output_column else f"rolling_{function}_{window}_{variable}"
        
        # Add the result to the dataframe
        df[col_name] = result
        
        # Store the result as a pivot table and update the data
        new_pipe.pivot_tables[col_name] = df
        new_pipe.data = df  # Update the data for subsequent operations
        new_pipe.current_metric = col_name
        
        return new_pipe
    
    return _rolling_metric


# Execute and display functions
def Execute():
    """
    Execute the pipeline and return all calculated metrics
    
    Returns:
    --------
    Callable
        Function that returns all metrics from a MetricsPipe
    """
    def _execute(pipe):
        # Simply return the metrics
        return pipe.metrics
    
    return _execute


def ShowPivot(pivot_name: Optional[str] = None):
    """
    Show a specific pivot table or the last created one
    
    Parameters:
    -----------
    pivot_name : str, optional
        Name of the pivot table to show
        
    Returns:
    --------
    Callable
        Function that returns a pivot table from a MetricsPipe
    """
    def _show_pivot(pipe):
        if not pipe.pivot_tables:
            raise ValueError("No pivot tables found in the pipeline.")
        
        # Determine which pivot table to show
        if pivot_name:
            if pivot_name not in pipe.pivot_tables:
                raise ValueError(f"Pivot table '{pivot_name}' not found.")
            return pipe.pivot_tables[pivot_name]
        else:
            # Show the most recent pivot table
            return pipe.pivot_tables[next(reversed(pipe.pivot_tables))]
    
    return _show_pivot


def ShowDataFrame():
    """
    Show the current dataframe
    
    Returns:
    --------
    Callable
        Function that returns the dataframe from a MetricsPipe
    """
    def _show_df(pipe):
        if pipe.data is None:
            raise ValueError("No data found in the pipeline.")
        
        return pipe.data
    
    return _show_df