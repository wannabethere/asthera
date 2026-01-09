"""
Test data for integration tests
Contains sample documents for HIPAA, SOC2, API definitions, metrics registry, and business processes
"""

# Sample HIPAA Control Text
HIPAA_CONTROL_TEXT = """
HIPAA Security Rule - Access Control (164.312(a)(1))

The covered entity must implement technical policies and procedures for electronic information systems 
that maintain electronic protected health information (ePHI) to allow access only to those persons 
or software programs that have been granted access rights as specified in §164.308(a)(4).

This control requires:
1. Unique user identification for each user
2. Emergency access procedures
3. Automatic logoff after period of inactivity
4. Encryption and decryption of ePHI
5. Audit logs of access to ePHI
6. Integrity controls to prevent unauthorized alteration

The organization must ensure that access to ePHI is restricted to authorized personnel only and that 
all access attempts are logged and monitored. This includes both physical and logical access controls.
"""

# Sample SOC2 Control Text
SOC2_CONTROL_TEXT = """
SOC 2 Type II - CC6.1: Logical and Physical Access Controls

The entity implements logical access security software, infrastructure, and architectures over 
protected information assets to protect them from security events to meet the entity's objectives.

Key requirements:
1. Identity and access management (IAM) systems
2. Multi-factor authentication (MFA) for privileged access
3. Role-based access control (RBAC)
4. Regular access reviews and certifications
5. Segregation of duties
6. Password policies and management
7. Session management and timeout controls
8. Network segmentation and firewall rules
9. Physical access controls to data centers
10. Monitoring and alerting for unauthorized access attempts

The entity must demonstrate that access controls are designed, implemented, and operating effectively 
to prevent unauthorized access to systems and data.
"""

# Sample API Definition Document
API_DEFINITION_DOC = """
API Security and Access Control Specification

## Authentication API
Endpoint: /api/v1/auth
Methods: POST, GET, DELETE

### POST /api/v1/auth/login
Authenticates a user and returns an access token.

Request Body:
{
  "username": "string",
  "password": "string",
  "mfa_token": "string (optional)"
}

Response:
{
  "access_token": "jwt_token",
  "refresh_token": "jwt_token",
  "expires_in": 3600,
  "user_id": "uuid",
  "roles": ["admin", "user"]
}

### GET /api/v1/auth/user
Retrieves current authenticated user information.

Headers:
- Authorization: Bearer {access_token}

Response:
{
  "user_id": "uuid",
  "username": "string",
  "email": "string",
  "roles": ["array"],
  "permissions": ["array"],
  "last_login": "timestamp"
}

### DELETE /api/v1/auth/logout
Invalidates the current access token.

Security Requirements:
- All endpoints require HTTPS
- Access tokens expire after 1 hour
- Refresh tokens expire after 30 days
- Failed login attempts are rate-limited (5 per 15 minutes)
- All authentication events are logged
- MFA required for admin accounts
"""

# Sample Metrics Registry with SOC2 Compliance Mapping
METRICS_REGISTRY_DOC = """
Metrics Registry - SOC2 Compliance Mapping

## Access Control Metrics

### AC-001: User Access Review Completion Rate
- **Metric ID**: AC-001
- **Description**: Percentage of user access reviews completed on schedule
- **SOC2 Mapping**: CC6.1 (Logical Access Controls)
- **Target**: >= 95%
- **Measurement**: (Completed Reviews / Total Scheduled Reviews) * 100
- **Frequency**: Monthly
- **Data Source**: IAM System, Access Review Tool
- **Evidence Type**: Access Review Reports, Completion Certificates

### AC-002: Privileged Access MFA Coverage
- **Metric ID**: AC-002
- **Description**: Percentage of privileged accounts with MFA enabled
- **SOC2 Mapping**: CC6.1 (Logical Access Controls)
- **Target**: 100%
- **Measurement**: (Privileged Accounts with MFA / Total Privileged Accounts) * 100
- **Frequency**: Weekly
- **Data Source**: IAM System, MFA Provider
- **Evidence Type**: MFA Configuration Reports, System Logs

### AC-003: Failed Authentication Attempts
- **Metric ID**: AC-003
- **Description**: Number of failed authentication attempts per day
- **SOC2 Mapping**: CC6.1 (Logical Access Controls), CC7.2 (System Monitoring)
- **Target**: < 10 per day (baseline)
- **Measurement**: Count of failed login attempts in 24-hour period
- **Frequency**: Daily
- **Data Source**: Authentication Logs, SIEM System
- **Evidence Type**: Security Event Logs, Alert Reports

### AC-004: Access Rights Certification Rate
- **Metric ID**: AC-004
- **Description**: Percentage of access rights certified by managers
- **SOC2 Mapping**: CC6.1 (Logical Access Controls)
- **Target**: >= 90% within 30 days
- **Measurement**: (Certified Access Rights / Total Access Rights) * 100
- **Frequency**: Quarterly
- **Data Source**: Access Certification Tool, HR System
- **Evidence Type**: Certification Reports, Manager Approvals

## Encryption Metrics

### ENC-001: Data Encryption at Rest Coverage
- **Metric ID**: ENC-001
- **Description**: Percentage of sensitive data encrypted at rest
- **SOC2 Mapping**: CC6.7 (Encryption)
- **Target**: 100%
- **Measurement**: (Encrypted Data Stores / Total Data Stores) * 100
- **Frequency**: Monthly
- **Data Source**: Database Inventory, Encryption Management System
- **Evidence Type**: Encryption Status Reports, Configuration Audits

### ENC-002: TLS/SSL Certificate Validity
- **Metric ID**: ENC-002
- **Description**: Percentage of certificates expiring within 30 days
- **SOC2 Mapping**: CC6.7 (Encryption)
- **Target**: 0% (all certificates renewed before expiration)
- **Measurement**: (Certificates Expiring in 30 Days / Total Certificates) * 100
- **Frequency**: Weekly
- **Data Source**: Certificate Management System
- **Evidence Type**: Certificate Inventory Reports, Renewal Logs

## Monitoring Metrics

### MON-001: Security Event Detection Time
- **Metric ID**: MON-001
- **Description**: Average time to detect security events (in minutes)
- **SOC2 Mapping**: CC7.2 (System Monitoring)
- **Target**: < 15 minutes
- **Measurement**: Average time from event occurrence to detection
- **Frequency**: Daily
- **Data Source**: SIEM System, Security Operations Center
- **Evidence Type**: Incident Reports, Detection Logs

### MON-002: Log Retention Compliance
- **Metric ID**: MON-002
- **Description**: Percentage of systems with logs retained per policy
- **SOC2 Mapping**: CC7.2 (System Monitoring)
- **Target**: 100%
- **Measurement**: (Systems with Compliant Log Retention / Total Systems) * 100
- **Frequency**: Monthly
- **Data Source**: Log Management System, System Inventory
- **Evidence Type**: Log Retention Reports, Configuration Audits
"""

# Sample Business Process Wiki Page Content
BUSINESS_PROCESS_WIKI = """
Employee Onboarding Process - Access Provisioning

## Overview
This document describes the process for provisioning access to new employees during onboarding.

## Process Steps

### Step 1: HR Creates Employee Record
- HR creates employee record in HRIS system
- Employee assigned to department and manager
- Employee role and job title defined
- Process Owner: HR Department
- System: HRIS (Workday)
- Duration: 1 business day

### Step 2: Manager Approves Access Request
- Manager reviews employee role and responsibilities
- Manager selects required access based on job function
- Manager submits access request form
- Process Owner: Hiring Manager
- System: Access Request Portal
- Duration: 2 business days

### Step 3: IT Security Review
- IT Security reviews access request for compliance
- Security team verifies role-based access is appropriate
- Security team checks for segregation of duties conflicts
- Process Owner: IT Security Team
- System: IAM System, Compliance Tool
- Duration: 1 business day

### Step 4: Access Provisioning
- IT Operations provisions access in target systems
- Access granted based on approved request
- MFA enabled for privileged accounts
- Access documented in IAM system
- Process Owner: IT Operations
- Systems: Active Directory, Application Systems, IAM Platform
- Duration: 1 business day

### Step 5: Access Verification
- New employee receives access credentials
- Employee verifies access to required systems
- Employee completes security awareness training
- Process Owner: New Employee, IT Helpdesk
- System: Various Application Systems
- Duration: 1 business day

## Access Types

### Standard Employee Access
- Email account (Office 365)
- Network file shares (based on department)
- Standard business applications
- VPN access (if remote worker)

### Privileged Access (if applicable)
- Admin accounts (requires MFA)
- Database access
- Cloud console access
- Production system access

## Compliance Requirements

### SOC2 Requirements
- CC6.1: Access must be approved and documented
- CC6.2: Segregation of duties must be verified
- CC6.3: MFA required for privileged access
- CC7.2: All access provisioning must be logged

### HIPAA Requirements (if handling ePHI)
- 164.308(a)(4): Access authorization and establishment
- 164.312(a)(1): Access control implementation
- 164.312(b): Audit controls for access logs

## Key Metrics
- Average time to provision access: 5 business days
- Access request approval rate: 95%
- Access provisioning accuracy: 98%
- Employee satisfaction with access: 4.2/5.0

## Related Processes
- Employee Offboarding (access deprovisioning)
- Access Review and Certification (quarterly)
- Access Change Management (role changes)
"""

# Sample Context Description for Healthcare Organization
HEALTHCARE_CONTEXT_DESCRIPTION = """
We are a mid-sized healthcare organization with approximately 500 employees. We operate a network 
of clinics and provide telemedicine services. We handle electronic protected health information (ePHI) 
for approximately 50,000 patients annually.

Our technology stack includes:
- Electronic Health Records (EHR) system (Epic)
- Patient portal and telemedicine platform
- Billing and claims processing systems
- Cloud infrastructure (AWS) for data storage
- Office 365 for email and collaboration

We are preparing for our first HIPAA compliance audit in 90 days. We have basic security controls 
in place but need to strengthen our access controls, encryption, and audit logging capabilities.

Our organization is in a developing maturity stage for compliance. We have a dedicated IT security 
team of 3 people and work with external consultants for compliance guidance.

Regulatory frameworks applicable:
- HIPAA (Health Insurance Portability and Accountability Act)
- HITECH Act
- State healthcare privacy regulations

We process the following types of sensitive data:
- ePHI (electronic Protected Health Information)
- PII (Personally Identifiable Information)
- Financial data (billing and insurance information)
"""

# Sample Context Description for Technology Company
TECH_COMPANY_CONTEXT_DESCRIPTION = """
We are a fast-growing technology company with 200 employees, providing SaaS solutions to enterprise 
customers. We process customer data including PII and business information.

Our technology infrastructure:
- Multi-cloud deployment (AWS, Azure)
- Microservices architecture
- Kubernetes orchestration
- CI/CD pipelines
- Customer-facing web applications
- Internal business systems

We are preparing for SOC 2 Type II certification and need to demonstrate effective controls over 
security, availability, and confidentiality. Our audit is scheduled in 120 days.

Our compliance maturity is at a developing stage. We have a security team of 5 people and are 
building out our compliance program.

Regulatory frameworks:
- SOC 2 (Service Organization Control 2)
- GDPR (for EU customers)
- CCPA (California Consumer Privacy Act)

Data types we handle:
- Customer PII
- Business confidential information
- Authentication credentials
- System logs and monitoring data

We have moderate automation capabilities and are working to improve our security monitoring and 
access management processes.
"""

