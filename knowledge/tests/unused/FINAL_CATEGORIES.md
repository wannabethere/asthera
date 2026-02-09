# Final Categories for Table Processing

## Overview

This document lists the **15 final categories** that are being used to categorize tables based on table name patterns. These categories align with the schema descriptions categories (with additional categories for groups, organizations, memberships and roles, issues, and artifacts).

## Category List

1. **access requests** - Access request management tables
2. **application data** - Application data and resource tables  
3. **assets** - Asset management tables (Asset* pattern)
4. **projects** - Project management tables (Project* pattern)
5. **vulnerabilities** - Vulnerability and finding tables
6. **integrations** - Integration and broker connection tables
7. **configuration** - Configuration and settings tables
8. **audit logs** - Audit log and catalog progress tables
9. **risk management** - Risk assessment and management tables (Risk* pattern)
10. **deployment** - Deployment process tables
11. **groups** - Group management and policy tables (Group* pattern)
12. **organizations** - Organization management tables (Org* pattern)
13. **memberships and roles** - Membership and role management tables (Membership*, Role* patterns)
14. **issues** - Issue tracking and management tables (Issue*, Issues* patterns)
15. **artifacts** - Artifact repository tables (Artifact* pattern)

## Category Patterns & Examples

### 1. access requests
- **Pattern**: `^AccessRequest`
- **Examples**: AccessRequest, AccessRequestAttributes
- **Count**: 2 unique tables

### 2. application data
- **Pattern**: `^App[A-Z]` (excluding AppRisk* which goes to risk management)
- **Examples**: AppBot, AppData, AppInstallWithClient, AppInstance
- **Count**: 19 unique tables

### 3. assets
- **Pattern**: `^Asset[A-Z]`
- **Examples**: AssetAttributes, AssetClass, AssetRelationships, AssetResponseData, AssetProjectAttributes
- **Count**: 9 unique tables

### 4. projects
- **Pattern**: `^Project[A-Z]` or `.*Project[A-Z]` (but AssetProject* goes to assets first)
- **Examples**: ProjectAttributes, ProjectMeta, ProjectRelationships, ProjectSettings
- **Count**: 16 unique tables

### 5. risk management
- **Pattern**: `.*Risk[A-Z]` or `.*RiskFactor`
- **Examples**: AppRiskAttributes, Risk, RiskFactor, DeployedRiskFactor, RiskScore
- **Count**: 7 unique tables

### 6. integrations
- **Pattern**: `.*Integration[A-Z]` or `.*BrokerConnection`
- **Examples**: AppliedIntegrationRelationship, IntegrationResource, BrokerConnectionIntegrationWithContextResource, OrgIntegrationResource
- **Count**: 17 unique tables

### 7. vulnerabilities
- **Pattern**: `^Vulnerability` or `.*Finding`
- **Examples**: Vulnerability-related tables, Finding-related tables
- **Count**: 4 unique tables

### 8. configuration
- **Pattern**: `^Config` or `.*Settings`
- **Examples**: Config-related tables, ProjectSettings, AutoDependencyUpgradeSettings
- **Count**: 14 unique tables

### 9. audit logs
- **Pattern**: `^Audit` or `.*Log` or `Catalog.*`
- **Examples**: AuditLogSearch, CatalogProgress, CatalogProgressAttributes
- **Count**: 5 unique tables

### 10. deployment
- **Pattern**: `^Deploy` or `.*Deploy`
- **Examples**: Deploy-related tables, DeployedRiskFactor
- **Count**: 14 unique tables

### 11. groups
- **Pattern**: `^Group`
- **Examples**: Group, GroupAttributes, GroupMembership, GroupPolicy, GroupPolicyAction, GroupPolicyCondition
- **Count**: 41 unique tables

### 12. organizations
- **Pattern**: `^Org[A-Z]` or `^Organization`
- **Examples**: Org, OrgAttributes, OrgInvitation, OrgMembership, OrgRole, Organization-related tables
- **Count**: 23 unique tables

### 13. memberships and roles
- **Pattern**: `.*Membership` or `.*Role` or `^Member`
- **Examples**: OrgMembership, GroupMembership, TenantMembership, OrgRole, TenantRole, MemberRoleRelationship
- **Count**: 25 unique tables

### 14. issues
- **Pattern**: `^Issue`
- **Examples**: Issue, IssueAttributes, Issues, IssuesCountAttributes, IssuesMeta, IssuesResponse
- **Count**: 7 unique tables

### 15. artifacts
- **Pattern**: `.*Artifact`
- **Examples**: ArtifactoryAttributes, ArtifactoryCrAttributes, GoogleArtifactCrAttributes
- **Count**: 3 unique tables

## Processing Status

✅ **Completed**: Both `table_definitions_20260123_180157_Snyk.json` and `table_descriptions_20260123_180157_Snyk.json` have been updated with category group descriptions.

Each table now has the following added to its description:
- In `page_content`: `" This is a {category}-related table."`
- In `metadata.description`: `" This is a {category}-related table."`

## Notes

- Tables are matched in order of pattern specificity (more specific patterns checked first)
- Some tables may match multiple patterns; the first match wins
- Approximately 295 unique tables remain uncategorized and may need additional pattern definitions
- The uncategorized tables can be reviewed to identify additional patterns if needed

## Files Updated

1. `/knowledge/indexing_preview/table_definitions/table_definitions_20260123_180157_Snyk.json`
2. `/knowledge/indexing_preview/table_descriptions/table_descriptions_20260123_180157_Snyk.json`

## Script Location

The update script is located at: `/knowledge/update_table_categories.py`
