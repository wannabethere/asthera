"""
Snyk Product Configuration Example
Comprehensive configuration for indexing Snyk product information based on docs.snyk.io.
Includes detailed product purpose, documentation links, key concepts, CVE/exploit database usage,
and extendable entities with actual API endpoints and examples.
"""
from typing import Dict, Any, List

# Snyk product information - Comprehensive configuration based on docs.snyk.io
SNYK_PRODUCT_CONFIG: Dict[str, Any] = {
    "product_name": "Snyk",
    "product_purpose": (
        "Snyk is a developer-first security platform that helps organizations find, prioritize, and fix "
        "vulnerabilities in their code, dependencies, containers, and infrastructure as code. "
        "Snyk provides continuous security monitoring, automated remediation capabilities, and integrates "
        "seamlessly into developer workflows. The platform maintains its own comprehensive vulnerability database "
        "that includes CVEs from NVD, manually curated vulnerabilities, exploit maturity data, and proprietary "
        "security research. Snyk supports multiple security domains including Software Composition Analysis (SCA) "
        "for open-source dependencies, Container Security for container images and Kubernetes, Infrastructure as Code "
        "(IaC) Security for Terraform, CloudFormation, and Kubernetes manifests, and Code Security for finding "
        "vulnerabilities in proprietary code. Snyk operates as a CVE Numbering Authority (CNA) and can assign CVE IDs "
        "for newly discovered vulnerabilities."
    ),
    "product_docs_link": "https://docs.snyk.io",
    "key_concepts": [
        "Vulnerability Database - Snyk maintains its own comprehensive vulnerability database that integrates CVEs from NVD, "
        "user reports from GitHub and community, manual security research, and automated feeds. The database includes both "
        "CVE-based and non-CVE vulnerabilities, with enriched metadata, verified vulnerability information, and version range "
        "specifications using semantic versioning and interval notation (e.g., '(,2.3.0]', '[1.5.0,2.0.0)'). "
        "Reference: https://docs.snyk.io/scan-with-snyk/snyk-open-source/manage-vulnerabilities/snyk-vulnerability-database",
        
        "CVE (Common Vulnerabilities and Exposures) - Snyk integrates CVE data from the National Vulnerability Database (NVD) "
        "and also assigns CVEs as a CVE Numbering Authority (CNA). Not all vulnerabilities have CVE IDs immediately, and Snyk's "
        "database includes vulnerabilities both with and without CVE assignments. CVEs allow cross-referencing with external "
        "databases and provide standardized vulnerability identification.",
        
        "Exploit Maturity - Snyk tracks exploit maturity levels to help prioritize vulnerabilities: 'No known exploit' (no evidence "
        "of exploitation), 'Proof of concept' (exploit code exists but not actively used), 'Mature' (actively exploited in the wild), "
        "and 'Attacked' (CVSS v4 classification for actively attacked vulnerabilities). Exploit data is collected from structured sources "
        "like CISA's Known Exploited Vulnerabilities List and Exploit DB, plus unstructured sources including social media, forums, and "
        "security research blogs. Reference: https://docs.snyk.io/manage-risk/prioritize-issues-for-fixing/view-exploits",
        
        "CVSS Scoring - Common Vulnerability Scoring System (CVSS) provides standardized severity ratings. Snyk uses CVSS scores to "
        "categorize vulnerabilities as Critical, High, Medium, Low, or Info severity levels, helping teams prioritize remediation efforts.",
        
        "Assets - Real-world components in the software development lifecycle that carry or aggregate risk, such as repositories, "
        "container images, packages, applications, and infrastructure configurations. Assets can be classified by business criticality "
        "(Class A, B, C, D) and tagged for organization and policy enforcement. Reference: https://docs.snyk.io/scan-with-snyk/snyk-essentials",
        
        "Projects - Represent applications, containers, or infrastructure configurations that Snyk monitors for security issues. "
        "Projects can be connected via integrations (GitHub, GitLab, etc.) or imported manually, and contain dependencies, code, "
        "or infrastructure definitions that are scanned for vulnerabilities.",
        
        "Issues - Security vulnerabilities, license violations, or policy violations found in projects. Each issue includes severity, "
        "CVE ID (if applicable), exploit maturity, affected package/version, remediation advice, and fix recommendations.",
        
        "Dependency Management - Snyk analyzes dependency trees (both direct and transitive dependencies) to identify vulnerable packages. "
        "The platform provides fix recommendations including version upgrades, patches, and alternative packages.",
        
        "Container Security - Scanning of container images for vulnerabilities in base images and installed packages. Includes Kubernetes "
        "security scanning, container registry integration, and runtime security monitoring.",
        
        "Infrastructure as Code (IaC) Security - Scanning of Terraform, CloudFormation, Kubernetes manifests, and other IaC files for "
        "misconfigurations and security issues. Helps prevent insecure infrastructure from being deployed.",
        
        "License Compliance - Detection and management of open-source license risks, including license conflicts, copyleft licenses, and "
        "commercial use restrictions.",
        
        "Security Policies - Automated rules that can tag assets, enforce coverage requirements, trigger alerts, and automate remediation "
        "actions based on vulnerability severity, exploit maturity, asset class, and other criteria.",
        
        "Coverage - Measurement of how well assets are scanned and tested for security issues. Coverage metrics help identify gaps in "
        "security scanning and ensure comprehensive protection.",
        
        "CI/CD Integration - Native integrations with GitHub Actions, GitLab CI, Jenkins, CircleCI, and other CI/CD platforms to "
        "automatically scan code, dependencies, and containers during the development pipeline.",
        
        "Developer Workflow - Snyk integrates into developer tools and workflows, providing IDE plugins, CLI tools, and pull request "
        "comments to help developers fix issues before they reach production.",
        
        "Prioritization and Risk Scoring - Snyk uses risk-based prioritization to help teams focus on the most critical vulnerabilities. "
        "Risk scoring considers factors like CVSS severity, exploit maturity (KEV, known exploited, in the wild), exploitability, "
        "reachability (whether vulnerable code is actually reachable), and business criticality. Prioritization helps teams allocate "
        "remediation resources effectively by focusing on vulnerabilities that pose the highest actual risk.",
        
        "EPSS (Exploit Probability Scoring System) - EPSS provides a data-driven score for the likelihood that a vulnerability will be "
        "exploited in the wild. EPSS scores range from 0.0 to 1.0, with higher scores indicating greater likelihood of exploitation. "
        "Snyk integrates EPSS data to help prioritize vulnerabilities based on both severity (CVSS) and likelihood of exploitation. "
        "Reference: https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/exploit-probability-scoring-system-epss",
        
        "KEV (Known Exploited Vulnerabilities) - Snyk tracks vulnerabilities from CISA's Known Exploited Vulnerabilities catalog, which "
        "identifies vulnerabilities that are actively being exploited. KEV vulnerabilities are automatically flagged as high priority "
        "and should be remediated immediately. Snyk also tracks exploit maturity levels: 'No known exploit', 'Proof of concept', "
        "'Mature' (actively exploited), and 'Attacked' (CVSS v4 classification).",
        
        "Asset Classification - Assets in Snyk can be classified by business criticality using Asset Classes A through D. Class A represents "
        "the most critical assets (e.g., customer-facing production applications), while Class D represents the least critical. Classification "
        "can be assigned automatically using repository names, labels, or manually. Asset classification is used in risk scoring and policy "
        "enforcement to prioritize security efforts on the most important assets. Reference: "
        "https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy",
        
        "Asset Inventory - Snyk automatically discovers and maintains an inventory of assets including repositories, container images, packages, "
        "applications, and infrastructure configurations. Assets have a hierarchical structure (e.g., repository → packages) and can be filtered "
        "by various dimensions including coverage gaps, last seen date, repo freshness, owner, lifecycle status, and issue severity. Asset inventory "
        "helps organizations understand their security posture and identify gaps in coverage. Reference: "
        "https://docs.snyk.io/manage-assets/assets-inventory-components",
        
        "Lifecycle and Decision State - Snyk tracks the lifecycle of vulnerabilities and supports decision states including: ignored (with expiration "
        "dates and reasons), suppressed, accepted risk, exceptions, and waivers. Issues can be marked as introduced, fixed, resolved, or reopened. "
        "These decision states are critical for compliance and audit purposes, as they provide evidence of risk management decisions and remediation "
        "tracking. Lifecycle tracking helps measure metrics like MTTR (Mean Time to Remediate).",
        
        "MTTR (Mean Time to Remediate) - MTTR is a key security metric that measures the average time it takes to fix vulnerabilities from when they "
        "are introduced to when they are resolved. Snyk provides MTTR metrics to help organizations measure and improve their remediation efficiency. "
        "Lower MTTR indicates faster response to security issues. MTTR can be measured across different asset classes, severity levels, and time periods.",
        
        "Coverage and Gap Analysis - Snyk tracks security scanning coverage across assets, measuring how well assets are scanned for vulnerabilities. "
        "Coverage metrics help identify gaps where assets are not being scanned or tested. Coverage can be measured across different security domains "
        "(SCA, Container, IaC, Code) and helps ensure comprehensive protection. Coverage gaps can trigger alerts and policy violations.",
        
        "Reporting and Analytics - Snyk provides comprehensive reporting and analytics capabilities including vulnerability trends, remediation metrics, "
        "coverage reports, and compliance dashboards. Reports can be exported in various formats and include detailed schemas for integration with "
        "external systems. Analytics help organizations understand their security posture, track improvements over time, and provide evidence for "
        "compliance audits."
    ],
    "extendable_entities": [
        {
            "name": "Projects",
            "type": "entity",
            "description": (
                "Projects represent applications, containers, or infrastructure configurations that Snyk monitors for security issues. "
                "Each project is associated with a specific target (repository, container image, or IaC file) and contains scan results, "
                "dependencies, and vulnerability data. Projects can be imported via integrations (GitHub, GitLab, etc.) or created manually. "
                "Projects support multiple project types including npm, Maven, PyPI, Docker, Kubernetes, Terraform, and more. "
                "Reference: https://docs.snyk.io/manage-projects"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/projects",
            "endpoints": [
                "GET /orgs/{orgId}/projects - List all projects in an organization with filtering options",
                "GET /orgs/{orgId}/projects/{projectId} - Get detailed information about a specific project",
                "POST /orgs/{orgId}/projects - Create a new project by importing from a repository or container registry",
                "PATCH /orgs/{orgId}/projects/{projectId} - Update project settings, tags, or attributes",
                "DELETE /orgs/{orgId}/projects/{projectId} - Delete a project and its associated scan data",
                "GET /orgs/{orgId}/projects/{projectId}/dependencies - Get dependency tree for a project",
                "GET /orgs/{orgId}/projects/{projectId}/issues - List all issues (vulnerabilities) found in a project"
            ],
            "examples": [
                {
                    "name": "my-node-app",
                    "type": "npm",
                    "target": {
                        "branch": "main",
                        "remoteUrl": "https://github.com/user/my-node-app",
                        "file": "package.json"
                    },
                    "origin": "github",
                    "tags": ["production", "critical"]
                },
                {
                    "name": "my-container",
                    "type": "dockerfile",
                    "target": {
                        "image": "myapp:latest",
                        "registry": "docker.io"
                    },
                    "origin": "container-registry"
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-projects"
        },
        {
            "name": "Issues",
            "type": "entity",
            "description": (
                "Issues represent security vulnerabilities, license violations, or policy violations found in projects. "
                "Each issue includes detailed information about the vulnerability including CVE ID (if applicable), CVSS score, "
                "exploit maturity level, affected package and version ranges, remediation advice, and fix recommendations. "
                "Issues can be filtered by severity, exploit maturity, CVE ID, package name, and other criteria. "
                "Issues support various actions including ignoring (with expiration dates), creating Jira tickets, and tracking "
                "remediation status. Reference: https://docs.snyk.io/manage-issues"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/issues",
            "endpoints": [
                "GET /orgs/{orgId}/issues - List all issues across projects with filtering (severity, exploit maturity, CVE, etc.)",
                "GET /orgs/{orgId}/issues/{issueId} - Get detailed information about a specific issue including CVE data and exploit maturity",
                "GET /orgs/{orgId}/issues/{issueId}/paths - Get all paths (dependency chains) through which a vulnerability is introduced",
                "POST /orgs/{orgId}/issues/{issueId}/ignore - Ignore an issue with optional expiration date and reason",
                "DELETE /orgs/{orgId}/issues/{issueId}/ignore - Remove ignore status from an issue",
                "POST /orgs/{orgId}/issues/{issueId}/jira - Create a Jira ticket for an issue",
                "GET /orgs/{orgId}/issues/{issueId}/fix - Get fix recommendations including upgrade paths and patches"
            ],
            "examples": [
                {
                    "id": "SNYK-JS-ACME-1234567",
                    "cve": "CVE-2025-9999",
                    "severity": "high",
                    "cvss_score": 8.5,
                    "title": "Prototype Pollution in acme package",
                    "package": "acme",
                    "version": "1.0.0",
                    "exploit_maturity": "Proof of concept",
                    "affected_versions": "(,1.2.3]",
                    "fixed_in": "1.2.4",
                    "description": "Prototype pollution vulnerability allows attackers to modify object prototypes..."
                },
                {
                    "id": "SNYK-JS-LODASH-567890",
                    "cve": "CVE-2021-23337",
                    "severity": "critical",
                    "cvss_score": 9.8,
                    "title": "Command Injection in lodash",
                    "package": "lodash",
                    "version": "4.17.20",
                    "exploit_maturity": "Mature",
                    "affected_versions": "[4.17.0,4.17.21)",
                    "fixed_in": "4.17.21"
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-issues"
        },
        {
            "name": "Organizations",
            "type": "entity",
            "description": (
                "Organizations represent teams or companies using Snyk. Each organization contains projects, members, "
                "integrations, policies, and settings. Organizations can have multiple groups for hierarchical management. "
                "Organization settings include security policies, notification preferences, API tokens, and billing information. "
                "Organizations support role-based access control (RBAC) with roles like Admin, Collaborator, and Viewer. "
                "Reference: https://docs.snyk.io/manage-account-and-settings"
            ),
            "api": "https://api.snyk.io/v1/orgs",
            "endpoints": [
                "GET /orgs - List all organizations the authenticated user has access to",
                "GET /orgs/{orgId} - Get detailed information about a specific organization",
                "PATCH /orgs/{orgId} - Update organization settings, name, or attributes",
                "GET /orgs/{orgId}/members - List all members in an organization",
                "POST /orgs/{orgId}/members - Add a member to an organization",
                "DELETE /orgs/{orgId}/members/{userId} - Remove a member from an organization",
                "GET /orgs/{orgId}/groups - List groups within an organization",
                "GET /orgs/{orgId}/settings - Get organization settings and preferences"
            ],
            "examples": [
                {
                    "id": "org-123abc",
                    "name": "Acme Corporation",
                    "slug": "acme-corp",
                    "group": {
                        "id": "group-456",
                        "name": "Engineering Team"
                    },
                    "settings": {
                        "require_mfa": True,
                        "default_org_role": "collaborator"
                    }
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-account-and-settings"
        },
        {
            "name": "Integrations",
            "type": "entity",
            "description": (
                "Integrations connect Snyk with external systems to enable automated scanning, notifications, and workflow automation. "
                "Supported integrations include source code management (GitHub, GitLab, Bitbucket), issue tracking (Jira, ServiceNow), "
                "communication (Slack, Microsoft Teams), CI/CD platforms (Jenkins, CircleCI, GitHub Actions), container registries "
                "(Docker Hub, AWS ECR, GCR), and cloud platforms (AWS, Azure, GCP). Integrations enable automatic project import, "
                "pull request testing, issue creation, and security notifications. Reference: https://docs.snyk.io/integrations"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/integrations",
            "endpoints": [
                "GET /orgs/{orgId}/integrations - List all configured integrations for an organization",
                "GET /orgs/{orgId}/integrations/{integrationId} - Get details about a specific integration",
                "POST /orgs/{orgId}/integrations - Create a new integration (GitHub, GitLab, Jira, etc.)",
                "PATCH /orgs/{orgId}/integrations/{integrationId} - Update integration settings or configuration",
                "DELETE /orgs/{orgId}/integrations/{integrationId} - Delete an integration",
                "GET /orgs/{orgId}/integrations/{integrationId}/import - Trigger import of projects from integration"
            ],
            "examples": [
                {
                    "type": "github",
                    "settings": {
                        "repo": "acme/my-app",
                        "branch": "main",
                        "auto_import": True,
                        "pull_request_testing": True
                    },
                    "credentials": {
                        "type": "oauth",
                        "scopes": ["repo", "admin:repo_hook"]
                    }
                },
                {
                    "type": "jira",
                    "settings": {
                        "project_key": "SEC",
                        "issue_type": "Bug",
                        "auto_create_issues": True,
                        "severity_threshold": "high"
                    },
                    "credentials": {
                        "type": "api_token",
                        "server_url": "https://acme.atlassian.net"
                    }
                }
            ],
            "docs_link": "https://docs.snyk.io/integrations"
        },
        {
            "name": "Vulnerability Database",
            "type": "entity",
            "description": (
                "Snyk's Vulnerability Database is a comprehensive, continuously updated database of security vulnerabilities. "
                "It includes CVEs from the National Vulnerability Database (NVD), manually curated vulnerabilities from Snyk's "
                "security research team, community-reported vulnerabilities, and proprietary research. The database uses semantic "
                "versioning with interval notation to specify affected version ranges (e.g., '(,2.3.0]' means all versions less than "
                "or equal to 2.3.0). Each vulnerability entry includes CVE ID (if assigned), CVSS score, severity classification, "
                "exploit maturity level, affected packages and version ranges, remediation advice, and fix recommendations. "
                "Snyk operates as a CVE Numbering Authority (CNA) and can assign CVE IDs for newly discovered vulnerabilities. "
                "The database supports both Application Feed (for application dependencies) and Operating System Feed (for OS packages). "
                "Reference: https://docs.snyk.io/scan-with-snyk/snyk-open-source/manage-vulnerabilities/snyk-vulnerability-database"
            ),
            "api": "https://security.snyk.io",
            "endpoints": [
                "GET /vuln/{ecosystem}/{package} - Get vulnerabilities for a specific package",
                "GET /vuln/{ecosystem}/{package}/{version} - Get vulnerabilities affecting a specific package version",
                "GET /vuln/cve/{cveId} - Get vulnerability details by CVE ID",
                "GET /vuln/{vulnId} - Get detailed vulnerability information by Snyk vulnerability ID"
            ],
            "examples": [
                {
                    "vuln_id": "SNYK-JS-LODASH-567890",
                    "cve": ["CVE-2021-23337"],
                    "severity": "critical",
                    "cvss_score": 9.8,
                    "exploit_maturity": "Mature",
                    "package": {
                        "name": "lodash",
                        "ecosystem": "npm"
                    },
                    "affected_versions": "[4.17.0,4.17.21)",
                    "fixed_in": ["4.17.21"],
                    "description": "Command Injection vulnerability in lodash package...",
                    "published_date": "2021-02-20",
                    "disclosure_date": "2021-02-15"
                }
            ],
            "docs_link": "https://docs.snyk.io/scan-with-snyk/snyk-open-source/manage-vulnerabilities/snyk-vulnerability-database"
        },
        {
            "name": "Assets",
            "type": "entity",
            "description": (
                "Assets represent real-world components in the software development lifecycle that carry or aggregate security risk. "
                "Assets can include repositories, container images, packages, applications, infrastructure configurations, and more. "
                "Assets are automatically discovered through integrations or can be manually added. Each asset can be classified by "
                "business criticality (Class A - most critical, Class B, Class C - default, Class D - least critical) and tagged "
                "for organization and policy enforcement. Assets have a hierarchical structure (e.g., repository → packages) and can be "
                "filtered by coverage gaps, last seen date, repo freshness, owner, lifecycle status, and issue severity. Assets are used "
                "in Snyk Essentials and AppRisk products for comprehensive security visibility and risk management. "
                "Reference: https://docs.snyk.io/scan-with-snyk/snyk-essentials"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/assets",
            "endpoints": [
                "GET /orgs/{orgId}/assets - List all assets in an organization with filtering options",
                "GET /orgs/{orgId}/assets/{assetId} - Get detailed information about a specific asset",
                "PATCH /orgs/{orgId}/assets/{assetId} - Update asset classification, tags, or attributes",
                "GET /orgs/{orgId}/assets/{assetId}/coverage - Get security coverage information for an asset",
                "GET /orgs/{orgId}/assets/{assetId}/issues - List all security issues associated with an asset"
            ],
            "examples": [
                {
                    "id": "asset-123",
                    "name": "my-production-app",
                    "type": "application",
                    "class": "A",
                    "tags": ["production", "customer-facing", "critical"],
                    "source": "github",
                    "repository": "acme/my-production-app",
                    "coverage": {
                        "sca": True,
                        "container": True,
                        "iac": False,
                        "code": True
                    },
                    "last_seen": "2025-01-15T10:30:00Z",
                    "freshness": "active"
                }
            ],
            "docs_link": "https://docs.snyk.io/scan-with-snyk/snyk-essentials"
        },
        {
            "name": "Asset Classification",
            "type": "entity",
            "description": (
                "Asset Classification allows organizations to categorize assets by business criticality using Asset Classes A through D. "
                "Class A represents the most critical assets (e.g., customer-facing production applications), Class B for important assets, "
                "Class C is the default classification, and Class D represents the least critical assets. Classification can be assigned "
                "automatically using repository names, labels, or manually through the UI or API. Asset classification is used in risk "
                "scoring and policy enforcement to prioritize security efforts on the most important assets. Classification policies can "
                "automatically assign classes based on naming patterns, tags, or other metadata. "
                "Reference: https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/assets",
            "endpoints": [
                "GET /orgs/{orgId}/assets?class=A - Filter assets by classification class",
                "PATCH /orgs/{orgId}/assets/{assetId} - Update asset classification",
                "GET /orgs/{orgId}/policies - List classification policies"
            ],
            "examples": [
                {
                    "asset_id": "asset-123",
                    "name": "customer-portal",
                    "class": "A",
                    "classification_method": "policy",
                    "policy_rule": "repo_name matches 'production' OR tags contains 'customer-facing'",
                    "description": "Class A - Most critical: customer-facing production application"
                },
                {
                    "asset_id": "asset-456",
                    "name": "internal-tool",
                    "class": "C",
                    "classification_method": "default",
                    "description": "Class C - Default classification for internal tools"
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy"
        },
        {
            "name": "Asset Inventory Components",
            "type": "entity",
            "description": (
                "Asset Inventory Components define the structure and types of assets in Snyk. Assets can be of different types including "
                "repositories, container images, packages, applications, and infrastructure configurations. Assets have a hierarchical "
                "structure where repositories contain packages, and applications aggregate multiple repositories. Asset inventory components "
                "help organizations understand their asset landscape, track asset relationships, and build asset graphs for comprehensive "
                "security visibility. The inventory automatically discovers assets through integrations and tracks metadata like owner, "
                "lifecycle status, coverage, and last seen date. "
                "Reference: https://docs.snyk.io/manage-assets/assets-inventory-components"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/assets",
            "endpoints": [
                "GET /orgs/{orgId}/assets - List all assets with type filtering",
                "GET /orgs/{orgId}/assets/{assetId} - Get asset details including type and hierarchy",
                "GET /orgs/{orgId}/assets/{assetId}/children - Get child assets (e.g., packages in a repo)",
                "GET /orgs/{orgId}/assets/{assetId}/parents - Get parent assets (e.g., repo containing a package)"
            ],
            "examples": [
                {
                    "asset_id": "repo-123",
                    "type": "repository",
                    "name": "acme/my-app",
                    "children": [
                        {"type": "package", "name": "lodash", "version": "4.17.20"},
                        {"type": "package", "name": "express", "version": "4.18.0"}
                    ],
                    "hierarchy_level": "parent"
                },
                {
                    "asset_id": "package-456",
                    "type": "package",
                    "name": "lodash",
                    "ecosystem": "npm",
                    "version": "4.17.20",
                    "parent": {"type": "repository", "name": "acme/my-app"},
                    "hierarchy_level": "child"
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-assets/assets-inventory-components"
        },
        {
            "name": "Asset Inventory Filters",
            "type": "entity",
            "description": (
                "Asset Inventory Filters provide analytics-friendly dimensions for querying and analyzing assets. Filters support dimensions "
                "including: coverage gaps (assets missing security scanning), last seen date (when asset was last scanned), repo freshness "
                "(how recently repository was updated), owner (asset owner or team), lifecycle status (active, archived, deprecated), and "
                "issue severity (critical, high, medium, low issues found). These filters enable organizations to identify security gaps, "
                "track asset health, measure coverage, and prioritize remediation efforts. Asset filters are essential for building dashboards, "
                "reports, and automated policies. "
                "Reference: https://docs.snyk.io/manage-assets/assets-inventory-filters"
            ),
            "api": "https://api.snyk.io/v1/orgs/{orgId}/assets",
            "endpoints": [
                "GET /orgs/{orgId}/assets?coverage_gap=true - Filter assets with coverage gaps",
                "GET /orgs/{orgId}/assets?last_seen_before=2025-01-01 - Filter by last seen date",
                "GET /orgs/{orgId}/assets?owner=team-security - Filter by owner",
                "GET /orgs/{orgId}/assets?lifecycle=active - Filter by lifecycle status",
                "GET /orgs/{orgId}/assets?severity=critical - Filter by issue severity"
            ],
            "examples": [
                {
                    "filter_type": "coverage_gap",
                    "description": "Find assets missing security scanning",
                    "query": {"coverage_gap": True, "class": "A"},
                    "use_case": "Identify critical assets without security coverage"
                },
                {
                    "filter_type": "freshness",
                    "description": "Find stale assets",
                    "query": {"last_seen_before": "2025-01-01", "lifecycle": "active"},
                    "use_case": "Identify active assets that haven't been scanned recently"
                },
                {
                    "filter_type": "severity",
                    "description": "Find assets with critical issues",
                    "query": {"severity": "critical", "class": "A"},
                    "use_case": "Prioritize remediation for critical assets with critical vulnerabilities"
                }
            ],
            "docs_link": "https://docs.snyk.io/manage-assets/assets-inventory-filters"
        }
    ],
    "extendable_docs": [
        {
            "title": "Getting Started with Snyk",
            "type": "getting_started",
            "link": "https://docs.snyk.io/getting-started",
            "description": (
                "Comprehensive guide to getting started with Snyk security scanning. Covers account creation, "
                "project setup, understanding scan results, configuring integrations, and basic security workflows. "
                "Includes tutorials for scanning your first repository, container, or infrastructure configuration."
            ),
            "sections": [
                "Creating a Snyk account and organization",
                "Connecting your first project (repository, container, or IaC)",
                "Understanding scan results and vulnerability reports",
                "Setting up integrations (GitHub, GitLab, CI/CD)",
                "Configuring security policies and notifications",
                "Using the Snyk CLI for local testing"
            ],
            "content": (
                "Snyk helps you find and fix vulnerabilities in your code, dependencies, containers, and infrastructure. "
                "Get started by creating an account, connecting your first project, and running your first scan. "
                "Snyk will automatically discover dependencies, scan for vulnerabilities, and provide fix recommendations."
            )
        },
        {
            "title": "Snyk REST API Documentation",
            "type": "api_reference",
            "link": "https://docs.snyk.io/api",
            "description": (
                "Complete REST API reference for programmatically managing Snyk security operations. "
                "The API enables automation of project management, issue tracking, vulnerability scanning, "
                "integration configuration, and security reporting. All API endpoints require authentication "
                "via API tokens and support filtering, pagination, and webhook notifications."
            ),
            "sections": [
                "Authentication - API tokens and OAuth",
                "Projects API - Create, list, update, and delete projects",
                "Issues API - Query vulnerabilities, manage ignores, create Jira tickets",
                "Organizations API - Manage organizations, members, and settings",
                "Integrations API - Configure and manage integrations",
                "Assets API - Manage assets, classifications, and coverage",
                "Vulnerability Database API - Query vulnerability information",
                "Webhooks - Receive real-time notifications for security events"
            ],
            "content": (
                "The Snyk REST API allows you to programmatically manage your security operations. "
                "Authenticate using API tokens obtained from your organization settings. The API follows "
                "RESTful principles with JSON request/response formats. All endpoints support filtering, "
                "pagination, and include detailed error responses. Use webhooks to receive real-time "
                "notifications for security events like new vulnerabilities, scan completions, and policy violations."
            )
        },
        {
            "title": "Snyk CLI Documentation",
            "type": "cli_reference",
            "link": "https://docs.snyk.io/cli",
            "description": (
                "Command-line interface for testing and monitoring projects locally and in CI/CD pipelines. "
                "The Snyk CLI supports scanning of code repositories, container images, infrastructure as code files, "
                "and can be integrated into any CI/CD pipeline. It provides detailed vulnerability reports, fix recommendations, "
                "and can fail builds based on security policies."
            ),
            "sections": [
                "Installation - npm, Homebrew, Scoop, or standalone binary",
                "Authentication - Using 'snyk auth' to authenticate with your account",
                "Scanning projects - 'snyk test' for vulnerability scanning",
                "Monitoring projects - 'snyk monitor' to track projects in Snyk",
                "Container scanning - 'snyk container test' for Docker images",
                "IaC scanning - 'snyk iac test' for Terraform, CloudFormation, Kubernetes",
                "Code scanning - 'snyk code test' for proprietary code analysis",
                "CI/CD integration - Using Snyk CLI in GitHub Actions, Jenkins, etc.",
                "Configuration - .snyk policy files for custom rules and ignores"
            ],
            "content": (
                "The Snyk CLI allows you to test and monitor your projects from the command line. "
                "Install via npm, Homebrew, or download the standalone binary. Authenticate using 'snyk auth' "
                "to connect to your Snyk account. Use 'snyk test' to scan for vulnerabilities, 'snyk monitor' "
                "to track projects in Snyk, and 'snyk container test' for container images. The CLI can be "
                "integrated into any CI/CD pipeline and supports exit codes for build failure based on security policies."
            )
        },
        {
            "title": "Snyk Container Security",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/products/snyk-container",
            "description": (
                "Comprehensive documentation for Snyk Container security scanning. Snyk Container scans container images "
                "for vulnerabilities in base images and installed packages, provides fix recommendations, and integrates "
                "with container registries and Kubernetes. Supports scanning of Docker images, OCI images, and provides "
                "runtime security monitoring for running containers."
            ),
            "sections": [
                "Container scanning basics - How Snyk scans container images for vulnerabilities",
                "Kubernetes integration - Scanning Kubernetes workloads and clusters",
                "Container registry scanning - Integration with Docker Hub, ECR, GCR, ACR",
                "Base image recommendations - Finding and upgrading to secure base images",
                "Policy configuration - Setting security policies for container deployments",
                "Runtime security - Monitoring running containers for security issues",
                "Fix recommendations - Upgrading base images and packages to fix vulnerabilities"
            ],
            "content": (
                "Snyk Container helps you find and fix vulnerabilities in your container images. It scans both the "
                "base image and installed packages, providing detailed vulnerability reports with CVSS scores and "
                "exploit maturity information. Snyk Container integrates with container registries to automatically "
                "scan images on push, provides base image upgrade recommendations, and can enforce security policies "
                "to prevent deployment of vulnerable images. For Kubernetes, Snyk provides cluster scanning and "
                "workload security monitoring."
            )
        },
        {
            "title": "Snyk Infrastructure as Code (IaC) Security",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/products/snyk-infrastructure-as-code",
            "description": (
                "Documentation for Snyk IaC security scanning. Snyk IaC scans Terraform, CloudFormation, Kubernetes manifests, "
                "and other IaC files for misconfigurations and security issues before infrastructure is deployed. It provides "
                "fix recommendations, policy enforcement, and integrates with cloud platforms for continuous monitoring of "
                "deployed infrastructure."
            ),
            "sections": [
                "Terraform scanning - Scanning Terraform files for security misconfigurations",
                "CloudFormation scanning - Analyzing AWS CloudFormation templates",
                "Kubernetes manifests - Security scanning of Kubernetes YAML files",
                "Cloud platform scanning - Continuous monitoring of AWS, Azure, GCP infrastructure",
                "Policy as code - Defining security policies using code",
                "Fix recommendations - Automated fixes for common misconfigurations",
                "CI/CD integration - Scanning IaC files in pull requests and pipelines"
            ],
            "content": (
                "Snyk IaC helps you find and fix misconfigurations in your infrastructure code before deployment. "
                "It scans Terraform, CloudFormation, Kubernetes manifests, and ARM templates for security issues like "
                "exposed secrets, overly permissive IAM policies, unencrypted storage, and more. Snyk IaC provides "
                "detailed fix recommendations and can enforce security policies to prevent insecure infrastructure from "
                "being deployed. For cloud platforms, Snyk provides continuous monitoring of deployed infrastructure to "
                "detect configuration drift and new security issues."
            )
        },
        {
            "title": "Snyk Vulnerability Database",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/scan-with-snyk/snyk-open-source/manage-vulnerabilities/snyk-vulnerability-database",
            "description": (
                "Comprehensive documentation about Snyk's Vulnerability Database, how it works, and how CVE and exploit data "
                "are used. Explains the database structure, data sources, version range notation, exploit maturity levels, "
                "and how vulnerabilities are discovered, verified, and maintained."
            ),
            "sections": [
                "Database overview - What is Snyk's Vulnerability Database",
                "CVE integration - How CVEs from NVD are integrated and new CVEs are assigned",
                "Exploit maturity - Understanding exploit maturity levels and data sources",
                "Version ranges - Semantic versioning and interval notation for affected versions",
                "Data sources - Where vulnerability and exploit data comes from",
                "Vulnerability lifecycle - How vulnerabilities are discovered, verified, and published",
                "Application vs OS feeds - Different vulnerability feeds for different use cases",
                "CVE Numbering Authority - Snyk's role as a CNA for assigning CVE IDs"
            ],
            "content": (
                "Snyk maintains its own comprehensive Vulnerability Database that includes CVEs from the National Vulnerability "
                "Database (NVD), manually curated vulnerabilities from Snyk's security research team, community-reported "
                "vulnerabilities, and proprietary research. The database uses semantic versioning with interval notation "
                "(e.g., '(,2.3.0]', '[1.5.0,2.0.0)') to specify which package versions are affected by each vulnerability. "
                "Each vulnerability entry includes CVE ID (if assigned), CVSS score, severity classification, exploit maturity "
                "level (No known exploit, Proof of concept, Mature, Attacked), affected packages and version ranges, remediation "
                "advice, and fix recommendations. Snyk operates as a CVE Numbering Authority (CNA) and can assign CVE IDs for "
                "newly discovered vulnerabilities. Exploit data is collected from structured sources like CISA's Known Exploited "
                "Vulnerabilities List and Exploit DB, plus unstructured sources including social media, forums, and security "
                "research blogs. The database supports both Application Feed (for application dependencies like npm, Maven, PyPI) "
                "and Operating System Feed (for OS packages)."
            )
        },
        {
            "title": "View Exploits and Exploit Maturity",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/manage-risk/prioritize-issues-for-fixing/view-exploits",
            "description": (
                "Documentation explaining how Snyk tracks and displays exploit maturity information for vulnerabilities. "
                "Explains the different exploit maturity levels, how exploit data is collected and verified, and how to use "
                "this information to prioritize vulnerability remediation."
            ),
            "sections": [
                "Exploit maturity levels - No known exploit, Proof of concept, Mature, Attacked",
                "Data sources - Where exploit information comes from (CISA, Exploit DB, research)",
                "Using exploit data - How to prioritize vulnerabilities based on exploit maturity",
                "Exploit details - Viewing proof-of-concept and real-world exploit information",
                "CVSS v4 integration - How CVSS v4 'Attacked' level is used"
            ],
            "content": (
                "Snyk tracks exploit maturity levels for vulnerabilities to help prioritize remediation efforts. Exploit maturity "
                "can be: 'No known exploit' (no evidence of exploitation), 'Proof of concept' (exploit code exists but not actively "
                "used in attacks), 'Mature' (actively exploited in the wild), and 'Attacked' (CVSS v4 classification for actively "
                "attacked vulnerabilities). Exploit data is collected from structured sources like CISA's Known Exploited "
                "Vulnerabilities List and Exploit DB, plus unstructured sources including social media, forums, and security "
                "research blogs. This information is curated by Snyk's security research team and displayed in the Snyk UI and "
                "API to help security teams prioritize which vulnerabilities to fix first."
            )
        },
        {
            "title": "Snyk Essentials",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/scan-with-snyk/snyk-essentials",
            "description": (
                "Documentation for Snyk Essentials, which helps operationalize and scale developer-first application security. "
                "Essentials provides asset discovery, policy enforcement, coverage tracking, risk prioritization, and comprehensive "
                "security dashboards."
            ),
            "sections": [
                "Asset discovery - Automatically finding and categorizing application assets",
                "Asset classification - Classifying assets by business criticality (Class A-D)",
                "Policy builder - Defining security policies and automated actions",
                "Coverage tracking - Measuring security scanning coverage across assets",
                "Dashboards and reporting - Visualizing security posture and risk",
                "Tagging and organization - Organizing assets with tags and metadata"
            ],
            "content": (
                "Snyk Essentials helps operationalize and scale developer-first application security by providing comprehensive "
                "asset discovery, policy enforcement, coverage tracking, and risk prioritization. Essentials automatically discovers "
                "assets through integrations, allows classification by business criticality (Class A - most critical to Class D - "
                "least critical), and supports tagging for organization. The Policy Builder enables defining automated security policies "
                "that can tag assets, enforce coverage requirements, trigger alerts, and automate remediation actions. Coverage tracking "
                "helps identify gaps in security scanning and ensures comprehensive protection. Dashboards provide visualizations of "
                "security posture, risk distribution, and coverage metrics across the organization."
            )
        },
        {
            "title": "Assets in Snyk",
            "type": "feature_documentation",
            "link": "https://docs.snyk.io/scan-with-snyk/snyk-essentials",
            "description": (
                "Detailed documentation about Assets in Snyk - what they are, how they're discovered, classified, and managed. "
                "Assets represent real-world components in the SDLC that carry security risk, such as repositories, container images, "
                "packages, and applications."
            ),
            "sections": [
                "What are Assets - Understanding assets and their role in security management",
                "Asset discovery - How Snyk automatically discovers assets through integrations",
                "Asset classification - Classifying assets by business criticality (Class A-D)",
                "Asset tagging - Organizing assets with tags and metadata",
                "Asset coverage - Tracking security scanning coverage for each asset",
                "Asset policies - Applying security policies to assets"
            ],
            "content": (
                "Assets represent real-world components in the software development lifecycle that carry or aggregate security risk. "
                "Assets can include repositories, container images, packages, applications, infrastructure configurations, and more. "
                "Assets are automatically discovered through integrations (GitHub, GitLab, container registries, etc.) or can be "
                "manually added. Each asset can be classified by business criticality: Class A (most critical), Class B, Class C "
                "(default), or Class D (least critical). Assets can be tagged for organization and policy enforcement. Coverage "
                "tracking shows how well each asset is scanned and tested for security issues across different security domains "
                "(SCA, Container, IaC, Code). Assets are central to Snyk Essentials and AppRisk products for comprehensive security "
                "visibility and risk management."
            )
        },
        {
            "title": "CVSS Severity and Scoring",
            "type": "reference_documentation",
            "link": "https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/severity-and-cvss",
            "description": (
                "Decision-grade documentation explaining CVSS (Common Vulnerability Scoring System) and how Snyk uses CVSS scores to "
                "categorize vulnerabilities by severity. This is a reference document that defines severity scoring semantics and "
                "is ideal for risk intelligence and analytics-driven knowledge bases. Contains CVSS/vulnerability-scoring semantics "
                "written for risk intelligence rather than UI usage."
            ),
            "sections": [
                "CVSS overview - Understanding Common Vulnerability Scoring System",
                "Severity levels - Critical, High, Medium, Low, Info classifications",
                "CVSS score interpretation - How to interpret CVSS scores (0.0 to 10.0)",
                "Severity categorization - How Snyk maps CVSS scores to severity levels",
                "Prioritization - Using CVSS scores for vulnerability prioritization"
            ],
            "content": (
                "CVSS (Common Vulnerability Scoring System) provides standardized severity ratings for vulnerabilities. Snyk uses CVSS "
                "scores to categorize vulnerabilities as Critical, High, Medium, Low, or Info severity levels, helping teams prioritize "
                "remediation efforts. CVSS scores range from 0.0 to 10.0, with higher scores indicating more severe vulnerabilities. "
                "This reference documentation is decision-grade and focuses on risk intelligence and scoring semantics rather than "
                "how to use the Snyk UI."
            )
        },
        {
            "title": "Exploit Probability Scoring System (EPSS)",
            "type": "reference_documentation",
            "link": "https://docs.snyk.io/scan-applications/snyk-open-source/vulnerability-management/exploit-probability-scoring-system-epss",
            "description": (
                "Decision-grade documentation explaining EPSS (Exploit Probability Scoring System) which provides a data-driven score "
                "for the likelihood that a vulnerability will be exploited in the wild. EPSS is a likelihood signal that complements "
                "CVSS severity scores. This documentation contains EPSS/vulnerability-scoring semantics written for risk intelligence "
                "and is ideal for analytics-driven knowledge bases."
            ),
            "sections": [
                "EPSS overview - What is Exploit Probability Scoring System",
                "EPSS scores - Understanding scores from 0.0 to 1.0",
                "Likelihood signal - How EPSS indicates exploitation probability",
                "Integration with CVSS - Combining EPSS with CVSS for prioritization",
                "Using EPSS - How to use EPSS scores for vulnerability prioritization"
            ],
            "content": (
                "EPSS (Exploit Probability Scoring System) provides a data-driven score for the likelihood that a vulnerability will be "
                "exploited in the wild. EPSS scores range from 0.0 to 1.0, with higher scores indicating greater likelihood of exploitation. "
                "Snyk integrates EPSS data to help prioritize vulnerabilities based on both severity (CVSS) and likelihood of exploitation. "
                "This reference documentation is decision-grade and focuses on risk intelligence and likelihood scoring semantics."
            )
        },
        {
            "title": "Asset Classification Policy",
            "type": "reference_documentation",
            "link": "https://docs.snyk.io/manage-risk/policies/assets-policies/use-cases-for-policies/classification-policy",
            "description": (
                "Decision-grade documentation explaining asset classification by business criticality (Asset Class A-D). This is the "
                "cleanest asset classification semantics document, ideal for knowledge bases and feature engineering. Defines Asset "
                "Class A (most critical) through D (least critical) and how classification is assigned using repository names, labels, "
                "or policies."
            ),
            "sections": [
                "Asset classification overview - Understanding business criticality classes",
                "Asset Class A - Most critical assets (customer-facing production)",
                "Asset Class B - Important assets",
                "Asset Class C - Default classification",
                "Asset Class D - Least critical assets",
                "Classification assignment - Automatic and manual classification methods",
                "Policy-based classification - Using policies to assign classes",
                "Classification in risk scoring - How asset class affects risk prioritization"
            ],
            "content": (
                "Asset Classification allows organizations to categorize assets by business criticality using Asset Classes A through D. "
                "Class A represents the most critical assets (e.g., customer-facing production applications), Class B for important "
                "assets, Class C is the default classification, and Class D represents the least critical. Classification can be assigned "
                "automatically using repository names, labels, or manually through policies. Asset classification is used in risk scoring "
                "and policy enforcement to prioritize security efforts on the most important assets. This documentation is decision-grade "
                "and focuses on classification semantics and risk management rather than UI usage."
            )
        },
        {
            "title": "Asset Inventory Components",
            "type": "reference_documentation",
            "link": "https://docs.snyk.io/manage-assets/assets-inventory-components",
            "description": (
                "Decision-grade documentation defining asset entity types and hierarchy in Snyk. Explicitly defines asset types "
                "(repositories, container images, packages, scanned artifacts) and hierarchy (repository → packages). This documentation "
                "is ideal for building asset graphs and rollups, and is perfect for knowledge bases focused on asset modeling and "
                "inventory management."
            ),
            "sections": [
                "Asset types - Repositories, container images, packages, applications",
                "Asset hierarchy - Parent-child relationships (repo → packages)",
                "Asset discovery - How assets are automatically discovered",
                "Asset metadata - Owner, lifecycle, coverage, last seen",
                "Asset relationships - Understanding asset graphs and dependencies"
            ],
            "content": (
                "Asset Inventory Components define the structure and types of assets in Snyk. Assets can be of different types including "
                "repositories, container images, packages, applications, and infrastructure configurations. Assets have a hierarchical "
                "structure where repositories contain packages, and applications aggregate multiple repositories. The inventory automatically "
                "discovers assets through integrations and tracks metadata like owner, lifecycle status, coverage, and last seen date. "
                "This documentation is decision-grade and focuses on asset modeling and inventory semantics rather than UI usage."
            )
        },
        {
            "title": "Asset Inventory Filters",
            "type": "reference_documentation",
            "link": "https://docs.snyk.io/manage-assets/assets-inventory-filters",
            "description": (
                "Decision-grade documentation explaining asset inventory filters and analytics-friendly dimensions. This documentation "
                "exposes analytics dimensions like coverage gaps, last seen date, repo freshness, owner, lifecycle status, and issue severity. "
                "Ideal for building asset freshness metrics, coverage gap analysis, and lifecycle tracking. This is decision-grade because "
                "it focuses on analytics and measurement rather than UI usage."
            ),
            "sections": [
                "Coverage gaps - Identifying assets missing security scanning",
                "Last seen date - Tracking when assets were last scanned",
                "Repo freshness - Measuring repository update frequency",
                "Owner filtering - Filtering assets by owner or team",
                "Lifecycle status - Active, archived, deprecated assets",
                "Issue severity filtering - Filtering by vulnerability severity",
                "Analytics dimensions - Using filters for dashboards and reports"
            ],
            "content": (
                "Asset Inventory Filters provide analytics-friendly dimensions for querying and analyzing assets. Filters support dimensions "
                "including: coverage gaps (assets missing security scanning), last seen date (when asset was last scanned), repo freshness "
                "(how recently repository was updated), owner (asset owner or team), lifecycle status (active, archived, deprecated), and "
                "issue severity (critical, high, medium, low issues found). These filters enable organizations to identify security gaps, "
                "track asset health, measure coverage, and prioritize remediation efforts. This documentation is decision-grade and focuses "
                "on analytics and measurement semantics rather than UI usage."
            )
        }
    ],
    "ingestion_filters": {
        "description": (
            "Decision-grade ingestion filter rules for Snyk documentation. These filters help identify and prioritize "
            "documentation that is useful for risk intelligence, analytics, and decision-making rather than UI usage guides. "
            "The filter uses a gated rule-set: ALLOW only if it hits decision keywords + fits allowed page types; DENY if it "
            "looks like UI/how-to/admin content."
        ),
        "scope_guard": {
            "host": "docs.snyk.io",
            "path_patterns": [
                "^/",
                "/(product|products|guides|concepts|glossary|reference|api|reporting|policy|vulnerability|security|risk|prioritization|issues)"
            ],
            "description": "Only allow pages from docs.snyk.io matching specified path patterns"
        },
        "deny_keywords": {
            "ui_howto_verbs": [
                "click", "navigate", "go to", "select", "open", "choose",
                "from the menu", "in the UI", "in the console", "in the dashboard"
            ],
            "tutorial_keywords": [
                "step-by-step", "getting started", "quickstart", "tutorial", "walkthrough"
            ],
            "admin_setup_keywords": [
                "create a project", "import a repo", "connect", "integration setup",
                "configure", "installation", "install", "agent", "CLI install"
            ],
            "admin_keywords": [
                "SSO", "SAML", "SCIM", "billing", "plans", "seats", "roles", "permissions"
            ],
            "troubleshooting_keywords": [
                "troubleshoot", "FAQ", "known issues", "release notes", "changelog"
            ],
            "description": "If any of these keywords appear in title/H1 or first ~3000 characters, DENY the page"
        },
        "allow_keywords": {
            "exploit_severity_intelligence": {
                "keywords": ["CVSS", "EPSS", "CVE", "CWE", "known exploited", "KEV", "in the wild", "exploit maturity", "severity", "vector", "attack vector"],
                "scores": {
                    "CVSS": 4,
                    "EPSS": 4,
                    "CVE": 3,
                    "CWE": 3,
                    "known exploited": 4,
                    "KEV": 4,
                    "in the wild": 4,
                    "exploit maturity": 3,
                    "severity": 2,
                    "vector": 2,
                    "attack vector": 2
                }
            },
            "prioritization_risk_semantics": {
                "keywords": ["prioritization", "risk score", "risk-based", "exploitability", "reachability", "business criticality", "SLA", "due date"],
                "scores": {
                    "prioritization": 4,
                    "risk score": 4,
                    "risk-based": 4,
                    "exploitability": 3,
                    "reachability": 3,
                    "business criticality": 3,
                    "SLA": 2,
                    "due date": 2
                }
            },
            "lifecycle_decision_state": {
                "keywords": ["ignored", "ignore", "suppressed", "accepted risk", "exception", "waiver", "introduced", "fixed", "resolved", "reopened"],
                "scores": {
                    "ignored": 3,
                    "ignore": 3,
                    "suppressed": 3,
                    "accepted risk": 4,
                    "exception": 3,
                    "waiver": 3,
                    "introduced": 2,
                    "fixed": 2,
                    "resolved": 2,
                    "reopened": 2
                }
            },
            "measurement_analytics": {
                "keywords": ["MTTR", "mean time to remediate", "remediation", "coverage", "trend", "baseline", "new vs existing", "reporting", "export", "schema", "field"],
                "scores": {
                    "MTTR": 4,
                    "mean time to remediate": 4,
                    "remediation": 3,
                    "coverage": 3,
                    "trend": 2,
                    "baseline": 2,
                    "new vs existing": 2,
                    "reporting": 3,
                    "export": 2,
                    "schema": 3,
                    "field": 2
                }
            },
            "decision_score_threshold": 6,
            "description": "Compute DecisionScore by scanning title/H1/body. ALLOW if DecisionScore >= 6"
        },
        "decision_intent_phrases": [
            "prioritize", "prioritise", "risk", "likelihood", "impact",
            "measure", "metric", "KPI", "SLA", "evidence", "audit",
            "compliance", "report", "dashboard", "trend"
        ],
        "preferred_document_types": [
            "Glossary / definitions pages",
            "Conceptual 'how scoring works' pages",
            "Reference pages that define data fields / issue model",
            "Reporting / export schema pages",
            "Policy semantics pages (ignore/acceptance lifecycle)"
        ],
        "minimal_config": {
            "allow_keywords_regex": "CVSS|EPSS|KEV|known exploited|CVE|CWE|risk score|prioritization|exploitability|reachability|MTTR|mean time to remediate|remediation|coverage|baseline|new vs existing|reporting|export|schema|accepted risk|ignore|suppressed|exception|waiver",
            "deny_keywords_regex": "click|navigate|go to|select|open|step-by-step|getting started|quickstart|tutorial|walkthrough|install|installation|configure|setup|connect|create a project|import|SSO|SAML|SCIM|billing|plans|seats|release notes|changelog|troubleshoot|FAQ",
            "rule": "If DENY hit → skip; Else if ALLOW hit AND intent phrase hit → index; Else skip"
        }
    }
}


def get_snyk_product_config() -> Dict[str, Any]:
    """Get Snyk product configuration."""
    return SNYK_PRODUCT_CONFIG.copy()


# Detailed explanation of how CVE and Exploit Database works in Snyk
SNYK_CVE_EXPLOIT_DB_EXPLANATION: Dict[str, Any] = {
    "title": "How Snyk's CVE and Exploit Database Works",
    "description": (
        "Comprehensive explanation of how Snyk's Vulnerability Database integrates CVE data, "
        "tracks exploit maturity, and provides security intelligence for vulnerability management."
    ),
    "vulnerability_database": {
        "overview": (
            "Snyk maintains its own comprehensive Vulnerability Database that is independent from but includes "
            "CVE data from the National Vulnerability Database (NVD). The database is continuously updated with "
            "vulnerabilities from multiple sources including CVEs, user reports, GitHub issues, security researcher "
            "inputs, and Snyk's own security research team."
        ),
        "data_sources": [
            "National Vulnerability Database (NVD) - CVE data and CVSS scores",
            "Snyk Security Research Team - Manual vulnerability research and verification",
            "Community Reports - User-submitted vulnerabilities from GitHub and community",
            "Automated Feeds - Continuous monitoring of security advisories and bulletins",
            "Proprietary Research - Snyk's own vulnerability discovery and analysis"
        ],
        "database_structure": {
            "vulnerability_id": "Snyk-assigned vulnerability ID (e.g., SNYK-JS-LODASH-567890)",
            "cve_ids": "List of associated CVE IDs (if assigned)",
            "severity": "CVSS-based severity (Critical, High, Medium, Low, Info)",
            "cvss_score": "Numeric CVSS score (0.0 to 10.0)",
            "exploit_maturity": "Exploit maturity level (No known exploit, Proof of concept, Mature, Attacked)",
            "affected_packages": "List of affected packages with ecosystem information",
            "version_ranges": "Semantic version ranges using interval notation",
            "description": "Detailed vulnerability description and impact",
            "remediation": "Fix recommendations including upgrade paths and patches",
            "published_date": "When the vulnerability was first published",
            "disclosure_date": "When the vulnerability was disclosed",
            "advisory_links": "Links to security advisories and related information"
        },
        "version_range_notation": {
            "explanation": (
                "Snyk uses semantic versioning with interval notation to specify which package versions are affected "
                "by a vulnerability. This allows precise specification of vulnerable version ranges."
            ),
            "examples": [
                "(,2.3.0] - All versions less than or equal to 2.3.0",
                "[1.5.0,2.0.0) - Versions from 1.5.0 (inclusive) to 2.0.0 (exclusive)",
                "[4.17.0,4.17.21) - Versions from 4.17.0 to 4.17.21 (lodash CVE-2021-23337)",
                "(,1.0.0) - All versions less than 1.0.0"
            ],
            "reference": "https://docs.snyk.io/scan-with-snyk/snyk-open-source/manage-vulnerabilities/snyk-vulnerability-database"
        },
        "cve_integration": {
            "how_it_works": (
                "Snyk integrates CVE data from NVD and also operates as a CVE Numbering Authority (CNA), "
                "allowing Snyk to assign CVE IDs for newly discovered vulnerabilities. Not all vulnerabilities "
                "have CVE IDs immediately - some may be assigned later, and some may never receive CVEs. "
                "Snyk's database includes both CVE-based and non-CVE vulnerabilities."
            ),
            "cve_assignment": (
                "When Snyk or the community discovers a valid vulnerability, Snyk can assign a CVE ID as a CNA. "
                "This allows cross-referencing with external databases and provides standardized vulnerability identification."
            ),
            "cve_sources": [
                "NVD (National Vulnerability Database) - Primary source for CVE data",
                "Snyk CNA - Snyk-assigned CVEs for newly discovered vulnerabilities",
                "Other CNAs - CVEs assigned by other organizations"
            ],
            "reference": "https://docs.snyk.io/snyk-data-and-governance/disclosure-of-a-vulnerability-in-an-open-source-package"
        },
        "exploit_maturity": {
            "overview": (
                "Snyk tracks exploit maturity levels to help prioritize vulnerability remediation. Exploit maturity "
                "indicates whether a vulnerability has been exploited in the wild and how mature the exploit code is."
            ),
            "levels": [
                {
                    "level": "No known exploit",
                    "description": "No evidence of exploitation exists. No proof-of-concept code or real-world attacks have been observed.",
                    "priority": "Lower priority unless severity is critical"
                },
                {
                    "level": "Proof of concept",
                    "description": "Exploit code exists but has not been actively used in real-world attacks. May be available in research papers, GitHub, or security forums.",
                    "priority": "Medium priority - exploit code exists but not actively used"
                },
                {
                    "level": "Mature",
                    "description": "Actively exploited in the wild. Exploit code is mature, reliable, and being used in real attacks.",
                    "priority": "High priority - actively being exploited"
                },
                {
                    "level": "Attacked",
                    "description": "CVSS v4 classification for vulnerabilities that are actively being attacked. Highest priority for remediation.",
                    "priority": "Critical priority - actively attacked"
                }
            ],
            "data_sources": [
                "CISA Known Exploited Vulnerabilities (KEV) Catalog - Structured source for known exploited vulnerabilities",
                "Exploit DB - Database of exploit code and proof-of-concepts",
                "Security Research Blogs - Unstructured sources from security researchers",
                "Social Media and Forums - Twitter, Reddit, security forums",
                "GitHub - Exploit code repositories and security research",
                "Snyk Security Research - Internal research and analysis"
            ],
            "collection_method": (
                "Exploit data is collected through a combination of automated scraping of structured sources "
                "(CISA KEV, Exploit DB) and unstructured sources (blogs, forums, social media), plus manual "
                "curation by Snyk's security research team. The data is verified and categorized into maturity levels."
            ),
            "reference": "https://docs.snyk.io/manage-risk/prioritize-issues-for-fixing/view-exploits"
        },
        "feed_types": {
            "application_feed": {
                "description": (
                    "Vulnerability data for application dependencies including npm, Maven, PyPI, NuGet, "
                    "RubyGems, Go modules, and other package managers."
                ),
                "use_cases": [
                    "Scanning application dependencies for vulnerabilities",
                    "Open source security management",
                    "License compliance checking"
                ]
            },
            "operating_system_feed": {
                "description": (
                    "Vulnerability data for operating system packages including Debian, Ubuntu, Alpine, "
                    "Red Hat, and other Linux distributions."
                ),
                "use_cases": [
                    "Container base image vulnerability scanning",
                    "OS package security management",
                    "Infrastructure security"
                ]
            }
        },
        "malicious_packages": {
            "description": (
                "Separate from vulnerabilities in legitimate packages, Snyk also tracks malicious packages - "
                "packages intentionally designed to carry out malicious behavior. These are flagged with severity "
                "'Critical' but may not have CVE IDs assigned."
            ),
            "reference": "https://docs.snyk.io/manage-risk/prioritize-issues-for-fixing/malicious-packages"
        },
        "public_database": {
            "url": "https://security.snyk.io",
            "description": (
                "Snyk provides a public vulnerability database at security.snyk.io where users can search for "
                "vulnerabilities by package name, CVE ID, or Snyk vulnerability ID. The database includes detailed "
                "information about each vulnerability including CVSS scores, exploit maturity, affected versions, "
                "and remediation advice."
            )
        }
    }
}


def get_snyk_cve_exploit_db_explanation() -> Dict[str, Any]:
    """Get detailed explanation of how Snyk's CVE and Exploit Database works."""
    return SNYK_CVE_EXPLOIT_DB_EXPLANATION.copy()


# Example usage
if __name__ == "__main__":
    print("Snyk Product Configuration:")
    print(f"Product: {SNYK_PRODUCT_CONFIG['product_name']}")
    print(f"Purpose: {SNYK_PRODUCT_CONFIG['product_purpose'][:100]}...")
    print(f"Key Concepts: {len(SNYK_PRODUCT_CONFIG['key_concepts'])}")
    print(f"Extendable Entities: {len(SNYK_PRODUCT_CONFIG['extendable_entities'])}")
    print(f"Extendable Docs: {len(SNYK_PRODUCT_CONFIG['extendable_docs'])}")

