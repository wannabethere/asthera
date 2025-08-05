import re
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Union, Optional, Any, Tuple, Callable, Iterable
from collections.abc import Callable as CallableABC
import warnings
from abc import ABCMeta, abstractmethod
import asyncio
import aiohttp

# Assuming these imports exist in your codebase
from app.tools.mltools.base_pipe import BasePipe
from app.core.engine import Engine

logger = logging.getLogger(__name__)


class SelectMetadata:
    """
    Metadata container for column selection operations
    Simplified version of the original Metadata class
    """
    
    def __init__(self, targets: List[str] = None, categories: Dict[str, List] = None):
        self.targets = targets or []
        self.categories = categories or {}
    
    def get_categories(self, column_name: str) -> Optional[List]:
        """Get categories for a column if it's categorical"""
        return self.categories.get(column_name)


class SelectPipe(BasePipe):
    """
    A pipeline-style column selection tool that enables functional composition
    with selector-based interface similar to dplyr's select functionality.
    """
    
    def _initialize_results(self):
        """Initialize the results storage for selection operations"""
        self.selected_columns = []
        self.selection_history = []
        self.metadata = SelectMetadata()
        self.engine = None
        self.table_name = None
        self.sql_context = {}
    
    def _copy_results(self, source_pipe):
        """Copy results from source pipe to this pipe"""
        if hasattr(source_pipe, 'selected_columns'):
            self.selected_columns = source_pipe.selected_columns.copy()
        if hasattr(source_pipe, 'selection_history'):
            self.selection_history = source_pipe.selection_history.copy()
        if hasattr(source_pipe, 'metadata'):
            self.metadata = source_pipe.metadata
        if hasattr(source_pipe, 'engine'):
            self.engine = source_pipe.engine
        if hasattr(source_pipe, 'table_name'):
            self.table_name = source_pipe.table_name
        if hasattr(source_pipe, 'sql_context'):
            self.sql_context = source_pipe.sql_context.copy()
    
    @classmethod
    def from_engine(cls, engine: Engine, table_name: str, **kwargs):
        """
        Create a SelectPipe from an engine and table name
        
        Parameters:
        -----------
        engine : Engine
            The engine instance to use for data operations
        table_name : str
            Name of the table to select from
        **kwargs : dict
            Additional arguments passed to the constructor
            
        Returns:
        --------
        SelectPipe
            A new SelectPipe instance configured with the engine
        """
        pipe = cls(**kwargs)
        pipe.engine = engine
        pipe.table_name = table_name
        return pipe
    
    async def _fetch_dataframe_from_engine(self, columns: List[str] = None) -> pd.DataFrame:
        """
        Fetch DataFrame from engine using the selected columns
        
        Parameters:
        -----------
        columns : List[str], optional
            Specific columns to select. If None, uses self.selected_columns
            
        Returns:
        --------
        pd.DataFrame
            The fetched DataFrame
        """
        if not self.engine or not self.table_name:
            raise ValueError("Engine and table_name must be set to fetch data")
        
        cols_to_select = columns or self.selected_columns
        
        # Try to use direct DataFrame access first (for PandasEngine)
        if hasattr(self.engine, 'get_dataframe'):
            try:
                return self.engine.get_dataframe(self.table_name, cols_to_select)
            except Exception as e:
                logger.warning(f"Direct DataFrame access failed: {e}, falling back to SQL")
        
        # Fallback to SQL-based approach
        if not cols_to_select:
            # Select all columns if none specified
            sql = f"SELECT * FROM {self.table_name}"
        else:
            # Select specific columns
            columns_str = ", ".join(f'"{col}"' for col in cols_to_select)
            sql = f"SELECT {columns_str} FROM {self.table_name}"
        
        # Create a dummy session for async operations
        async with aiohttp.ClientSession() as session:
            success, result = await self.engine.execute_sql(
                sql=sql,
                session=session,
                dry_run=False,
                limit=None
            )
        
        if not success:
            raise RuntimeError(f"Failed to fetch data: {result.get('error', 'Unknown error')}")
        
        # Convert result to DataFrame
        data = result.get('data', [])
        columns = result.get('columns', [])
        
        return pd.DataFrame(data, columns=columns)
    
    def _get_available_columns(self) -> List[str]:
        """Get list of available columns from current data source"""
        if self.data is not None:
            return list(self.data.columns)
        elif self.engine and self.table_name:
            # Get table info from engine
            try:
                table_info = self.engine.get_table_info(self.table_name)
                if 'columns' in table_info:
                    return [col['name'] for col in table_info['columns']]
                else:
                    logger.warning("Could not get column info from engine")
                    return []
            except Exception as e:
                logger.warning(f"Failed to get column info: {e}")
                return []
        else:
            return []
    
    def to_df(self, fetch_data: bool = True) -> pd.DataFrame:
        """
        Convert the selection to a DataFrame
        
        Parameters:
        -----------
        fetch_data : bool, default=True
            Whether to fetch data if using an engine
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with selected columns
        """
        if self.data is not None:
            if self.selected_columns:
                return self.data[self.selected_columns]
            else:
                return self.data
        elif self.engine and fetch_data:
            # Fetch data from engine
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._fetch_dataframe_from_engine())
            finally:
                loop.close()
        else:
            raise ValueError("No data available. Either provide a DataFrame or set fetch_data=True with an engine.")
    
    def get_selected_columns(self) -> List[str]:
        """Get the list of currently selected columns"""
        return self.selected_columns.copy()
    
    def get_selection_summary(self) -> Dict[str, Any]:
        """Get a summary of the current selection"""
        available_cols = self._get_available_columns()
        
        return {
            "total_available_columns": len(available_cols),
            "selected_columns": len(self.selected_columns),
            "selected_column_names": self.selected_columns,
            "selection_history": self.selection_history,
            "data_source": "dataframe" if self.data is not None else "engine",
            "table_name": self.table_name
        }
    
    def get_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Get a summary of the pipe's current state and operations.
        This method satisfies the abstract method requirement from BasePipe.
        
        Parameters:
        -----------
        **kwargs : dict
            Additional arguments (not used in this implementation)
            
        Returns:
        --------
        Dict[str, Any]
            Summary of the pipe's current state
        """
        return self.get_selection_summary()


# Base Selector Classes
class Selector:
    """The base selector class"""

    __slots__ = ()
    _fields: Tuple[str, ...] = ()

    def __init_subclass__(cls):
        slots = []
        for base in cls.__mro__:
            if base is not object and hasattr(base, '__slots__'):
                slots.extend(reversed(base.__slots__))
        cls._fields = tuple(reversed(slots))

    def __repr__(self):
        name = type(self).__name__
        args = ",".join(repr(getattr(self, n)) for n in self._fields)
        return f"{name}({args})"

    def __eq__(self, other):
        return isinstance(other, type(self)) and all(
            getattr(self, name) == getattr(other, name) for name in self._fields
        )

    def __and__(self, other: 'SelectionType') -> 'Selector':
        selectors = []
        for part in [self, selector(other)]:
            if isinstance(part, and_):
                selectors.extend(part.selectors)
            else:
                selectors.append(part)
        return and_(*selectors)

    def __or__(self, other: 'SelectionType') -> 'Selector':
        selectors = []
        for part in [self, selector(other)]:
            if isinstance(part, or_):
                selectors.extend(part.selectors)
            else:
                selectors.append(part)
        return or_(*selectors)

    def __sub__(self, other: 'SelectionType') -> 'Selector':
        return self & ~selector(other)

    def __invert__(self) -> 'Selector':
        if isinstance(self, not_):
            return self.selector
        return not_(self)

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        """Whether the selector matches a given column"""
        raise NotImplementedError

    def select_columns(self, df: pd.DataFrame, metadata: SelectMetadata) -> List[str]:
        """Return a list of column names matching this selector."""
        return [
            c
            for c in df.columns
            if c not in metadata.targets and self.matches(df[c], metadata)
        ]


SelectionType = Union[str, Iterable[str], Callable[[pd.Series], bool], Selector]


def selector(obj: SelectionType) -> Selector:
    """Convert `obj` to a Selector"""
    if isinstance(obj, Selector):
        return obj
    elif isinstance(obj, str):
        return cols(obj)
    elif isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return cols(*obj)
    elif callable(obj):
        return where(obj)
    raise TypeError("Expected a str, list of strings, callable, or Selector")


# Logical Combination Selectors
class and_(Selector):
    """Select only columns selected by all selectors."""

    __slots__ = ("selectors",)

    def __init__(self, *selectors):
        self.selectors = tuple(selector(s) for s in selectors)

    def __repr__(self):
        args = " & ".join(repr(s) for s in self.selectors)
        return f"({args})"

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return all(s.matches(col, metadata) for s in self.selectors)


class or_(Selector):
    """Select all columns selected by at least one selector."""

    __slots__ = ("selectors",)

    def __init__(self, *selectors):
        self.selectors = tuple(selector(s) for s in selectors)

    def __repr__(self):
        args = " | ".join(repr(s) for s in self.selectors)
        return f"({args})"

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return any(s.matches(col, metadata) for s in self.selectors)


class not_(Selector):
    """Select all columns not selected by the wrapped selector."""

    __slots__ = ("selector",)

    def __init__(self, selector_obj):
        self.selector = selector(selector_obj)

    def __repr__(self):
        return f"~{self.selector!r}"

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return not self.selector.matches(col, metadata)


# Basic Selection Selectors
class everything(Selector):
    """Select all columns"""

    __slots__ = ()

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return True


class cols(Selector):
    """Select columns by name."""

    __slots__ = ("columns",)

    def __init__(self, *columns: str):
        self.columns = tuple(columns)

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return col.name in self.columns


# String-based Selectors
class contains(Selector):
    """Select all columns whose names contain a specific string."""

    __slots__ = ("pattern",)

    def __init__(self, pattern: str):
        self.pattern = pattern

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return self.pattern in str(col.name)


class endswith(Selector):
    """Select all columns whose names end with a specific string."""

    __slots__ = ("suffix",)

    def __init__(self, suffix: str):
        self.suffix = suffix

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return str(col.name).endswith(self.suffix)


class startswith(Selector):
    """Select all columns whose names start with a specific string."""

    __slots__ = ("prefix",)

    def __init__(self, prefix: str):
        self.prefix = prefix

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return str(col.name).startswith(self.prefix)


class matches(Selector):
    """Select all columns whose names match a specific regex."""

    __slots__ = ("pattern",)

    def __init__(self, pattern: str):
        self.pattern = pattern

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return re.search(self.pattern, str(col.name)) is not None


# Type-based Selectors
class has_type(Selector):
    """Select all columns matching a specified dtype."""

    __slots__ = ("dtype",)

    def __init__(self, dtype: Union[str, type, np.dtype]):
        if isinstance(dtype, str):
            self.dtype = dtype.lower()
        else:
            self.dtype = dtype

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        if metadata.get_categories(col.name) is not None:
            return False
        
        col_dtype = col.dtype
        
        if isinstance(self.dtype, str):
            return self.dtype in str(col_dtype).lower()
        elif isinstance(self.dtype, type):
            return isinstance(col_dtype.type(), self.dtype)
        else:
            return col_dtype == self.dtype


class _TypeSelector(Selector):
    __slots__ = ()
    _numpy_types: Tuple[type, ...] = ()
    _pandas_types: Tuple[str, ...] = ()

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        if metadata.get_categories(col.name) is not None:
            return False
        
        col_dtype = col.dtype
        dtype_str = str(col_dtype).lower()
        
        # Check pandas types
        for ptype in self._pandas_types:
            if ptype in dtype_str:
                return True
        
        # Check numpy types
        for ntype in self._numpy_types:
            if np.issubdtype(col_dtype, ntype):
                return True
        
        return False


class integer(_TypeSelector):
    """Select all integral columns"""
    __slots__ = ()
    _numpy_types = (np.integer,)
    _pandas_types = ('int',)


class floating(_TypeSelector):
    """Select all floating columns"""
    __slots__ = ()
    _numpy_types = (np.floating,)
    _pandas_types = ('float',)


class numeric(_TypeSelector):
    """Select all numeric columns"""
    __slots__ = ()
    _numpy_types = (np.number,)
    _pandas_types = ('int', 'float', 'complex')


class temporal(_TypeSelector):
    """Select all temporal columns"""
    __slots__ = ()
    _numpy_types = (np.datetime64, np.timedelta64)
    _pandas_types = ('datetime', 'timedelta', 'period')


class date(_TypeSelector):
    """Select all date columns"""
    __slots__ = ()
    _pandas_types = ('datetime64',)


class time(_TypeSelector):
    """Select all time columns"""
    __slots__ = ()
    _pandas_types = ('timedelta',)


class timestamp(_TypeSelector):
    """Select all timestamp columns"""
    __slots__ = ()
    _pandas_types = ('datetime',)


class string(_TypeSelector):
    """Select all string columns"""
    __slots__ = ()
    _numpy_types = (np.str_, np.unicode_)
    _pandas_types = ('object', 'string')

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        if metadata.get_categories(col.name) is not None:
            return False
        
        # For object columns, check if they contain strings
        if col.dtype == 'object':
            # Sample a few values to check if they're strings
            sample = col.dropna().head(10)
            if len(sample) > 0:
                return all(isinstance(x, str) for x in sample)
        
        return super().matches(col, metadata)


class nominal(Selector):
    """Select all nominal (string or categorical) columns"""

    __slots__ = ()

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        # Check if it's categorical
        if metadata.get_categories(col.name) is not None:
            return True
        
        # Check if it's string-like
        if col.dtype == 'object':
            sample = col.dropna().head(10)
            if len(sample) > 0:
                return all(isinstance(x, str) for x in sample)
        
        return 'string' in str(col.dtype).lower()


class categorical(Selector):
    """Select all categorical columns."""

    __slots__ = ()

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        # Check metadata first
        if metadata.get_categories(col.name) is not None:
            return True
        
        # Check pandas categorical
        return hasattr(col.dtype, 'categories')


class where(Selector):
    """Select all columns matching a specific predicate function."""

    __slots__ = ("predicate",)

    def __init__(self, predicate: Callable[[pd.Series], bool]):
        self.predicate = predicate

    def matches(self, col: pd.Series, metadata: SelectMetadata) -> bool:
        return self.predicate(col)


# Pipeline Selection Functions
def Select(*selectors: SelectionType):
    """
    Select columns using one or more selectors
    
    Parameters:
    -----------
    *selectors : SelectionType
        One or more selectors to apply
        
    Returns:
    --------
    Callable
        Function that applies selection to a SelectPipe
    """
    def _select(pipe: SelectPipe):
        new_pipe = pipe.copy()
        
        # Get available columns
        if new_pipe.data is not None:
            df = new_pipe.data
            available_columns = list(df.columns)
        else:
            available_columns = new_pipe._get_available_columns()
            # Create a dummy DataFrame with column info for selection
            df = pd.DataFrame({col: pd.Series(dtype='object') for col in available_columns})
        
        # Apply all selectors
        selected_columns = set()
        
        for sel in selectors:
            sel_obj = selector(sel)
            matches = sel_obj.select_columns(df, new_pipe.metadata)
            selected_columns.update(matches)
        
        # Update pipe state
        new_pipe.selected_columns = list(selected_columns)
        new_pipe.selection_history.append({
            'operation': 'select',
            'selectors': [str(selector(s)) for s in selectors],
            'selected_count': len(selected_columns)
        })
        
        # Update data if available
        if new_pipe.data is not None and selected_columns:
            new_pipe.data = new_pipe.data[list(selected_columns)]
        
        return new_pipe
    
    return _select


def Deselect(*selectors: SelectionType):
    """
    Remove columns using one or more selectors
    
    Parameters:
    -----------
    *selectors : SelectionType
        One or more selectors to apply for removal
        
    Returns:
    --------
    Callable
        Function that removes selected columns from a SelectPipe
    """
    def _deselect(pipe: SelectPipe):
        new_pipe = pipe.copy()
        
        # Get available columns
        if new_pipe.data is not None:
            df = new_pipe.data
            available_columns = list(df.columns)
        else:
            available_columns = new_pipe._get_available_columns()
            df = pd.DataFrame({col: pd.Series(dtype='object') for col in available_columns})
        
        # Find columns to remove
        columns_to_remove = set()
        
        for sel in selectors:
            sel_obj = selector(sel)
            matches = sel_obj.select_columns(df, new_pipe.metadata)
            columns_to_remove.update(matches)
        
        # Update selected columns (remove the matched ones)
        if new_pipe.selected_columns:
            new_pipe.selected_columns = [
                col for col in new_pipe.selected_columns 
                if col not in columns_to_remove
            ]
        else:
            # If no columns were selected, select all except the ones to remove
            new_pipe.selected_columns = [
                col for col in available_columns 
                if col not in columns_to_remove
            ]
        
        new_pipe.selection_history.append({
            'operation': 'deselect',
            'selectors': [str(selector(s)) for s in selectors],
            'removed_count': len(columns_to_remove)
        })
        
        # Update data if available
        if new_pipe.data is not None:
            new_pipe.data = new_pipe.data[new_pipe.selected_columns]
        
        return new_pipe
    
    return _deselect


def Rename(column_mapping: Dict[str, str]):
    """
    Rename columns
    
    Parameters:
    -----------
    column_mapping : Dict[str, str]
        Mapping of old_name -> new_name
        
    Returns:
    --------
    Callable
        Function that renames columns in a SelectPipe
    """
    def _rename(pipe: SelectPipe):
        new_pipe = pipe.copy()
        
        # Update selected columns
        new_pipe.selected_columns = [
            column_mapping.get(col, col) for col in new_pipe.selected_columns
        ]
        
        new_pipe.selection_history.append({
            'operation': 'rename',
            'mapping': column_mapping,
            'renamed_count': len(column_mapping)
        })
        
        # Update data if available
        if new_pipe.data is not None:
            new_pipe.data = new_pipe.data.rename(columns=column_mapping)
        
        return new_pipe
    
    return _rename


def Reorder(*column_order: str):
    """
    Reorder columns
    
    Parameters:
    -----------
    *column_order : str
        Column names in desired order
        
    Returns:
    --------
    Callable
        Function that reorders columns in a SelectPipe
    """
    def _reorder(pipe: SelectPipe):
        new_pipe = pipe.copy()
        
        # Reorder selected columns
        ordered_columns = []
        remaining_columns = new_pipe.selected_columns.copy()
        
        # Add columns in specified order
        for col in column_order:
            if col in remaining_columns:
                ordered_columns.append(col)
                remaining_columns.remove(col)
        
        # Add any remaining columns
        ordered_columns.extend(remaining_columns)
        
        new_pipe.selected_columns = ordered_columns
        new_pipe.selection_history.append({
            'operation': 'reorder',
            'order': list(column_order),
            'reordered_count': len(ordered_columns)
        })
        
        # Update data if available
        if new_pipe.data is not None:
            new_pipe.data = new_pipe.data[ordered_columns]
        
        return new_pipe
    
    return _reorder


def AddColumns(**new_columns: Any):
    """
    Add new computed columns
    
    Parameters:
    -----------
    **new_columns : Any
        Column_name=value pairs for new columns
        
    Returns:
    --------
    Callable
        Function that adds columns to a SelectPipe
    """
    def _add_columns(pipe: SelectPipe):
        new_pipe = pipe.copy()
        
        if new_pipe.data is None:
            raise ValueError("Cannot add columns without DataFrame data")
        
        # Add new columns to DataFrame
        for col_name, col_value in new_columns.items():
            if callable(col_value):
                # If value is a function, apply it to the DataFrame
                new_pipe.data[col_name] = col_value(new_pipe.data)
            else:
                # Otherwise, use the value directly
                new_pipe.data[col_name] = col_value
            
            # Add to selected columns if not already there
            if col_name not in new_pipe.selected_columns:
                new_pipe.selected_columns.append(col_name)
        
        new_pipe.selection_history.append({
            'operation': 'add_columns',
            'new_columns': list(new_columns.keys()),
            'added_count': len(new_columns)
        })
        
        return new_pipe
    
    return _add_columns


# Convenience functions for common selections
def select_numeric():
    """Select all numeric columns"""
    return Select(numeric())


def select_strings():
    """Select all string columns"""
    return Select(string())


def select_dates():
    """Select all date/datetime columns"""
    return Select(temporal())


def select_by_pattern(pattern: str):
    """Select columns matching a regex pattern"""
    return Select(matches(pattern))


def select_by_prefix(prefix: str):
    """Select columns starting with a prefix"""
    return Select(startswith(prefix))


def select_by_suffix(suffix: str):
    """Select columns ending with a suffix"""
    return Select(endswith(suffix))


def select_containing(substring: str):
    """Select columns containing a substring"""
    return Select(contains(substring))


# Example usage and helper functions
def preview_selection(df: pd.DataFrame, *selectors: SelectionType, metadata: SelectMetadata = None) -> Dict[str, Any]:
    """
    Preview what columns would be selected without creating a pipe
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame to preview selection on
    *selectors : SelectionType
        Selectors to apply
    metadata : SelectMetadata, optional
        Metadata for selection
        
    Returns:
    --------
    Dict[str, Any]
        Preview information
    """
    if metadata is None:
        metadata = SelectMetadata()
    
    selected_columns = set()
    
    for sel in selectors:
        sel_obj = selector(sel)
        matches = sel_obj.select_columns(df, metadata)
        selected_columns.update(matches)
    
    return {
        'total_columns': len(df.columns),
        'selected_columns': len(selected_columns),
        'selected_column_names': sorted(selected_columns),
        'unselected_columns': sorted(set(df.columns) - selected_columns),
        'selectors_applied': [str(selector(s)) for s in selectors]
    }