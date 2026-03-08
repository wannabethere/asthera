"""
Dashboard data and config paths.
Centralizes paths for ingestion sources (data/) and config (app/config/dashboard/).
"""
from pathlib import Path

# Project root: app/config/dashboard_paths.py -> parent=config, parent.parent=app, parent.parent.parent=project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Ingestion source data
DATA_DIR = _PROJECT_ROOT / "data"
DASHBOARD_DATA_DIR = DATA_DIR / "dashboard"

# Dashboard config (taxonomy, control mapping, etc.)
DASHBOARD_CONFIG_DIR = Path(__file__).resolve().parent / "dashboard"

# Convenience paths for specific files
def get_templates_registry_path() -> Path:
    return DASHBOARD_DATA_DIR / "templates_registry.json"

def get_ld_templates_registry_path() -> Path:
    return DASHBOARD_DATA_DIR / "ld_templates_registry.json"

def get_dashboard_domain_taxonomy_path() -> Path:
    return DASHBOARD_CONFIG_DIR / "dashboard_domain_taxonomy.json"

def get_dashboard_domain_taxonomy_enriched_path() -> Path:
    return DASHBOARD_CONFIG_DIR / "dashboard_domain_taxonomy_enriched.json"

def get_metric_use_case_groups_path() -> Path:
    return DASHBOARD_CONFIG_DIR / "metric_use_case_groups.json"

def get_control_domain_taxonomy_path() -> Path:
    return DASHBOARD_CONFIG_DIR / "control_domain_taxonomy.json"


def get_taxonomy_keyword_index_path() -> Path:
    return DASHBOARD_CONFIG_DIR / "taxonomy_keyword_index.json"
