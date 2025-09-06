"""
Chart Template Utilities

This module provides common utilities for chart template generation,
including field mapping, validation, and schema adaptation functions.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import re
from difflib import SequenceMatcher

logger = logging.getLogger("lexy-ai-service")


class ChartTemplateUtils:
    """Utility class for chart template operations"""
    
    # Common field patterns for automatic mapping
    FIELD_PATTERNS = {
        'date': ['date', 'time', 'timestamp', 'created', 'updated', 'modified', 'created_at', 'updated_at'],
        'sales': ['sales', 'revenue', 'amount', 'value', 'income', 'earnings', 'total'],
        'region': ['region', 'area', 'location', 'country', 'state', 'province', 'city', 'zone'],
        'product': ['product', 'item', 'category', 'type', 'class', 'group', 'division'],
        'count': ['count', 'number', 'quantity', 'total', 'sum', 'amount', 'qty'],
        'profit': ['profit', 'margin', 'income', 'earnings', 'gain', 'return'],
        'customer': ['customer', 'client', 'user', 'buyer', 'purchaser'],
        'order': ['order', 'transaction', 'purchase', 'sale', 'deal'],
        'price': ['price', 'cost', 'fee', 'charge', 'rate', 'unit_price'],
        'status': ['status', 'state', 'condition', 'phase', 'stage'],
        'id': ['id', 'key', 'identifier', 'code', 'ref', 'reference']
    }
    
    @classmethod
    def create_field_mapping(
        cls, 
        template_fields: List[str], 
        new_columns: List[str],
        strategy: str = "auto"
    ) -> Dict[str, str]:
        """Create field mapping between template fields and new columns
        
        Args:
            template_fields: List of field names from the template
            new_columns: List of column names from new data
            strategy: Mapping strategy ('auto', 'exact', 'fuzzy', 'semantic')
            
        Returns:
            Dict mapping template fields to new column names
        """
        field_mapping = {}
        
        for template_field in template_fields:
            if strategy == "exact":
                match = cls._find_exact_match(template_field, new_columns)
            elif strategy == "fuzzy":
                match = cls._find_fuzzy_match(template_field, new_columns)
            elif strategy == "semantic":
                match = cls._find_semantic_match(template_field, new_columns)
            else:  # auto - try all strategies
                match = cls._find_best_match(template_field, new_columns)
            
            if match:
                field_mapping[template_field] = match
        
        return field_mapping
    
    @classmethod
    def _find_exact_match(cls, template_field: str, new_columns: List[str]) -> Optional[str]:
        """Find exact case-insensitive match"""
        template_lower = template_field.lower()
        for col in new_columns:
            if col.lower() == template_lower:
                return col
        return None
    
    @classmethod
    def _find_fuzzy_match(cls, template_field: str, new_columns: List[str], threshold: float = 0.6) -> Optional[str]:
        """Find fuzzy match using string similarity"""
        best_match = None
        best_ratio = 0
        
        for col in new_columns:
            ratio = SequenceMatcher(None, template_field.lower(), col.lower()).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = col
        
        return best_match
    
    @classmethod
    def _find_semantic_match(cls, template_field: str, new_columns: List[str]) -> Optional[str]:
        """Find semantic match using field patterns"""
        template_lower = template_field.lower()
        
        # Find matching pattern
        for pattern, keywords in cls.FIELD_PATTERNS.items():
            if pattern in template_lower:
                # Look for columns containing any of the keywords
                for col in new_columns:
                    col_lower = col.lower()
                    for keyword in keywords:
                        if keyword in col_lower:
                            return col
        
        return None
    
    @classmethod
    def _find_best_match(cls, template_field: str, new_columns: List[str]) -> Optional[str]:
        """Find best match using all strategies"""
        # Try exact match first
        match = cls._find_exact_match(template_field, new_columns)
        if match:
            return match
        
        # Try semantic match
        match = cls._find_semantic_match(template_field, new_columns)
        if match:
            return match
        
        # Try fuzzy match
        match = cls._find_fuzzy_match(template_field, new_columns)
        if match:
            return match
        
        # Try partial match as last resort
        template_lower = template_field.lower()
        for col in new_columns:
            col_lower = col.lower()
            if template_lower in col_lower or col_lower in template_lower:
                return col
        
        return None
    
    @classmethod
    def validate_field_mapping(
        cls, 
        field_mapping: Dict[str, str], 
        template_fields: List[str], 
        new_columns: List[str]
    ) -> Tuple[bool, List[str]]:
        """Validate field mapping for completeness and correctness
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check if all template fields are mapped
        unmapped_fields = set(template_fields) - set(field_mapping.keys())
        if unmapped_fields:
            errors.append(f"Unmapped template fields: {list(unmapped_fields)}")
        
        # Check if all mapped fields exist in new columns
        invalid_mappings = []
        for template_field, new_field in field_mapping.items():
            if new_field not in new_columns:
                invalid_mappings.append(f"{template_field} -> {new_field}")
        
        if invalid_mappings:
            errors.append(f"Invalid field mappings: {invalid_mappings}")
        
        # Check for duplicate mappings
        mapped_values = list(field_mapping.values())
        duplicates = [v for v in set(mapped_values) if mapped_values.count(v) > 1]
        if duplicates:
            errors.append(f"Duplicate field mappings: {duplicates}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def suggest_field_mappings(
        cls, 
        template_fields: List[str], 
        new_columns: List[str]
    ) -> Dict[str, List[str]]:
        """Suggest possible field mappings for each template field
        
        Returns:
            Dict mapping template fields to lists of suggested new columns
        """
        suggestions = {}
        
        for template_field in template_fields:
            field_suggestions = []
            
            # Add exact matches
            exact_match = cls._find_exact_match(template_field, new_columns)
            if exact_match:
                field_suggestions.append(exact_match)
            
            # Add semantic matches
            semantic_matches = []
            template_lower = template_field.lower()
            for pattern, keywords in cls.FIELD_PATTERNS.items():
                if pattern in template_lower:
                    for col in new_columns:
                        col_lower = col.lower()
                        for keyword in keywords:
                            if keyword in col_lower and col not in field_suggestions:
                                semantic_matches.append(col)
            
            field_suggestions.extend(semantic_matches)
            
            # Add fuzzy matches
            fuzzy_matches = []
            for col in new_columns:
                if col not in field_suggestions:
                    ratio = SequenceMatcher(None, template_field.lower(), col.lower()).ratio()
                    if ratio >= 0.5:  # Lower threshold for suggestions
                        fuzzy_matches.append((col, ratio))
            
            # Sort by similarity and add top matches
            fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
            field_suggestions.extend([col for col, _ in fuzzy_matches[:3]])
            
            suggestions[template_field] = field_suggestions[:5]  # Limit to 5 suggestions
        
        return suggestions
    
    @classmethod
    def extract_fields_from_vega_schema(cls, schema: Dict[str, Any]) -> List[str]:
        """Extract field names from Vega-Lite schema"""
        fields = []
        
        def extract_from_encoding(encoding):
            if isinstance(encoding, dict):
                for key, value in encoding.items():
                    if isinstance(value, dict) and "field" in value:
                        fields.append(value["field"])
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict) and "field" in item:
                                fields.append(item["field"])
        
        # Extract from main encoding
        if "encoding" in schema:
            extract_from_encoding(schema["encoding"])
        
        # Extract from transform operations
        if "transform" in schema:
            for transform in schema["transform"]:
                if "fold" in transform:
                    fields.extend(transform["fold"])
        
        return list(set(fields))
    
    @classmethod
    def extract_fields_from_plotly_config(cls, config: Dict[str, Any]) -> List[str]:
        """Extract field names from Plotly config"""
        fields = []
        
        if "data" in config and isinstance(config["data"], list):
            for trace in config["data"]:
                if isinstance(trace, dict):
                    field_keys = ["x", "y", "z", "labels", "values", "text", "color", "size"]
                    for key in field_keys:
                        if key in trace and isinstance(trace[key], str):
                            fields.append(trace[key])
        
        return list(set(fields))
    
    @classmethod
    def extract_fields_from_powerbi_config(cls, config: Dict[str, Any]) -> List[str]:
        """Extract field names from PowerBI config"""
        fields = []
        
        if "dataRoles" in config:
            for role_name, role_data in config["dataRoles"].items():
                if isinstance(role_data, list):
                    for role_item in role_data:
                        if isinstance(role_item, dict) and "field" in role_item:
                            fields.append(role_item["field"])
        
        return list(set(fields))
    
    @classmethod
    def normalize_field_name(cls, field_name: str) -> str:
        """Normalize field name for comparison"""
        # Convert to lowercase and replace common separators
        normalized = field_name.lower()
        normalized = re.sub(r'[_\-\s]+', '_', normalized)
        return normalized
    
    @classmethod
    def calculate_field_similarity(cls, field1: str, field2: str) -> float:
        """Calculate similarity between two field names"""
        norm1 = cls.normalize_field_name(field1)
        norm2 = cls.normalize_field_name(field2)
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    @classmethod
    def create_mapping_report(
        cls, 
        field_mapping: Dict[str, str], 
        template_fields: List[str], 
        new_columns: List[str]
    ) -> Dict[str, Any]:
        """Create a detailed report of the field mapping"""
        is_valid, errors = cls.validate_field_mapping(field_mapping, template_fields, new_columns)
        
        # Calculate mapping statistics
        mapped_count = len(field_mapping)
        total_template_fields = len(template_fields)
        mapping_coverage = mapped_count / total_template_fields if total_template_fields > 0 else 0
        
        # Calculate average similarity
        similarities = []
        for template_field, new_field in field_mapping.items():
            similarity = cls.calculate_field_similarity(template_field, new_field)
            similarities.append(similarity)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "statistics": {
                "mapped_fields": mapped_count,
                "total_template_fields": total_template_fields,
                "mapping_coverage": mapping_coverage,
                "average_similarity": avg_similarity,
                "unmapped_fields": list(set(template_fields) - set(field_mapping.keys()))
            },
            "mapping_details": {
                template_field: {
                    "mapped_to": new_field,
                    "similarity": cls.calculate_field_similarity(template_field, new_field)
                }
                for template_field, new_field in field_mapping.items()
            }
        }


def create_field_mapping_interactive(
    template_fields: List[str], 
    new_columns: List[str]
) -> Dict[str, str]:
    """Create field mapping interactively (for CLI tools)"""
    utils = ChartTemplateUtils()
    field_mapping = {}
    
    print("Field Mapping Assistant")
    print("=" * 30)
    print()
    
    for template_field in template_fields:
        print(f"Template field: '{template_field}'")
        
        # Get suggestions
        suggestions = utils.suggest_field_mappings([template_field], new_columns)
        field_suggestions = suggestions.get(template_field, [])
        
        if field_suggestions:
            print("Suggestions:")
            for i, suggestion in enumerate(field_suggestions, 1):
                similarity = utils.calculate_field_similarity(template_field, suggestion)
                print(f"  {i}. {suggestion} (similarity: {similarity:.2f})")
        
        print("Available columns:")
        for i, col in enumerate(new_columns, 1):
            print(f"  {i}. {col}")
        
        while True:
            try:
                choice = input(f"Choose mapping for '{template_field}' (number or name, 'skip' to skip): ").strip()
                
                if choice.lower() == 'skip':
                    break
                
                # Try to parse as number
                try:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(new_columns):
                        field_mapping[template_field] = new_columns[choice_num - 1]
                        break
                except ValueError:
                    pass
                
                # Try to parse as column name
                if choice in new_columns:
                    field_mapping[template_field] = choice
                    break
                
                print("Invalid choice. Please try again.")
                
            except KeyboardInterrupt:
                print("\nMapping cancelled.")
                return field_mapping
        
        print()
    
    return field_mapping


# Example usage
if __name__ == "__main__":
    # Example usage of the utilities
    template_fields = ["Date", "Sales", "Region"]
    new_columns = ["timestamp", "revenue", "area", "category"]
    
    utils = ChartTemplateUtils()
    
    # Create automatic mapping
    mapping = utils.create_field_mapping(template_fields, new_columns)
    print("Automatic mapping:", mapping)
    
    # Validate mapping
    is_valid, errors = utils.validate_field_mapping(mapping, template_fields, new_columns)
    print("Valid:", is_valid)
    if errors:
        print("Errors:", errors)
    
    # Get suggestions
    suggestions = utils.suggest_field_mappings(template_fields, new_columns)
    print("Suggestions:", suggestions)
    
    # Create mapping report
    report = utils.create_mapping_report(mapping, template_fields, new_columns)
    print("Report:", report)
