# Snyk Product Documentation

## Overview

Snyk is a comprehensive AI-driven developer security platform designed to help organizations build software applications quickly while maintaining the highest standards of security throughout the entire software development lifecycle. The platform represents a paradigm shift in how security is integrated into modern software development practices, moving away from traditional reactive security approaches toward a proactive, developer-centric model that embeds security directly into the development workflow. Snyk's core philosophy centers on the principle that security should be a natural part of the development process rather than a separate concern that gets addressed after code is written.

The platform leverages advanced artificial intelligence capabilities, powered by DeepCode AI technology, combined with an industry-leading vulnerability database that continuously monitors and catalogs security threats across millions of open source packages, container images, infrastructure configurations, and application code patterns. This AI-powered approach enables Snyk to provide intelligent, context-aware security recommendations that help developers understand not just what vulnerabilities exist, but why they matter, how they can be exploited, and what the most effective remediation strategies are for their specific use cases.

Snyk operates across multiple dimensions of modern application security, providing comprehensive coverage that spans from the earliest stages of code development through production deployment and ongoing maintenance. The platform integrates seamlessly into developer workflows through native integrations with popular integrated development environments, source code management systems, continuous integration and continuous deployment pipelines, container registries, and cloud infrastructure platforms. This deep integration ensures that security checks happen automatically as part of the natural development process, without requiring developers to context-switch or learn new tools.

One of Snyk's most significant differentiators is its ability to provide full application context when analyzing security issues. Rather than treating vulnerabilities in isolation, the platform understands how different components of an application interact, how data flows through the system, and how security issues in one area might impact other parts of the application. This contextual understanding enables Snyk to prioritize security issues based on actual risk rather than generic severity scores, helping development teams focus their remediation efforts on the vulnerabilities that pose the greatest threat to their specific applications and business operations.

The platform is built on a foundation of comprehensive security intelligence that includes not just vulnerability data, but also information about exploit availability, attack patterns, remediation guidance, and industry best practices. This intelligence is continuously updated as new threats emerge and new research becomes available, ensuring that organizations using Snyk always have access to the most current security information. The platform's ability to learn from the collective security experiences of its user base further enhances its effectiveness, as patterns and solutions discovered by one organization can benefit others facing similar challenges.

Snyk's architecture is designed to scale from individual developers working on small projects to large enterprises managing complex, multi-team development organizations with thousands of developers and millions of lines of code. The platform provides both centralized management capabilities for security teams and distributed, self-service capabilities for development teams, enabling organizations to maintain security governance while empowering developers to take ownership of security in their daily work. This balance between centralized control and distributed execution is critical for modern software development organizations that need to move quickly while maintaining security standards.

### Related Documentation Links
- [Snyk Platform Overview](https://snyk.io/product/)
- [Getting Started with Snyk](https://docs.snyk.io/getting-started)
- [Snyk Web UI Guide](https://docs.snyk.io/getting-started/snyk-web-ui)
- [Snyk CLI Documentation](https://docs.snyk.io/snyk-cli)
- [Snyk Integrations](https://docs.snyk.io/integrations)

### Related API Links
- [Snyk REST API Documentation](https://docs.snyk.io/api)
- [Snyk API Authentication](https://docs.snyk.io/api/authentication-for-api)
- [Snyk API Rate Limits](https://docs.snyk.io/api/rate-limits-for-api-requests)

## Assets

Assets in the Snyk platform represent the fundamental building blocks of an organization's software infrastructure that require security monitoring and protection. The concept of assets extends far beyond traditional application code to encompass the entire technology stack that modern applications depend on, including open source dependencies, container images, infrastructure as code configurations, cloud resources, and application code itself. Snyk's asset management capabilities provide organizations with comprehensive visibility into all the components that make up their software ecosystem, enabling security teams to understand what they have, where it's located, who's responsible for it, and what security risks it might pose.

The platform automatically discovers and catalogs assets through its various integration points, continuously scanning repositories, container registries, cloud environments, and other sources to build a comprehensive inventory of an organization's software assets. This automated discovery process is critical because modern applications often depend on hundreds or thousands of open source packages, multiple container images, and complex cloud infrastructure configurations that would be impossible to track manually. Snyk maintains detailed metadata about each asset, including version information, dependency relationships, usage patterns, and security characteristics, creating a rich knowledge base that supports both security analysis and operational decision-making.

Open source dependencies represent one of the most significant categories of assets that Snyk manages. Modern applications typically depend on hundreds of open source packages, each of which may have its own dependencies, creating complex dependency trees that can be difficult to understand and secure. Snyk maps these dependency relationships, tracking not just direct dependencies but also transitive dependencies that might be several levels deep in the dependency tree. This comprehensive mapping enables the platform to identify vulnerabilities that might exist in deeply nested dependencies that developers aren't directly aware of, ensuring that security issues are discovered even when they're not immediately visible in the code that developers write.

Container images represent another critical asset category that Snyk manages. Containers have become the standard deployment mechanism for modern applications, but they introduce unique security challenges because they package not just application code but also operating system components, runtime environments, and other dependencies. Snyk analyzes container images at multiple levels, examining the base operating system, installed packages, application code, and configuration files to identify security issues across all layers of the container stack. The platform maintains a comprehensive database of container image vulnerabilities, tracking issues in popular base images and providing guidance on how to remediate problems when they're discovered.

Infrastructure as code represents a growing category of assets that Snyk manages, recognizing that cloud infrastructure configurations are as much a part of the application as the code itself. Modern applications often define their infrastructure using code written in languages like Terraform, CloudFormation, or Kubernetes manifests, and misconfigurations in these files can create security vulnerabilities just as serious as bugs in application code. Snyk analyzes infrastructure as code files to identify common misconfigurations, insecure default settings, and violations of security best practices, helping organizations ensure that their cloud infrastructure is configured securely from the start.

The platform's asset management capabilities extend beyond simple inventory to include sophisticated relationship mapping that helps organizations understand how different assets relate to each other. For example, Snyk can identify which applications depend on a particular open source package, which container images are used by which applications, and which cloud resources are associated with which applications. This relationship mapping is crucial for understanding the impact of security issues, as a vulnerability in a widely-used dependency might affect dozens of applications, while a vulnerability in a rarely-used component might have minimal impact. This contextual understanding enables organizations to prioritize remediation efforts based on actual business impact rather than generic severity scores.

Snyk also provides asset lifecycle management capabilities, tracking assets from their initial introduction into the organization through their active use and eventual retirement. This lifecycle tracking helps organizations understand asset usage patterns, identify unused or abandoned assets that might pose security risks, and ensure that security monitoring continues throughout an asset's entire lifecycle. The platform can also track asset ownership and responsibility, ensuring that security issues are routed to the appropriate teams or individuals who can address them effectively.

### Related Documentation Links
- [Managing Projects in Snyk](https://docs.snyk.io/manage-issues/introduction-to-snyk-projects)
- [Snyk Open Source](https://docs.snyk.io/products/snyk-open-source)
- [Snyk Container](https://docs.snyk.io/products/snyk-container)
- [Snyk Infrastructure as Code](https://docs.snyk.io/products/snyk-infrastructure-as-code)
- [Asset Dashboard](https://docs.snyk.io/manage-risk/reporting/asset-dashboard)
- [Dependency Management](https://docs.snyk.io/manage-issues/dependency-management)

### Related API Links
- [Projects API](https://docs.snyk.io/api/projects)
- [Targets API](https://docs.snyk.io/api/targets)
- [Dependencies API](https://docs.snyk.io/api/dependencies)
- [Container Image API](https://docs.snyk.io/api/container-image)

## Vulnerabilities

Vulnerabilities represent the core security threats that Snyk identifies and helps organizations remediate across their entire software ecosystem. The platform maintains one of the industry's most comprehensive vulnerability databases, continuously updated with information about security issues discovered in open source packages, container images, infrastructure configurations, and application code. Snyk's vulnerability intelligence goes far beyond simple lists of known issues, providing deep contextual information about each vulnerability including how it can be exploited, what the potential impact might be, whether exploits are publicly available, and what the most effective remediation strategies are.

The platform's vulnerability detection capabilities operate across multiple layers of the application stack, from the operating system level in container images to application-level code issues. Snyk uses a combination of signature-based detection, behavioral analysis, and AI-powered pattern recognition to identify vulnerabilities, ensuring that both known issues and emerging threats are detected. The platform's vulnerability database is continuously updated as new security research is published, new exploits are discovered, and new attack patterns emerge, ensuring that organizations always have access to the most current threat intelligence.

One of Snyk's most significant differentiators in vulnerability management is its ability to provide contextual risk assessment rather than generic severity scores. The platform understands that the same vulnerability might pose very different levels of risk depending on how it's used in a specific application context. For example, a vulnerability in a package that's used in a critical authentication flow might be much more serious than the same vulnerability in a package used only for logging. Snyk analyzes how vulnerabilities are actually used in an organization's codebase, considering factors like whether vulnerable code paths are reachable, whether sensitive data flows through vulnerable components, and whether the vulnerability is in a production-critical system.

The platform provides detailed vulnerability information that helps developers understand not just what the problem is, but why it matters and how to fix it. Each vulnerability entry includes comprehensive documentation about the issue, including descriptions of the vulnerability, potential attack scenarios, proof-of-concept examples when available, and detailed remediation guidance. This educational approach helps developers learn about security as they work, building security awareness and expertise across the development organization rather than treating security as a black box that only security specialists can understand.

Snyk's vulnerability prioritization capabilities help organizations focus their remediation efforts on the issues that pose the greatest actual risk to their business. The platform considers multiple factors when prioritizing vulnerabilities, including the severity of the vulnerability itself, how it's used in the application context, whether exploits are publicly available, whether the vulnerable component is in production, and the business criticality of the affected systems. This multi-factor prioritization ensures that organizations don't waste time addressing low-risk issues while critical vulnerabilities remain unpatched.

The platform also provides sophisticated vulnerability tracking and management capabilities that help organizations coordinate remediation efforts across large, distributed development organizations. Snyk can track which vulnerabilities have been assigned to which teams, monitor remediation progress, and provide reporting that helps security teams understand overall vulnerability trends and remediation effectiveness. This tracking capability is essential for large organizations that need to coordinate security efforts across multiple teams, time zones, and business units.

Snyk's vulnerability intelligence includes information about exploit availability, which is crucial for understanding the actual threat level posed by a vulnerability. The platform tracks when exploits become publicly available, when proof-of-concept code is published, and when vulnerabilities are actively being exploited in the wild. This intelligence helps organizations understand not just what vulnerabilities exist, but which ones are being actively exploited and therefore require immediate attention. The platform can also provide early warning about vulnerabilities that are likely to become exploited based on patterns observed in similar vulnerabilities.

The platform's vulnerability remediation guidance goes beyond simple patch recommendations to include comprehensive remediation strategies that consider the full context of how vulnerabilities are used in an organization's applications. Snyk can recommend not just upgrading to a patched version, but also alternative approaches like removing unused dependencies, implementing compensating controls, or refactoring code to avoid vulnerable patterns altogether. This comprehensive approach to remediation helps organizations address vulnerabilities in ways that make sense for their specific technical and business contexts.

### Related Documentation Links
- [Understanding Snyk Issues](https://docs.snyk.io/manage-issues/introduction-to-snyk-issues)
- [Vulnerability Database](https://docs.snyk.io/manage-issues/vulnerability-database)
- [Prioritizing Issues](https://docs.snyk.io/manage-issues/issue-management/prioritizing-issues)
- [Fixing Vulnerabilities](https://docs.snyk.io/manage-issues/fixing-vulnerabilities)
- [Snyk Security Policies](https://docs.snyk.io/manage-issues/security-policies)
- [Vulnerability Intelligence](https://docs.snyk.io/manage-issues/vulnerability-intelligence)

### Related API Links
- [Issues API](https://docs.snyk.io/api/issues)
- [Vulnerabilities API](https://docs.snyk.io/api/vulnerabilities)
- [Issue Attributes API](https://docs.snyk.io/api/issue-attributes)
- [Remediation API](https://docs.snyk.io/api/remediation)

## Access Controls

Access controls in the Snyk platform represent a comprehensive framework for managing who can access what resources within the organization's security infrastructure, ensuring that sensitive security information and powerful platform capabilities are only available to authorized individuals and systems. The platform implements sophisticated role-based access control mechanisms that enable organizations to define granular permissions based on job functions, team structures, project assignments, and organizational hierarchies. This access control framework is critical for maintaining security governance in large organizations where different teams need different levels of access to security information and platform capabilities.

Snyk's access control system is built on a foundation of roles and permissions that can be customized to match an organization's specific structure and security requirements. The platform provides predefined roles for common organizational functions like security administrators, development team leads, individual developers, and auditors, but also allows organizations to create custom roles that match their unique organizational structures. Each role defines a set of permissions that determine what actions users in that role can perform, what information they can view, and what resources they can manage within the platform.

The platform's permission model operates at multiple levels of granularity, enabling organizations to control access not just at the platform level, but also at the level of individual projects, applications, repositories, and even specific security issues. This fine-grained control is essential for organizations that need to maintain strict boundaries between different business units, projects, or teams while still providing the access necessary for effective collaboration. For example, a development team might have full access to security information for their own projects but only read-only access to information about other teams' projects, ensuring that teams can focus on their own work without being distracted by irrelevant information.

Snyk integrates with enterprise identity providers and single sign-on systems, enabling organizations to leverage their existing identity management infrastructure rather than maintaining separate user accounts and authentication systems. This integration supports popular identity providers including Active Directory, LDAP, SAML, and OAuth, allowing organizations to use their existing authentication mechanisms and user directories. The platform also supports multi-factor authentication and other advanced authentication mechanisms that organizations might require for enhanced security.

The platform provides comprehensive audit logging that tracks all user actions and access attempts, creating a detailed record of who accessed what information, when they accessed it, and what actions they performed. This audit trail is essential for security compliance, incident investigation, and understanding how the platform is being used across the organization. The audit logs can be exported and integrated with external security information and event management systems, enabling organizations to maintain centralized security monitoring across all their tools and platforms.

Snyk's access control system includes sophisticated delegation capabilities that enable organizations to distribute access management responsibilities while maintaining centralized oversight. For example, project administrators might be able to manage access for their own projects, team leads might be able to manage access for their teams, and security administrators maintain overall control and can override local decisions when necessary. This distributed model of access management is essential for large organizations where centralized management of all access decisions would be impractical, but it's balanced with centralized oversight capabilities that ensure security policies are consistently applied.

The platform also provides access control capabilities for programmatic access through APIs and integrations, recognizing that modern development workflows often involve automated systems that need to interact with security tools. Snyk supports API tokens and service accounts that can be configured with specific permissions, enabling organizations to grant programmatic access to the minimum set of capabilities necessary for each integration or automation use case. This programmatic access control is critical for maintaining security while enabling the automation and integration capabilities that modern development organizations require.

Snyk's access control framework includes capabilities for managing access to sensitive security information, recognizing that vulnerability details, remediation strategies, and security metrics might contain information that could be useful to attackers if it fell into the wrong hands. The platform allows organizations to restrict access to detailed vulnerability information while still providing developers with the information they need to remediate issues, enabling a balance between security through obscurity and the transparency necessary for effective security operations.

The platform also provides access control capabilities specifically designed for compliance and audit scenarios, enabling organizations to grant read-only access to auditors, compliance teams, and other stakeholders who need to review security information but shouldn't be able to modify configurations or access sensitive operational details. These compliance-focused access controls help organizations demonstrate security posture to external auditors, customers, and regulators while maintaining appropriate security boundaries.

### Related Documentation Links
- [User and Group Management](https://docs.snyk.io/user-and-group-management)
- [Role-Based Access Control](https://docs.snyk.io/user-and-group-management/managing-users-and-permissions)
- [Organization Settings](https://docs.snyk.io/user-and-group-management/managing-settings)
- [Single Sign-On (SSO)](https://docs.snyk.io/user-and-group-management/setting-up-sso-for-authentication)
- [API Tokens](https://docs.snyk.io/user-and-group-management/managing-authentication-methods/api-tokens)
- [Service Accounts](https://docs.snyk.io/user-and-group-management/managing-authentication-methods/service-accounts)
- [Audit Logs](https://docs.snyk.io/user-and-group-management/audit-logs)

### Related API Links
- [Organizations API](https://docs.snyk.io/api/organizations)
- [Users API](https://docs.snyk.io/api/users)
- [Groups API](https://docs.snyk.io/api/groups)
- [Roles API](https://docs.snyk.io/api/roles)
- [Service Accounts API](https://docs.snyk.io/api/service-accounts)

## Reporting

Reporting capabilities in the Snyk platform represent a comprehensive framework for transforming raw security data into actionable business intelligence that helps organizations understand their security posture, track progress toward security goals, demonstrate compliance with regulatory requirements, and make informed decisions about security investments and priorities. The platform provides a wide range of reporting capabilities that serve different audiences and purposes, from high-level executive dashboards that provide strategic security overviews to detailed technical reports that help development teams understand and remediate specific security issues.

Executive reporting capabilities provide senior leadership with the information they need to understand overall security posture, track security trends over time, and make strategic decisions about security investments and priorities. These reports typically focus on high-level metrics like total vulnerability counts, remediation rates, security coverage across different parts of the organization, and trends that indicate whether security is improving or deteriorating over time. Executive reports are designed to be consumed quickly by busy executives who need to understand security status at a glance, but they also provide drill-down capabilities that allow executives to explore details when they need deeper understanding.

Compliance reporting capabilities help organizations demonstrate adherence to various regulatory frameworks and industry standards, including SOC 2, ISO 27001, HIPAA, PCI DSS, and others. These reports are specifically designed to address the requirements of different compliance frameworks, providing evidence that security controls are in place, vulnerabilities are being managed, and security processes are being followed. Compliance reports can be customized to match the specific requirements of different frameworks and can be generated on demand or on a scheduled basis to support regular compliance audits and assessments.

Technical reporting capabilities provide development teams and security engineers with the detailed information they need to understand and remediate security issues. These reports include detailed vulnerability information, remediation guidance, code-level details about where issues exist, and recommendations for how to fix problems. Technical reports are designed for audiences with deep technical expertise who need to understand the root causes of security issues and implement specific remediation strategies.

The platform's reporting capabilities include sophisticated data aggregation and analysis features that help organizations understand security trends and patterns that might not be visible when looking at individual security issues in isolation. Snyk can aggregate data across multiple projects, teams, time periods, and vulnerability types to identify trends like whether certain types of vulnerabilities are becoming more common, whether remediation efforts are accelerating or slowing down, and whether security investments in specific areas are producing the desired results. This trend analysis is essential for understanding whether security programs are effective and for identifying areas that might need additional attention or resources.

Custom reporting capabilities enable organizations to create reports that match their specific needs and requirements, whether those needs are driven by unique business contexts, specific compliance requirements, or particular organizational structures. The platform provides flexible reporting tools that allow organizations to select which data to include, how to aggregate and present it, and what format to use for delivery. Custom reports can be scheduled for automatic generation and distribution, ensuring that stakeholders receive the information they need on a regular basis without requiring manual report generation.

The platform's reporting capabilities are designed to support different stakeholder needs and communication styles. Some stakeholders might prefer visual dashboards with charts and graphs, while others might prefer detailed tabular reports with specific metrics and data points. Snyk provides both approaches, enabling organizations to communicate security information in ways that are most effective for different audiences. The platform also supports export capabilities that allow reports to be integrated into other business intelligence tools, presentation software, and documentation systems.

Reporting in Snyk serves multiple critical purposes beyond simple data presentation. Reports help organizations establish security baselines that can be used to measure progress over time, identify areas where security is strong and areas where improvement is needed, and demonstrate return on investment for security programs and initiatives. Reports also serve as communication tools that help security teams explain security status and needs to non-technical stakeholders, enabling better decision-making and resource allocation.

The platform's reporting capabilities include comparative analysis features that help organizations understand how their security posture compares to industry benchmarks, peer organizations, and their own historical performance. This comparative context is essential for understanding whether security metrics represent good or poor performance and for setting realistic security goals and expectations. Comparative reporting helps organizations identify areas where they might be lagging behind industry standards and areas where they might be leading, enabling more informed strategic planning.

Snyk's reporting system also includes capabilities for tracking and demonstrating remediation progress, showing not just what vulnerabilities exist but also how effectively organizations are addressing them. These progress reports help organizations understand whether their remediation efforts are on track, whether they're addressing the highest-priority issues first, and whether their remediation velocity is sufficient to keep up with the discovery of new vulnerabilities. This progress tracking is essential for security program management and for demonstrating to stakeholders that security investments are producing tangible results.

The platform provides reporting capabilities specifically designed for different stages of the software development lifecycle, recognizing that security information needs vary depending on whether code is in development, testing, staging, or production. Development-stage reports might focus on helping developers understand and fix issues before code is deployed, while production-stage reports might focus on monitoring for new vulnerabilities and tracking remediation of issues that are already in production. This lifecycle-aware reporting ensures that stakeholders receive the information that's most relevant to their current concerns and responsibilities.

### Related Documentation Links
- [Snyk Reporting Overview](https://docs.snyk.io/manage-risk/reporting)
- [Available Snyk Reports](https://docs.snyk.io/manage-risk/reporting/available-snyk-reports)
- [Asset Dashboard](https://docs.snyk.io/manage-risk/reporting/asset-dashboard)
- [Compliance Reports](https://docs.snyk.io/manage-risk/reporting/compliance-reports)
- [Executive Reports](https://docs.snyk.io/manage-risk/reporting/executive-reports)
- [Custom Reports](https://docs.snyk.io/manage-risk/reporting/custom-reports)
- [Exporting Reports](https://docs.snyk.io/manage-risk/reporting/exporting-reports)

### Related API Links
- [Reports API](https://docs.snyk.io/api/reports)
- [Metrics API](https://docs.snyk.io/api/metrics)
- [Dashboard API](https://docs.snyk.io/api/dashboard)
- [Export API](https://docs.snyk.io/api/export)
