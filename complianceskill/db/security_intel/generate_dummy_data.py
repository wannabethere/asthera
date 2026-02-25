#!/usr/bin/env python3
"""
Generate dummy data for security intelligence tables using LLM.

This script uses LangChain LLM calls to generate realistic dummy data
for all security intelligence tables. Generates approximately 100 rows
per table.

Usage:
    # Generate data for all tables
    python generate_dummy_data.py

    # Generate data for specific phase
    python generate_dummy_data.py --phase 1

    # Generate specific number of rows
    python generate_dummy_data.py --rows 50

    # Use specific source database
    python generate_dummy_data.py --source cve_attack
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.settings import get_settings
from app.core.provider import get_llm
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent


def get_database_url(source: Optional[str] = None) -> str:
    """Get database URL for the specified source."""
    settings = get_settings()
    
    if source:
        db_config = settings.get_security_intel_db_config(source)
    else:
        db_config = settings.get_database_config()
    
    if db_config["type"] == "postgres":
        user = db_config.get("user") or "postgres"
        password = db_config.get("password") or "postgres"
        host = db_config.get("host") or "localhost"
        port = db_config.get("port", 5432)
        database = db_config.get("database") or "framework_kb"
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unsupported database type: {db_config['type']}")


def get_session(source: Optional[str] = None) -> Session:
    """Get SQLAlchemy session for the specified source."""
    db_url = get_database_url(source)
    engine = create_engine(db_url, echo=False)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()


def generate_with_llm(
    llm,
    prompt_template: str,
    num_rows: int,
    table_name: str,
    schema_description: str,
    examples: Optional[str] = None,
    **extra_kwargs
) -> List[Dict[str, Any]]:
    """
    Generate dummy data using LLM.
    
    Args:
        llm: LangChain LLM instance
        prompt_template: Template for the prompt
        num_rows: Number of rows to generate
        table_name: Name of the table
        schema_description: Description of the table schema
        examples: Optional examples of data format
        **extra_kwargs: Additional keyword arguments to pass to the prompt template
    
    Returns:
        List of dictionaries representing rows
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    full_prompt = prompt.format_messages(
        table_name=table_name,
        schema_description=schema_description,
        num_rows=num_rows,
        examples=examples or "",
        **extra_kwargs
    )
    
    logger.info(f"Generating {num_rows} rows for {table_name}...")
    
    content = None
    try:
        response = llm.invoke(full_prompt)
        content = response.content
        
        # Try to extract JSON from the response
        # LLM might wrap JSON in markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        data = json.loads(content)
        
        # Ensure it's a list
        if isinstance(data, dict):
            # If LLM returned a dict with a 'data' key
            if 'data' in data:
                data = data['data']
            elif 'rows' in data:
                data = data['rows']
            else:
                # Wrap in list
                data = [data]
        
        if not isinstance(data, list):
            raise ValueError(f"Expected list, got {type(data)}")
        
        logger.info(f"✓ Generated {len(data)} rows for {table_name}")
        return data
        
    except Exception as e:
        logger.error(f"Error generating data for {table_name}: {e}")
        if content:
            logger.error(f"Response content (first 500 chars): {content[:500]}")
        raise


# ============================================================================
# Data Generation Functions for Each Table
# ============================================================================

def generate_cve_attack_mapping(llm, num_rows: int, session: Session) -> None:
    """Generate CVE to ATT&CK technique mappings."""
    prompt_template = """Generate {num_rows} realistic CVE to MITRE ATT&CK technique mappings.

Table: {table_name}
Schema: {schema_description}

Requirements:
- cve_id: Format as CVE-YYYY-NNNN (e.g., CVE-2024-1234)
- attack_technique_id: Valid ATT&CK technique ID (e.g., T1003.001, T1078, T1055)
- attack_tactic: One of: Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact
- mapping_source: One of: mitre_official, ctid, manual, ai_inferred
- confidence_score: Float between 0.0 and 1.0
- notes: Brief description of the mapping relationship

Return as JSON array of objects. Each object should have all required fields.
{examples}
"""
    
    schema = """
    - cve_id (VARCHAR): CVE identifier
    - attack_technique_id (VARCHAR): ATT&CK technique ID
    - attack_tactic (VARCHAR): ATT&CK tactic name
    - mapping_source (VARCHAR): Source of mapping
    - confidence_score (FLOAT): Confidence 0.0-1.0
    - notes (TEXT): Optional notes
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "cve_attack_mapping", schema)
    
    # Insert data
    stmt = text("""
        INSERT INTO cve_attack_mapping 
        (cve_id, attack_technique_id, attack_tactic, mapping_source, confidence_score, notes)
        VALUES (:cve_id, :attack_technique_id, :attack_tactic, :mapping_source, :confidence_score, :notes)
        ON CONFLICT (cve_id, attack_technique_id) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "cve_id": row["cve_id"],
            "attack_technique_id": row.get("attack_technique_id"),
            "attack_tactic": row.get("attack_tactic"),
            "mapping_source": row.get("mapping_source", "ai_inferred"),
            "confidence_score": row.get("confidence_score", 0.7),
            "notes": row.get("notes")
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into cve_attack_mapping")


def generate_attack_technique_control_mapping(llm, num_rows: int, session: Session) -> None:
    """Generate ATT&CK technique to control mappings."""
    # Check if controls table exists and get valid control IDs
    controls_exist = False
    valid_control_ids = []
    
    try:
        check_stmt = text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'controls'
            )
        """)
        result = session.execute(check_stmt)
        controls_exist = result.scalar()
        
        if controls_exist:
            # Get valid control IDs from the controls table
            control_ids_stmt = text("SELECT id FROM controls LIMIT 100")
            valid_control_ids = [row[0] for row in session.execute(control_ids_stmt).fetchall()]
            logger.info(f"Found {len(valid_control_ids)} valid control IDs in controls table")
    except Exception as e:
        logger.warning(f"Could not check controls table: {e}")
    
    # Update prompt based on whether we have valid control IDs
    if controls_exist and valid_control_ids:
        control_id_instruction = f"control_id: Must be from this list of valid control IDs: {', '.join(valid_control_ids[:20])}"
        use_control_ids = True
    else:
        control_id_instruction = "control_id: Set to NULL (the controls table exists but we don't have valid control IDs to reference)"
        use_control_ids = False
    
    prompt_template = """Generate {num_rows} realistic ATT&CK technique to framework control mappings.

Table: {table_name}
Schema: {schema_description}

Requirements:
- attack_technique_id: Valid ATT&CK technique ID (e.g., T1003.001, T1078)
- {control_id_instruction}
- mitigation_effectiveness: One of: full, partial, low
- mapping_source: One of: manual, ai_generated, mitre_derived
- confidence_score: Float between 0.0 and 1.0
- notes: Brief description of how the control mitigates the technique

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - attack_technique_id (VARCHAR): ATT&CK technique ID
    - control_id (VARCHAR): Framework control ID (can be NULL)
    - mitigation_effectiveness (VARCHAR): full, partial, or low
    - mapping_source (VARCHAR): Source of mapping
    - confidence_score (FLOAT): Confidence 0.0-1.0
    - notes (TEXT): Optional notes
    """
    
    data = generate_with_llm(
        llm, 
        prompt_template, 
        num_rows, 
        "attack_technique_control_mapping", 
        schema,
        control_id_instruction=control_id_instruction
    )
    
    stmt = text("""
        INSERT INTO attack_technique_control_mapping
        (attack_technique_id, control_id, mitigation_effectiveness, mapping_source, confidence_score, notes)
        VALUES (:attack_technique_id, :control_id, :mitigation_effectiveness, :mapping_source, :confidence_score, :notes)
        ON CONFLICT (attack_technique_id, control_id) DO NOTHING
    """)
    
    inserted_count = 0
    for row in data:
        control_id = row.get("control_id")
        
        # If controls table exists, validate or set to NULL
        if controls_exist:
            if use_control_ids:
                # Only use control_id if it's in the valid list
                if control_id not in valid_control_ids:
                    logger.debug(f"Invalid control_id '{control_id}' not in controls table, setting to NULL")
                    control_id = None
            else:
                # No valid control IDs available, set to NULL
                control_id = None
        
        try:
            session.execute(stmt, {
                "attack_technique_id": row["attack_technique_id"],
                "control_id": control_id,
                "mitigation_effectiveness": row.get("mitigation_effectiveness", "partial"),
                "mapping_source": row.get("mapping_source", "ai_generated"),
                "confidence_score": row.get("confidence_score", 0.7),
                "notes": row.get("notes")
            })
            inserted_count += 1
        except Exception as e:
            # Log but continue - might be duplicate or constraint violation
            logger.warning(f"Failed to insert row (attack_technique_id={row.get('attack_technique_id')}, control_id={control_id}): {e}")
            continue
    
    session.commit()
    logger.info(f"✓ Inserted {inserted_count} rows into attack_technique_control_mapping")


def generate_cpe_dictionary(llm, num_rows: int, session: Session) -> None:
    """Generate CPE dictionary entries."""
    prompt_template = """Generate {num_rows} realistic CPE (Common Platform Enumeration) dictionary entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- cpe_uri: Full CPE URI in format: cpe:2.3:a:vendor:product:version:update:edition:language:sw_edition:target_sw:target_hw:other
- vendor: Software vendor name (lowercase, no spaces)
- product: Product name (lowercase, no spaces)
- version: Version number (e.g., 2.14.1, 1.0.0)
- cpe_title: Human-readable product name
- Other fields can be NULL or empty strings

Common vendors: apache, microsoft, oracle, google, mozilla, adobe, cisco, etc.
Common products: log4j, windows, java, chrome, firefox, flash, etc.

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - cpe_uri (VARCHAR): Full CPE URI (PRIMARY KEY)
    - vendor (VARCHAR): Vendor name
    - product (VARCHAR): Product name
    - version (VARCHAR): Version
    - update_version (VARCHAR): Optional update version
    - edition (VARCHAR): Optional edition
    - language (VARCHAR): Optional language
    - sw_edition (VARCHAR): Optional software edition
    - target_sw (VARCHAR): Optional target software
    - target_hw (VARCHAR): Optional target hardware
    - other (VARCHAR): Optional other attributes
    - cpe_title (TEXT): Human-readable name
    - deprecated (BOOLEAN): Default false
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "cpe_dictionary", schema)
    
    stmt = text("""
        INSERT INTO cpe_dictionary
        (cpe_uri, vendor, product, version, update_version, edition, language, 
         sw_edition, target_sw, target_hw, other, cpe_title, deprecated)
        VALUES (:cpe_uri, :vendor, :product, :version, :update_version, :edition, :language,
                :sw_edition, :target_sw, :target_hw, :other, :cpe_title, :deprecated)
        ON CONFLICT (cpe_uri) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "cpe_uri": row["cpe_uri"],
            "vendor": row.get("vendor"),
            "product": row.get("product"),
            "version": row.get("version"),
            "update_version": row.get("update_version"),
            "edition": row.get("edition"),
            "language": row.get("language"),
            "sw_edition": row.get("sw_edition"),
            "target_sw": row.get("target_sw"),
            "target_hw": row.get("target_hw"),
            "other": row.get("other"),
            "cpe_title": row.get("cpe_title", f"{row.get('vendor', '')} {row.get('product', '')} {row.get('version', '')}"),
            "deprecated": row.get("deprecated", False)
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into cpe_dictionary")


def generate_cve_cpe_affected(llm, num_rows: int, session: Session) -> None:
    """Generate CVE to CPE affected mappings."""
    # First, get existing CVEs and CPEs
    cve_stmt = text("SELECT DISTINCT cve_id FROM cve_attack_mapping LIMIT 50")
    cpe_stmt = text("SELECT cpe_uri FROM cpe_dictionary LIMIT 100")
    
    cves = [row[0] for row in session.execute(cve_stmt).fetchall()]
    cpes = [row[0] for row in session.execute(cpe_stmt).fetchall()]
    
    if not cves:
        logger.warning("No CVEs found. Generating CVE-CPE mappings will be limited.")
        cves = [f"CVE-2024-{i:04d}" for i in range(1000, 1100)]
    
    if not cpes:
        logger.warning("No CPEs found. Please generate CPE dictionary first.")
        return
    
    prompt_template = """Generate {num_rows} realistic CVE to CPE affected mappings.

Table: {table_name}
Schema: {schema_description}

Available CVEs (use these): {cve_list}
Available CPEs (use these): {cpe_list}

Requirements:
- cve_id: Must be from the available CVEs list
- cpe_uri: Must be from the available CPEs list
- version_start: Vulnerable from this version (e.g., "2.0.0")
- version_end: Vulnerable up to this version (NULL means all versions after start)
- version_start_including: Boolean, default true
- version_end_including: Boolean, default false

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - cve_id (VARCHAR): CVE identifier
    - cpe_uri (VARCHAR): CPE URI (references cpe_dictionary)
    - version_start (VARCHAR): Vulnerable from version
    - version_end (VARCHAR): Vulnerable to version (can be NULL)
    - version_start_including (BOOLEAN): Include start version
    - version_end_including (BOOLEAN): Include end version
    """
    
    data = generate_with_llm(
        llm, 
        prompt_template, 
        num_rows, 
        "cve_cpe_affected", 
        schema,
        examples=f"Available CVEs: {', '.join(cves[:10])}\nAvailable CPEs: {', '.join(cpes[:5])}",
        cve_list=', '.join(cves),
        cpe_list=', '.join(cpes)
    )
    
    stmt = text("""
        INSERT INTO cve_cpe_affected
        (cve_id, cpe_uri, version_start, version_end, version_start_including, version_end_including)
        VALUES (:cve_id, :cpe_uri, :version_start, :version_end, :version_start_including, :version_end_including)
        ON CONFLICT (cve_id, cpe_uri) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "cve_id": row["cve_id"],
            "cpe_uri": row["cpe_uri"],
            "version_start": row.get("version_start"),
            "version_end": row.get("version_end"),
            "version_start_including": row.get("version_start_including", True),
            "version_end_including": row.get("version_end_including", False)
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into cve_cpe_affected")


def generate_metasploit_modules(llm, num_rows: int, session: Session) -> None:
    """Generate Metasploit module entries."""
    prompt_template = """Generate {num_rows} realistic Metasploit Framework module entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- module_path: Path in Metasploit (e.g., exploit/windows/smb/ms17_010_eternalblue)
- module_type: One of: exploit, auxiliary, post, payload
- name: Module name
- fullname: Full module name
- description: Brief description
- author: Array of author names
- platform: Array of platforms (e.g., ["windows"], ["linux", "unix"])
- arch: Array of architectures (e.g., ["x86"], ["x64"], ["x86", "x64"])
- cve_references: Array of CVE IDs (e.g., ["CVE-2017-0144"])
- cwe_references: Array of CWE IDs (e.g., ["CWE-119"])
- rank: One of: excellent, great, good, normal, average, low, manual
- disclosure_date: Date in YYYY-MM-DD format
- check_available: Boolean
- targets: Array of target descriptions
- notes: Optional additional notes

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - module_path (VARCHAR): Path in Metasploit
    - module_type (VARCHAR): exploit, auxiliary, post, or payload
    - name (VARCHAR): Module name
    - fullname (VARCHAR): Full module name
    - description (TEXT): Description
    - author (VARCHAR[]): Array of authors
    - platform (VARCHAR[]): Array of platforms
    - arch (VARCHAR[]): Array of architectures
    - cve_references (VARCHAR[]): Array of CVE IDs
    - cwe_references (VARCHAR[]): Array of CWE IDs
    - rank (VARCHAR): Module rank
    - disclosure_date (DATE): Disclosure date
    - check_available (BOOLEAN): Can test without exploiting
    - targets (TEXT[]): Array of targets
    - notes (TEXT): Optional notes
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "metasploit_modules", schema)
    
    stmt = text("""
        INSERT INTO metasploit_modules
        (module_path, module_type, name, fullname, description, author, platform, arch,
         cve_references, cwe_references, rank, disclosure_date, check_available, targets, notes)
        VALUES (:module_path, :module_type, :name, :fullname, :description, :author, :platform, :arch,
                :cve_references, :cwe_references, :rank, :disclosure_date, :check_available, :targets, :notes)
        ON CONFLICT (module_path) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "module_path": row["module_path"],
            "module_type": row.get("module_type", "exploit"),
            "name": row.get("name"),
            "fullname": row.get("fullname", row.get("name")),
            "description": row.get("description"),
            "author": row.get("author", []),
            "platform": row.get("platform", []),
            "arch": row.get("arch", []),
            "cve_references": row.get("cve_references", []),
            "cwe_references": row.get("cwe_references", []),
            "rank": row.get("rank", "normal"),
            "disclosure_date": row.get("disclosure_date"),
            "check_available": row.get("check_available", False),
            "targets": row.get("targets", []),
            "notes": row.get("notes")
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into metasploit_modules")


def generate_nuclei_templates(llm, num_rows: int, session: Session) -> None:
    """Generate Nuclei template entries."""
    prompt_template = """Generate {num_rows} realistic Nuclei vulnerability detection template entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- template_id: Unique template identifier (e.g., CVE-2024-1234.yaml or unique ID)
- name: Template name
- severity: One of: info, low, medium, high, critical
- description: Brief description
- tags: Array of tags (e.g., ["cve", "rce", "log4j", "xss"])
- cve_references: Array of CVE IDs
- cwe_references: Array of CWE IDs
- template_path: Path in nuclei-templates repo
- author: Array of author names
- metadata: JSON object with template metadata
- classification: JSON object with classification data

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - template_id (VARCHAR): Unique template identifier
    - name (VARCHAR): Template name
    - severity (VARCHAR): info, low, medium, high, or critical
    - description (TEXT): Description
    - tags (VARCHAR[]): Array of tags
    - cve_references (VARCHAR[]): Array of CVE IDs
    - cwe_references (VARCHAR[]): Array of CWE IDs
    - template_path (VARCHAR): Path in repo
    - author (VARCHAR[]): Array of authors
    - metadata (JSONB): Template metadata
    - classification (JSONB): Classification data
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "nuclei_templates", schema)
    
    stmt = text("""
        INSERT INTO nuclei_templates
        (template_id, name, severity, description, tags, cve_references, cwe_references,
         template_path, author, metadata, classification)
        VALUES (:template_id, :name, :severity, :description, :tags, :cve_references, :cwe_references,
                :template_path, :author, :metadata::jsonb, :classification::jsonb)
        ON CONFLICT (template_id) DO NOTHING
    """)
    
    for row in data:
        metadata = row.get("metadata", {})
        classification = row.get("classification", {})
        
        session.execute(stmt, {
            "template_id": row["template_id"],
            "name": row.get("name"),
            "severity": row.get("severity", "medium"),
            "description": row.get("description"),
            "tags": row.get("tags", []),
            "cve_references": row.get("cve_references", []),
            "cwe_references": row.get("cwe_references", []),
            "template_path": row.get("template_path"),
            "author": row.get("author", []),
            "metadata": json.dumps(metadata),
            "classification": json.dumps(classification)
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into nuclei_templates")


def generate_exploit_db_index(llm, num_rows: int, session: Session) -> None:
    """Generate Exploit-DB index entries."""
    prompt_template = """Generate {num_rows} realistic Exploit-DB index entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- exploit_id: Unique EDB-ID (integer, e.g., 50001, 50002)
- title: Exploit title
- description: Brief description
- author: Author name
- platform: Platform (e.g., windows, linux, hardware, webapps)
- exploit_type: Type (e.g., remote, local, webapps, dos, shellcode)
- cve_id: CVE reference if available (can be NULL)
- date_published: Publication date (YYYY-MM-DD)
- date_added: Date added to Exploit-DB (YYYY-MM-DD)
- verified: Boolean
- codes: Array of code types
- exploit_url: URL to exploit
- application_url: URL to application (can be NULL)
- source_url: Original source URL (can be NULL)

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - exploit_id (INTEGER): EDB-ID (unique)
    - title (VARCHAR): Exploit title
    - description (TEXT): Description
    - author (VARCHAR): Author name
    - platform (VARCHAR): Platform
    - exploit_type (VARCHAR): Type of exploit
    - cve_id (VARCHAR): CVE reference (optional)
    - date_published (DATE): Publication date
    - date_added (DATE): Date added
    - verified (BOOLEAN): Is verified
    - codes (VARCHAR[]): Array of code types
    - exploit_url (VARCHAR): URL to exploit
    - application_url (VARCHAR): Application URL (optional)
    - source_url (VARCHAR): Source URL (optional)
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "exploit_db_index", schema)
    
    stmt = text("""
        INSERT INTO exploit_db_index
        (exploit_id, title, description, author, platform, exploit_type, cve_id,
         date_published, date_added, verified, codes, exploit_url, application_url, source_url)
        VALUES (:exploit_id, :title, :description, :author, :platform, :exploit_type, :cve_id,
                :date_published, :date_added, :verified, :codes, :exploit_url, :application_url, :source_url)
        ON CONFLICT (exploit_id) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "exploit_id": row["exploit_id"],
            "title": row.get("title"),
            "description": row.get("description"),
            "author": row.get("author"),
            "platform": row.get("platform", "linux"),
            "exploit_type": row.get("exploit_type", "remote"),
            "cve_id": row.get("cve_id"),
            "date_published": row.get("date_published"),
            "date_added": row.get("date_added"),
            "verified": row.get("verified", False),
            "codes": row.get("codes", []),
            "exploit_url": row.get("exploit_url", f"https://www.exploit-db.com/exploits/{row['exploit_id']}"),
            "application_url": row.get("application_url"),
            "source_url": row.get("source_url")
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into exploit_db_index")


def generate_cis_benchmark_rules(llm, num_rows: int, session: Session) -> None:
    """Generate CIS Benchmark rules."""
    prompt_template = """Generate {num_rows} realistic CIS Benchmark rule entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- benchmark_id: CIS Benchmark ID (e.g., CIS_Ubuntu_Linux_22.04, CIS_Windows_Server_2019)
- rule_number: Rule number (e.g., 1.1.1.1, 2.2.1)
- title: Rule title
- description: Rule description
- rationale: Why this rule is important
- remediation: How to fix
- audit_procedure: How to audit
- level: 1 or 2 (CIS Level)
- profile: Server, Workstation, Level_1, or Level_2
- control_id: Framework control ID (can be NULL)
- attack_techniques: Array of ATT&CK techniques this mitigates
- compliance_frameworks: Array of additional framework mappings

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - benchmark_id (VARCHAR): CIS Benchmark identifier
    - rule_number (VARCHAR): Rule number
    - title (VARCHAR): Rule title
    - description (TEXT): Description
    - rationale (TEXT): Rationale
    - remediation (TEXT): Remediation steps
    - audit_procedure (TEXT): Audit procedure
    - level (INTEGER): CIS Level (1 or 2)
    - profile (VARCHAR): Profile type
    - control_id (VARCHAR): Framework control ID (optional)
    - attack_techniques (VARCHAR[]): Array of ATT&CK techniques
    - compliance_frameworks (VARCHAR[]): Array of framework names
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "cis_benchmark_rules", schema)
    
    stmt = text("""
        INSERT INTO cis_benchmark_rules
        (benchmark_id, rule_number, title, description, rationale, remediation, audit_procedure,
         level, profile, control_id, attack_techniques, compliance_frameworks)
        VALUES (:benchmark_id, :rule_number, :title, :description, :rationale, :remediation, :audit_procedure,
                :level, :profile, :control_id, :attack_techniques, :compliance_frameworks)
        ON CONFLICT (benchmark_id, rule_number) DO NOTHING
    """)
    
    for row in data:
        session.execute(stmt, {
            "benchmark_id": row["benchmark_id"],
            "rule_number": row["rule_number"],
            "title": row.get("title"),
            "description": row.get("description"),
            "rationale": row.get("rationale"),
            "remediation": row.get("remediation"),
            "audit_procedure": row.get("audit_procedure"),
            "level": row.get("level", 1),
            "profile": row.get("profile", "Server"),
            "control_id": row.get("control_id"),
            "attack_techniques": row.get("attack_techniques", []),
            "compliance_frameworks": row.get("compliance_frameworks", [])
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into cis_benchmark_rules")


def generate_sigma_rules(llm, num_rows: int, session: Session) -> None:
    """Generate Sigma detection rule entries."""
    prompt_template = """Generate {num_rows} realistic Sigma detection rule entries.

Table: {table_name}
Schema: {schema_description}

Requirements:
- rule_id: Unique rule identifier (UUID format or unique string)
- title: Rule title
- description: Rule description
- status: One of: stable, test, experimental
- level: One of: low, medium, high, critical
- logsource: JSON object with log source config (e.g., {{"product": "windows", "service": "sysmon", "category": "process_creation"}})
- detection: JSON object with detection logic
- falsepositives: Array of known false positives
- attack_technique_refs: Array of ATT&CK technique IDs
- tags: Array of additional tags
- author: Author name
- date: Creation date (YYYY-MM-DD)
- modified: Last modification date (YYYY-MM-DD)
- rule_path: Path in sigma repo

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - rule_id (VARCHAR): Unique rule identifier
    - title (VARCHAR): Rule title
    - description (TEXT): Description
    - status (VARCHAR): stable, test, or experimental
    - level (VARCHAR): low, medium, high, or critical
    - logsource (JSONB): Log source configuration
    - detection (JSONB): Detection logic
    - falsepositives (TEXT[]): Array of false positives
    - attack_technique_refs (VARCHAR[]): Array of ATT&CK techniques
    - tags (VARCHAR[]): Array of tags
    - author (VARCHAR): Author name
    - date (DATE): Creation date
    - modified (DATE): Modification date
    - rule_path (VARCHAR): Path in repo
    """
    
    data = generate_with_llm(llm, prompt_template, num_rows, "sigma_rules", schema)
    
    stmt = text("""
        INSERT INTO sigma_rules
        (rule_id, title, description, status, level, logsource, detection, falsepositives,
         attack_technique_refs, tags, author, date, modified, rule_path)
        VALUES (:rule_id, :title, :description, :status, :level, :logsource::jsonb, :detection::jsonb, :falsepositives,
                :attack_technique_refs, :tags, :author, :date, :modified, :rule_path)
        ON CONFLICT (rule_id) DO NOTHING
    """)
    
    for row in data:
        logsource = row.get("logsource", {})
        detection = row.get("detection", {})
        
        session.execute(stmt, {
            "rule_id": row["rule_id"],
            "title": row.get("title"),
            "description": row.get("description"),
            "status": row.get("status", "stable"),
            "level": row.get("level", "medium"),
            "logsource": json.dumps(logsource),
            "detection": json.dumps(detection),
            "falsepositives": row.get("falsepositives", []),
            "attack_technique_refs": row.get("attack_technique_refs", []),
            "tags": row.get("tags", []),
            "author": row.get("author"),
            "date": row.get("date"),
            "modified": row.get("modified", row.get("date")),
            "rule_path": row.get("rule_path")
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into sigma_rules")


def generate_cve_cache(llm, num_rows: int, session: Session) -> None:
    """Generate CVE cache entries."""
    # Get existing CVEs
    cve_stmt = text("SELECT DISTINCT cve_id FROM cve_attack_mapping LIMIT 50")
    cves = [row[0] for row in session.execute(cve_stmt).fetchall()]
    
    if not cves:
        cves = [f"CVE-2024-{i:04d}" for i in range(1000, 1100)]
    
    prompt_template = """Generate {num_rows} realistic CVE cache entries.

Table: {table_name}
Schema: {schema_description}

Available CVEs (use these): {cve_list}

Requirements:
- cve_id: Must be from the available CVEs list
- nvd_data: JSON object with NVD API response data (e.g., {{"cvss": {{"v3": {{"score": 7.5}}}}, "description": "..."}})
- epss_data: JSON object with EPSS score data (e.g., {{"epss": 0.75, "percentile": 95.0}})
- kev_data: JSON object with CISA KEV data (e.g., {{"kev": true, "dateAdded": "2024-01-01"}})
- expires_at: Future timestamp (e.g., 24 hours from now)
- source: Source identifier (e.g., "nvd_api")

Return as JSON array of objects.
{examples}
"""
    
    schema = """
    - cve_id (VARCHAR): CVE identifier
    - nvd_data (JSONB): NVD API response data
    - epss_data (JSONB): EPSS score data
    - kev_data (JSONB): CISA KEV data
    - expires_at (TIMESTAMP): Cache expiration time
    - source (VARCHAR): Data source
    """
    
    data = generate_with_llm(
        llm,
        prompt_template,
        num_rows,
        "cve_cache",
        schema,
        examples=f"Available CVEs: {', '.join(cves[:10])}",
        cve_list=', '.join(cves)
    )
    
    stmt = text("""
        INSERT INTO cve_cache
        (cve_id, nvd_data, epss_data, kev_data, expires_at, source)
        VALUES (:cve_id, :nvd_data::jsonb, :epss_data::jsonb, :kev_data::jsonb, :expires_at, :source)
        ON CONFLICT (cve_id) DO NOTHING
    """)
    
    for row in data:
        nvd_data = row.get("nvd_data", {})
        epss_data = row.get("epss_data", {})
        kev_data = row.get("kev_data", {})
        
        # Set expires_at to 24 hours from now if not provided
        expires_at = row.get("expires_at")
        if not expires_at:
            expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        
        session.execute(stmt, {
            "cve_id": row["cve_id"],
            "nvd_data": json.dumps(nvd_data),
            "epss_data": json.dumps(epss_data),
            "kev_data": json.dumps(kev_data),
            "expires_at": expires_at,
            "source": row.get("source", "nvd_api")
        })
    
    session.commit()
    logger.info(f"✓ Inserted {len(data)} rows into cve_cache")


# ============================================================================
# Main Generation Function
# ============================================================================

def generate_all_data(
    num_rows: int = 100,
    phase: Optional[int] = None,
    source: Optional[str] = None,
    tables: Optional[List[str]] = None
) -> None:
    """
    Generate dummy data for all security intelligence tables.
    
    Args:
        num_rows: Number of rows to generate per table
        phase: Phase number (1, 2, 3) or None for all
        source: Security intelligence source
        tables: Specific tables to generate (None = all)
    """
    logger.info(f"Starting data generation: {num_rows} rows per table, phase={phase}, source={source}")
    
    # Initialize LLM
    try:
        llm = get_llm(temperature=0.0, model="gpt-4o-mini")
        logger.info("✓ LLM initialized")
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        logger.error("Make sure OPENAI_API_KEY is set in your environment or .env file")
        raise
    
    # Get database session
    session = get_session(source)
    
    try:
        # Phase 1 tables (Critical)
        phase1_tables = {
            "cve_attack_mapping": generate_cve_attack_mapping,
            "cpe_dictionary": generate_cpe_dictionary,
            "cve_cpe_affected": generate_cve_cpe_affected,
            "attack_technique_control_mapping": generate_attack_technique_control_mapping,
        }
        
        # Phase 2 tables (Enhanced)
        phase2_tables = {
            "metasploit_modules": generate_metasploit_modules,
            "nuclei_templates": generate_nuclei_templates,
            "exploit_db_index": generate_exploit_db_index,
        }
        
        # Phase 3 tables (Compliance)
        phase3_tables = {
            "cis_benchmark_rules": generate_cis_benchmark_rules,
            "sigma_rules": generate_sigma_rules,
        }
        
        # Utility tables
        utility_tables = {
            "cve_cache": generate_cve_cache,
        }
        
        # Determine which tables to generate
        all_tables = {}
        if phase == 1:
            all_tables = phase1_tables
        elif phase == 2:
            all_tables = {**phase1_tables, **phase2_tables}
        elif phase == 3:
            all_tables = {**phase1_tables, **phase2_tables, **phase3_tables}
        else:
            all_tables = {**phase1_tables, **phase2_tables, **phase3_tables, **utility_tables}
        
        # Filter by requested tables
        if tables:
            all_tables = {k: v for k, v in all_tables.items() if k in tables}
        
        # Generate data in dependency order
        # 1. CPE dictionary (needed for CVE-CPE mappings)
        if "cpe_dictionary" in all_tables:
            all_tables["cpe_dictionary"](llm, num_rows, session)
        
        # 2. CVE-ATT&CK mappings (needed for CVE-CPE and cache)
        if "cve_attack_mapping" in all_tables:
            all_tables["cve_attack_mapping"](llm, num_rows, session)
        
        # 3. CVE-CPE affected (depends on CPE and CVE)
        if "cve_cpe_affected" in all_tables:
            all_tables["cve_cpe_affected"](llm, num_rows, session)
        
        # 4. ATT&CK-Control mappings
        if "attack_technique_control_mapping" in all_tables:
            all_tables["attack_technique_control_mapping"](llm, num_rows, session)
        
        # 5. Exploit intelligence tables
        for table_name in ["metasploit_modules", "nuclei_templates", "exploit_db_index"]:
            if table_name in all_tables:
                all_tables[table_name](llm, num_rows, session)
        
        # 6. Compliance tables
        for table_name in ["cis_benchmark_rules", "sigma_rules"]:
            if table_name in all_tables:
                all_tables[table_name](llm, num_rows, session)
        
        # 7. Cache tables
        if "cve_cache" in all_tables:
            all_tables["cve_cache"](llm, num_rows, session)
        
        logger.info("✓ All data generation complete!")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error during data generation: {e}", exc_info=True)
        raise
    finally:
        session.close()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate dummy data for security intelligence tables using LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 100 rows for all tables
  python generate_dummy_data.py

  # Generate 50 rows for Phase 1 tables only
  python generate_dummy_data.py --phase 1 --rows 50

  # Generate data for specific tables
  python generate_dummy_data.py --tables cve_attack_mapping cpe_dictionary

  # Generate data in source-specific database
  python generate_dummy_data.py --source cve_attack
        """
    )
    
    parser.add_argument(
        '--rows', '-r',
        type=int,
        default=100,
        help='Number of rows to generate per table (default: 100)'
    )
    
    parser.add_argument(
        '--phase',
        type=int,
        choices=[1, 2, 3],
        help='Phase number (1=Critical, 2=Enhanced, 3=Compliance). If not specified, all phases are included.'
    )
    
    parser.add_argument(
        '--source',
        choices=['cve_attack', 'cpe', 'exploit', 'compliance'],
        help='Security intelligence source. If not specified, uses default database.'
    )
    
    parser.add_argument(
        '--tables',
        nargs='+',
        help='Specific tables to generate data for. If not specified, generates for all tables in the selected phase.'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        generate_all_data(
            num_rows=args.rows,
            phase=args.phase,
            source=args.source,
            tables=args.tables
        )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()
