"""
Base Pipe Class for Unified ML Tools Interface

This module provides a unified base class for all pipeline-style ML tools,
ensuring consistent interface across different analysis types.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, List
import pandas as pd


class BasePipe(ABC):
    """
    Base pipeline class that provides a unified interface for all ML tools.
    
    This abstract base class defines the common interface that all specific
    pipe classes must implement, ensuring consistency across different
    analysis types.
    """
    
    def __init__(self, data=None):
        """
        Initialize the base pipe with optional data.
        
        Parameters:
        -----------
        data : pd.DataFrame, optional
            The input data for analysis
        """
        self.data = data
        self._initialize_results()
    
    @abstractmethod
    def _initialize_results(self):
        """
        Initialize the results storage for the specific pipe type.
        This method must be implemented by each subclass.
        """
        pass
    
    def __or__(self, other):
        """
        Enable the | (pipe) operator for function composition.
        
        Parameters:
        -----------
        other : callable
            The function to apply to this pipe
            
        Returns:
        --------
        The result of applying the function to this pipe
            
        Raises:
        -------
        ValueError
            If other is not callable
        """
        if callable(other):
            return other(self)
        raise ValueError(f"Cannot pipe {self.__class__.__name__} to {type(other)}")
    
    def copy(self):
        """
        Create a shallow copy with deep copy of data.
        
        Returns:
        --------
        A copy of this pipe instance
        """
        new_pipe = self.__class__()
        if self.data is not None:
            new_pipe.data = self.data.copy()
        new_pipe._copy_results(self)
        return new_pipe
    
    @abstractmethod
    def _copy_results(self, source_pipe):
        """
        Copy results from source pipe to this pipe.
        This method must be implemented by each subclass.
        
        Parameters:
        -----------
        source_pipe : BasePipe
            The source pipe to copy results from
        """
        pass
    
    @classmethod
    def from_dataframe(cls, df):
        """
        Create a pipe instance from a dataframe.
        
        Parameters:
        -----------
        df : pd.DataFrame
            The input dataframe
            
        Returns:
        --------
        An instance of the pipe class with the dataframe loaded
        """
        pipe = cls()
        pipe.data = df.copy()
        return pipe
    
    def to_df(self, **kwargs) -> pd.DataFrame:
        """
        Convert the analysis results to a DataFrame by merging state into original data.
        
        This method provides a unified interface that merges pipeline state into
        new columns of the original dataframe, allowing each pipeline to run
        independently and produce a single combined result.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments specific to each pipe type
            
        Returns:
        --------
        pd.DataFrame
            Original dataframe with pipeline state merged as new columns
            
        Raises:
        -------
        ValueError
            If no analysis has been performed or no data is available
        """
        if self.data is None:
            raise ValueError("No data found. Data must be provided when creating the pipeline.")
        
        if not self._has_results():
            raise ValueError("No analysis has been performed. Run some analysis first.")
        
        # Start with a copy of the original data
        result_df = self.data.copy()
        
        # Merge the pipeline state into new columns
        result_df = self.merge_to_df(result_df, **kwargs)
        
        return result_df
    
    @abstractmethod
    def merge_to_df(self, base_df: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Merge pipeline state into the base dataframe as new columns.
        
        This method should be implemented by each subclass to handle their
        specific state and merge it into the base dataframe.
        
        Parameters:
        -----------
        base_df : pd.DataFrame
            The base dataframe to merge state into
        **kwargs : dict
            Additional arguments specific to each pipe type
            
        Returns:
        --------
        pd.DataFrame
            Base dataframe with pipeline state merged as new columns
        """
        pass
    
    @abstractmethod
    def _has_results(self) -> bool:
        """
        Check if the pipeline has any results to merge.
        
        Returns:
        --------
        bool
            True if the pipeline has results, False otherwise
        """
        pass
    
    def get_data(self) -> Optional[pd.DataFrame]:
        """
        Get the current data.
        
        Returns:
        --------
        pd.DataFrame or None
            The current data
        """
        return self.data
    
    def set_data(self, data: pd.DataFrame):
        """
        Set the data for this pipe.
        
        Parameters:
        -----------
        data : pd.DataFrame
            The data to set
        """
        self.data = data.copy() if data is not None else None
    
    @abstractmethod
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the analysis results.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments specific to each pipe type
            
        Returns:
        --------
        dict
            Summary of the analysis results
        """
        pass
    
    def has_data(self) -> bool:
        """
        Check if the pipe has data.
        
        Returns:
        --------
        bool
            True if data is available, False otherwise
        """
        return self.data is not None and not self.data.empty
    
    def get_data_info(self) -> Dict[str, Any]:
        """
        Get information about the current data.
        
        Returns:
        --------
        dict
            Information about the data including shape, columns, etc.
        """
        if not self.has_data():
            return {"has_data": False}
        
        return {
            "has_data": True,
            "shape": self.data.shape,
            "columns": list(self.data.columns),
            "dtypes": self.data.dtypes.to_dict(),
            "memory_usage": self.data.memory_usage(deep=True).sum()
        } 