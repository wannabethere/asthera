# Category Group Summary

## Final Categories to Process

Based on the schema descriptions and table name patterns, the following **10 categories** are defined:

1. **access requests** - Tables related to access request management
2. **application data** - Tables related to application data and resources
3. **assets** - Tables related to asset management (Asset* tables)
4. **projects** - Tables related to project management (Project* tables)
5. **vulnerabilities** - Tables related to vulnerability management
6. **integrations** - Tables related to integrations and broker connections
7. **configuration** - Tables related to configuration and settings
8. **audit logs** - Tables related to audit logs and catalog progress
9. **risk management** - Tables related to risk assessment and management (Risk* tables)
10. **deployment** - Tables related to deployment processes

## Category Statistics

From the latest run:

| Category | Table Count |
|----------|-------------|
| access requests | 2 unique tables |
| application data | 19 unique tables |
| assets | 9 unique tables |
| projects | 16 unique tables |
| risk management | 7 unique tables |
| integrations | 17 unique tables |
| vulnerabilities | 4 unique tables |
| configuration | 14 unique tables |
| audit logs | 5 unique tables |
| deployment | 14 unique tables |
| **uncategorized** | ~388 unique tables |

*Note: Counts shown are unique tables (each table appears in both definitions and descriptions files)*

## Category Patterns

### 1. Assets
- Pattern: `^Asset[A-Z]`
- Examples: AssetAttributes, AssetClass, AssetRelationships, AssetResponseData

### 2. Projects  
- Pattern: `^Project[A-Z]` or `.*Project[A-Z]`
- Examples: ProjectAttributes, ProjectMeta, AssetProjectAttributes

### 3. Risk Management
- Pattern: `.*Risk[A-Z]` or `.*RiskFactor`
- Examples: AppRiskAttributes, Risk, RiskFactor, DeployedRiskFactor

### 4. Integrations
- Pattern: `.*Integration[A-Z]` or `.*BrokerConnection`
- Examples: AppliedIntegrationRelationship, IntegrationResource, BrokerConnectionIntegrationWithContextResource

### 5. Access Requests
- Pattern: `^AccessRequest`
- Examples: AccessRequest, AccessRequestAttributes

### 6. Vulnerabilities
- Pattern: `^Vulnerability` or `.*Finding`
- Examples: Vulnerability-related tables, Finding-related tables

### 7. Application Data
- Pattern: `^App[A-Z]` (but not AppRisk*)
- Examples: AppBot, AppData, AppInstallWithClient

### 8. Configuration
- Pattern: `^Config` or `.*Settings`
- Examples: Config-related tables, ProjectSettings, AutoDependencyUpgradeSettings

### 9. Audit Logs
- Pattern: `^Audit` or `.*Log` or `Catalog.*`
- Examples: AuditLogSearch, CatalogProgress

### 10. Deployment
- Pattern: `^Deploy` or `.*Deploy`
- Examples: Deploy-related tables, DeployedRiskFactor

## Next Steps

1. Review uncategorized tables to identify additional patterns
2. Consider if uncategorized tables need their own category or can be mapped to existing ones
3. Update category patterns if needed based on review of uncategorized tables
