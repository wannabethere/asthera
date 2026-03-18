-- ============================================================================
-- Seed: Real CVE-2024 / CVE-2025 data
-- Run AFTER migrate_schema.sql
-- All CVEs are real, publicly documented vulnerabilities.
-- ATT&CK mappings are based on MITRE documentation and CISA KEV entries.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. CWE → ATT&CK crosswalk (subset — most common CWEs in 2024/2025 CVEs)
-- ============================================================================

INSERT INTO cwe_technique_mappings (cwe_id, technique_id, tactic, confidence, notes) VALUES
-- Command/Code Injection
('CWE-77',  'T1059',     'execution',             'high',   'OS command injection maps directly to scripting interpreter execution'),
('CWE-77',  'T1190',     'initial-access',        'high',   'Unauthenticated command injection is a public-facing exploit vector'),
('CWE-78',  'T1059',     'execution',             'high',   'OS command injection via shell metacharacters'),
('CWE-78',  'T1190',     'initial-access',        'high',   'Shell injection in public-facing services'),
('CWE-94',  'T1059',     'execution',             'high',   'Code injection enables arbitrary code execution'),
('CWE-917', 'T1059',     'execution',             'high',   'Expression language injection → code execution'),
-- Authentication / Access Control
('CWE-287', 'T1078',     'initial-access',        'high',   'Authentication bypass enables use of valid account without credentials'),
('CWE-287', 'T1078',     'persistence',           'medium', 'Auth bypass can be used to maintain persistent access'),
('CWE-306', 'T1078',     'initial-access',        'high',   'Missing auth for critical function = valid account abuse'),
('CWE-306', 'T1190',     'initial-access',        'high',   'Unauthenticated access to public-facing function'),
('CWE-290', 'T1078',     'initial-access',        'high',   'Auth bypass by spoofing'),
('CWE-798', 'T1078',     'initial-access',        'high',   'Hard-coded credentials are pre-placed valid accounts'),
('CWE-798', 'T1078',     'persistence',           'high',   'Hard-coded creds provide durable persistent access'),
-- Memory Safety
('CWE-120', 'T1203',     'execution',             'high',   'Buffer overflow enables arbitrary code execution client-side'),
('CWE-120', 'T1190',     'initial-access',        'medium', 'Network-reachable buffer overflow'),
('CWE-125', 'T1005',     'collection',            'medium', 'Out-of-bounds read enables data exposure'),
('CWE-122', 'T1203',     'execution',             'high',   'Heap buffer overflow → code execution'),
('CWE-416', 'T1203',     'execution',             'high',   'Use-after-free → code execution'),
('CWE-476', 'T1499',     'impact',                'medium', 'NULL pointer dereference → denial of service'),
-- Path Traversal / File Inclusion
('CWE-22',  'T1083',     'discovery',             'high',   'Path traversal enables directory and file discovery'),
('CWE-22',  'T1005',     'collection',            'high',   'Path traversal enables collection of local files'),
('CWE-22',  'T1190',     'initial-access',        'medium', 'Path traversal in public-facing app'),
('CWE-434', 'T1105',     'command-and-control',   'high',   'Unrestricted file upload enables payload delivery'),
('CWE-434', 'T1059',     'execution',             'high',   'Uploaded file executed server-side'),
-- SQL Injection
('CWE-89',  'T1190',     'initial-access',        'high',   'SQL injection in public-facing application'),
('CWE-89',  'T1078',     'initial-access',        'high',   'SQLi used to extract/bypass credentials'),
('CWE-89',  'T1005',     'collection',            'high',   'SQL injection enables data exfiltration'),
-- SSRF / XXE / Deserialization
('CWE-918', 'T1090',     'command-and-control',   'high',   'SSRF proxies attacker requests through server'),
('CWE-918', 'T1083',     'discovery',             'medium', 'SSRF used for internal network reconnaissance'),
('CWE-502', 'T1059',     'execution',             'high',   'Unsafe deserialization enables arbitrary code execution'),
('CWE-502', 'T1190',     'initial-access',        'high',   'Deserialization vulnerability in public-facing component'),
-- Privilege Escalation
('CWE-269', 'T1068',     'privilege-escalation',  'high',   'Improper privilege management → local privilege escalation'),
('CWE-732', 'T1068',     'privilege-escalation',  'medium', 'Incorrect permission assignment enables privilege escalation')
ON CONFLICT (cwe_id, technique_id, tactic) DO NOTHING;


-- ============================================================================
-- 2. cve_intelligence — real 2024/2025 CVEs
-- ============================================================================

INSERT INTO cve_intelligence (
    cve_id, description, cvss_score, cvss_vector, attack_vector, attack_complexity,
    privileges_required, cwe_ids, affected_products, epss_score, exploit_available,
    exploit_maturity, kev_listed, published_date, last_modified,
    technique_ids, tactics
) VALUES

-- CVE-2024-3400: Palo Alto PAN-OS GlobalProtect Command Injection (CVSS 10.0)
('CVE-2024-3400',
 'A command injection vulnerability in the GlobalProtect feature of Palo Alto Networks PAN-OS '
 'allows an unauthenticated attacker to execute arbitrary code with root privileges on the firewall.',
 10.0, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-77'], ARRAY['Palo Alto PAN-OS 10.2', 'Palo Alto PAN-OS 11.0', 'Palo Alto PAN-OS 11.1'],
 0.9712, TRUE, 'weaponised', TRUE, '2024-04-12', '2024-04-19',
 ARRAY['T1190', 'T1059.004', 'T1068', 'T1133', 'T1098', 'T1562.004'],
 ARRAY['initial-access', 'execution', 'privilege-escalation', 'persistence', 'defense-evasion']),

-- CVE-2024-21762: Fortinet FortiOS Out-of-Bound Write (CVSS 9.6)
('CVE-2024-21762',
 'An out-of-bounds write vulnerability in FortiOS allows a remote unauthenticated attacker '
 'to execute arbitrary code or commands via specially crafted HTTP requests.',
 9.6, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-787'], ARRAY['Fortinet FortiOS 6.x', 'Fortinet FortiOS 7.x', 'Fortinet FortiProxy'],
 0.9435, TRUE, 'weaponised', TRUE, '2024-02-09', '2024-02-15',
 ARRAY['T1190', 'T1059', 'T1068'],
 ARRAY['initial-access', 'execution', 'privilege-escalation']),

-- CVE-2024-1709: ConnectWise ScreenConnect Auth Bypass (CVSS 10.0)
('CVE-2024-1709',
 'An authentication bypass vulnerability in ConnectWise ScreenConnect allows an unauthenticated '
 'attacker to create an admin account and gain full access to the ScreenConnect instance.',
 10.0, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-288'], ARRAY['ConnectWise ScreenConnect < 23.9.8'],
 0.9821, TRUE, 'weaponised', TRUE, '2024-02-21', '2024-03-01',
 ARRAY['T1190', 'T1078', 'T1059', 'T1105'],
 ARRAY['initial-access', 'execution', 'command-and-control']),

-- CVE-2024-6387: OpenSSH regreSSHion Race Condition RCE (CVSS 8.1)
('CVE-2024-6387',
 'A signal handler race condition in OpenSSH server (sshd) allows an unauthenticated '
 'remote attacker to execute arbitrary code as root on glibc-based Linux systems.',
 8.1, 'CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'high', 'none',
 ARRAY['CWE-362'], ARRAY['OpenSSH < 4.4p1', 'OpenSSH >= 8.5p1 < 9.8p1'],
 0.0521, TRUE, 'poc', FALSE, '2024-07-01', '2024-07-08',
 ARRAY['T1190', 'T1068', 'T1059.004'],
 ARRAY['initial-access', 'privilege-escalation', 'execution']),

-- CVE-2024-38193: Windows Ancillary Function Driver LPE (CVSS 7.8)
('CVE-2024-38193',
 'A use-after-free vulnerability in the Windows Ancillary Function Driver for WinSock '
 'allows a local attacker to elevate privileges to SYSTEM.',
 7.8, 'CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H',
 'local', 'low', 'low',
 ARRAY['CWE-416'], ARRAY['Windows 10', 'Windows 11', 'Windows Server 2019', 'Windows Server 2022'],
 0.1842, TRUE, 'weaponised', TRUE, '2024-08-13', '2024-08-19',
 ARRAY['T1068', 'T1546'],
 ARRAY['privilege-escalation', 'persistence']),

-- CVE-2024-4577: PHP CGI Argument Injection (CVSS 9.8)
('CVE-2024-4577',
 'An argument injection vulnerability in PHP on Windows allows an unauthenticated attacker '
 'to execute arbitrary code when PHP is used in CGI mode. Bypasses CVE-2012-1823 patch.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-88'], ARRAY['PHP 8.1 < 8.1.29', 'PHP 8.2 < 8.2.20', 'PHP 8.3 < 8.3.8'],
 0.9614, TRUE, 'weaponised', TRUE, '2024-06-09', '2024-06-17',
 ARRAY['T1190', 'T1059.004', 'T1059.001'],
 ARRAY['initial-access', 'execution']),

-- CVE-2024-23897: Jenkins Path Traversal / Arbitrary File Read (CVSS 9.8)
('CVE-2024-23897',
 'Jenkins has a path traversal vulnerability in its CLI that allows unauthenticated '
 'attackers to read arbitrary files, including secrets, credentials, and Java heap dumps.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-22'], ARRAY['Jenkins < 2.442', 'Jenkins LTS < 2.426.3'],
 0.9756, TRUE, 'weaponised', TRUE, '2024-01-24', '2024-02-02',
 ARRAY['T1190', 'T1083', 'T1005', 'T1552'],
 ARRAY['initial-access', 'discovery', 'collection', 'credential-access']),

-- CVE-2024-27198: JetBrains TeamCity Auth Bypass (CVSS 9.8)
('CVE-2024-27198',
 'An authentication bypass vulnerability in JetBrains TeamCity web interface allows '
 'an unauthenticated attacker to gain administrative access to the TeamCity server.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-288', 'CWE-306'], ARRAY['JetBrains TeamCity < 2023.11.4'],
 0.9734, TRUE, 'weaponised', TRUE, '2024-03-06', '2024-03-12',
 ARRAY['T1190', 'T1078', 'T1059', 'T1105', 'T1195.002'],
 ARRAY['initial-access', 'execution', 'command-and-control', 'supply-chain']),

-- CVE-2024-55591: Fortinet FortiOS Auth Bypass (CVSS 9.6)
('CVE-2024-55591',
 'An authentication bypass vulnerability in FortiOS and FortiProxy allows a remote '
 'unauthenticated attacker to gain super-admin privileges via crafted requests to Node.js websocket module.',
 9.6, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-290'], ARRAY['Fortinet FortiOS 7.0.0-7.0.16', 'Fortinet FortiProxy 7.0.x', 'Fortinet FortiProxy 7.2.x'],
 0.8934, TRUE, 'weaponised', TRUE, '2025-01-14', '2025-01-20',
 ARRAY['T1190', 'T1078', 'T1098'],
 ARRAY['initial-access', 'persistence', 'privilege-escalation']),

-- CVE-2025-0282: Ivanti Connect Secure Stack Overflow RCE (CVSS 9.0)
('CVE-2025-0282',
 'A stack-based buffer overflow in Ivanti Connect Secure, Policy Secure, and ZTA Gateways '
 'allows a remote unauthenticated attacker to achieve remote code execution.',
 9.0, 'CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H',
 'network', 'high', 'none',
 ARRAY['CWE-121'], ARRAY['Ivanti Connect Secure < 22.7R2.5', 'Ivanti Policy Secure < 22.7R1.2', 'Ivanti ZTA Gateways < 22.8R2.2'],
 0.9203, TRUE, 'weaponised', TRUE, '2025-01-08', '2025-01-15',
 ARRAY['T1190', 'T1059', 'T1068', 'T1133'],
 ARRAY['initial-access', 'execution', 'privilege-escalation', 'persistence']),

-- CVE-2024-49113: Windows LDAP Remote Code Execution (CVSS 9.8) — LDAPNightmare
('CVE-2024-49113',
 'A remote code execution vulnerability in Windows LDAP allows an unauthenticated '
 'attacker to execute arbitrary code on Windows domain controllers via specially crafted packets.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-122'], ARRAY['Windows Server 2019', 'Windows Server 2022', 'Windows Server 2025'],
 0.2341, TRUE, 'poc', FALSE, '2025-01-14', '2025-01-21',
 ARRAY['T1190', 'T1210', 'T1059'],
 ARRAY['initial-access', 'lateral-movement', 'execution']),

-- CVE-2024-20353: Cisco ASA / FTD DoS (CVSS 8.6) — ArcaneDoor campaign
('CVE-2024-20353',
 'A vulnerability in Cisco ASA and FTD software allows an unauthenticated remote attacker '
 'to cause the device to reload unexpectedly. Exploited in ArcaneDoor espionage campaign.',
 8.6, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:N/I:N/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-835'], ARRAY['Cisco ASA', 'Cisco Firepower Threat Defense'],
 0.9512, TRUE, 'weaponised', TRUE, '2024-04-24', '2024-05-01',
 ARRAY['T1499', 'T1190', 'T1133'],
 ARRAY['impact', 'initial-access', 'persistence']),

-- CVE-2024-30051: Windows DWM Core Library LPE (CVSS 7.8)
('CVE-2024-30051',
 'A use-after-free in Windows Desktop Window Manager (DWM) Core Library allows a local '
 'attacker to elevate privileges to SYSTEM. Exploited by QakBot operators.',
 7.8, 'CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H',
 'local', 'low', 'low',
 ARRAY['CWE-416'], ARRAY['Windows 10', 'Windows 11', 'Windows Server 2016', 'Windows Server 2019', 'Windows Server 2022'],
 0.7823, TRUE, 'weaponised', TRUE, '2024-05-14', '2024-05-20',
 ARRAY['T1068', 'T1546.015'],
 ARRAY['privilege-escalation', 'persistence']),

-- CVE-2025-21298: Windows OLE Remote Code Execution (CVSS 9.8)
('CVE-2025-21298',
 'A remote code execution vulnerability in Windows Object Linking and Embedding (OLE) '
 'allows an attacker to execute arbitrary code via a malicious email opened in Microsoft Outlook.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-416'], ARRAY['Microsoft Outlook', 'Microsoft Office', 'Windows (all supported versions)'],
 0.1123, FALSE, 'none', FALSE, '2025-01-14', '2025-01-14',
 ARRAY['T1566.001', 'T1203', 'T1059'],
 ARRAY['initial-access', 'execution']),

-- CVE-2024-26169: Windows Error Reporting LPE (CVSS 7.8) — used by Black Basta
('CVE-2024-26169',
 'An improper access control vulnerability in Windows Error Reporting Service allows a '
 'local attacker to elevate privileges to SYSTEM without user interaction.',
 7.8, 'CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H',
 'local', 'low', 'low',
 ARRAY['CWE-269'], ARRAY['Windows 10', 'Windows 11', 'Windows Server 2019', 'Windows Server 2022'],
 0.6342, TRUE, 'weaponised', TRUE, '2024-04-09', '2024-04-16',
 ARRAY['T1068', 'T1574'],
 ARRAY['privilege-escalation', 'defense-evasion']),

-- CVE-2024-47575: Fortinet FortiManager Remote Code Execution (CVSS 9.8) — FortiJump
('CVE-2024-47575',
 'A missing authentication vulnerability in FortiManager fgfmd daemon allows a remote '
 'unauthenticated attacker to execute arbitrary code via specially crafted requests. '
 'Part of the FortiJump campaign targeting managed service providers.',
 9.8, 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
 'network', 'low', 'none',
 ARRAY['CWE-306'], ARRAY['Fortinet FortiManager 6.x', 'Fortinet FortiManager 7.x'],
 0.9621, TRUE, 'weaponised', TRUE, '2024-10-23', '2024-10-30',
 ARRAY['T1190', 'T1059', 'T1078', 'T1195.002'],
 ARRAY['initial-access', 'execution', 'persistence', 'supply-chain'])

ON CONFLICT (cve_id) DO UPDATE SET
    epss_score       = EXCLUDED.epss_score,
    exploit_maturity = EXCLUDED.exploit_maturity,
    kev_listed       = EXCLUDED.kev_listed,
    technique_ids    = EXCLUDED.technique_ids,
    tactics          = EXCLUDED.tactics;


-- ============================================================================
-- 3. cve_attack_mapping — technique mappings for all CVEs above
-- ============================================================================

INSERT INTO cve_attack_mapping (
    cve_id, attack_technique_id, attack_tactic, attack_tactic_slug,
    mapping_source, confidence_score,
    cvss_score, epss_score, attack_vector, cwe_ids,
    exploit_available, exploit_maturity, notes
) VALUES

-- CVE-2024-3400 (PAN-OS)
('CVE-2024-3400','T1190',     'Initial Access',         'initial-access',        'mitre_official', 0.97, 10.0, 0.9712, 'network', ARRAY['CWE-77'], TRUE, 'weaponised', 'Unauthenticated exploit of GlobalProtect interface'),
('CVE-2024-3400','T1059.004', 'Execution',              'execution',             'ai_inferred',    0.95, 10.0, 0.9712, 'network', ARRAY['CWE-77'], TRUE, 'weaponised', 'Command injection executes via Unix shell as root'),
('CVE-2024-3400','T1068',     'Privilege Escalation',   'privilege-escalation',  'ai_inferred',    0.90, 10.0, 0.9712, 'network', ARRAY['CWE-77'], TRUE, 'weaponised', 'Exploit yields root on firewall OS'),
('CVE-2024-3400','T1133',     'Persistence',            'persistence',           'ai_inferred',    0.75, 10.0, 0.9712, 'network', ARRAY['CWE-77'], TRUE, 'weaponised', 'Root on VPN gateway enables persistent external access'),
('CVE-2024-3400','T1562.004', 'Defense Evasion',        'defense-evasion',       'ai_inferred',    0.70, 10.0, 0.9712, 'network', ARRAY['CWE-77'], TRUE, 'weaponised', 'Root enables modification of firewall rules'),

-- CVE-2024-21762 (FortiOS)
('CVE-2024-21762','T1190',    'Initial Access',         'initial-access',        'mitre_official', 0.94, 9.6, 0.9435, 'network', ARRAY['CWE-787'], TRUE, 'weaponised', 'Out-of-bounds write via HTTP to public-facing FortiOS'),
('CVE-2024-21762','T1059',    'Execution',              'execution',             'ai_inferred',    0.88, 9.6, 0.9435, 'network', ARRAY['CWE-787'], TRUE, 'weaponised', 'Memory corruption enables arbitrary code execution'),
('CVE-2024-21762','T1068',    'Privilege Escalation',   'privilege-escalation',  'ai_inferred',    0.82, 9.6, 0.9435, 'network', ARRAY['CWE-787'], TRUE, 'weaponised', 'Exploit achieves elevated OS privileges'),

-- CVE-2024-1709 (ConnectWise ScreenConnect)
('CVE-2024-1709', 'T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.98, 10.0, 0.9821, 'network', ARRAY['CWE-288'], TRUE, 'weaponised', 'Auth bypass creates admin account on public-facing RMM'),
('CVE-2024-1709', 'T1078',   'Persistence',            'persistence',           'mitre_official', 0.95, 10.0, 0.9821, 'network', ARRAY['CWE-288'], TRUE, 'weaponised', 'Created admin account provides persistent valid credentials'),
('CVE-2024-1709', 'T1059',   'Execution',              'execution',             'ai_inferred',    0.90, 10.0, 0.9821, 'network', ARRAY['CWE-288'], TRUE, 'weaponised', 'Admin access enables remote command execution via RMM'),
('CVE-2024-1709', 'T1105',   'Command and Control',    'command-and-control',   'ai_inferred',    0.85, 10.0, 0.9821, 'network', ARRAY['CWE-288'], TRUE, 'weaponised', 'ScreenConnect admin used to push payloads to managed endpoints'),

-- CVE-2024-6387 (OpenSSH regreSSHion)
('CVE-2024-6387', 'T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.72, 8.1, 0.0521, 'network', ARRAY['CWE-362'], TRUE, 'poc', 'Race condition in sshd; exploitation is probabilistic'),
('CVE-2024-6387', 'T1068',   'Privilege Escalation',   'privilege-escalation',  'ai_inferred',    0.88, 8.1, 0.0521, 'network', ARRAY['CWE-362'], TRUE, 'poc', 'Successful exploit yields root on Linux server'),
('CVE-2024-6387', 'T1059.004','Execution',             'execution',             'ai_inferred',    0.85, 8.1, 0.0521, 'network', ARRAY['CWE-362'], TRUE, 'poc', 'Code execution as root via signal handler corruption'),

-- CVE-2024-38193 (Windows AFD LPE)
('CVE-2024-38193','T1068',   'Privilege Escalation',   'privilege-escalation',  'mitre_official', 0.90, 7.8, 0.1842, 'local',   ARRAY['CWE-416'], TRUE, 'weaponised', 'AFD use-after-free → SYSTEM privileges, used by Lazarus'),
('CVE-2024-38193','T1546',   'Persistence',            'persistence',           'ai_inferred',    0.65, 7.8, 0.1842, 'local',   ARRAY['CWE-416'], TRUE, 'weaponised', 'SYSTEM-level access enables event-triggered persistence'),

-- CVE-2024-4577 (PHP CGI)
('CVE-2024-4577', 'T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.96, 9.8, 0.9614, 'network', ARRAY['CWE-88'],  TRUE, 'weaponised', 'Argument injection via URL in PHP CGI on Windows'),
('CVE-2024-4577', 'T1059.004','Execution',             'execution',             'ai_inferred',    0.94, 9.8, 0.9614, 'network', ARRAY['CWE-88'],  TRUE, 'weaponised', 'PHP executes attacker-controlled shell commands'),
('CVE-2024-4577', 'T1059.001','Execution',             'execution',             'ai_inferred',    0.80, 9.8, 0.9614, 'network', ARRAY['CWE-88'],  TRUE, 'weaponised', 'PowerShell execution as secondary stage on Windows'),

-- CVE-2024-23897 (Jenkins)
('CVE-2024-23897','T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.97, 9.8, 0.9756, 'network', ARRAY['CWE-22'],  TRUE, 'weaponised', 'Unauthenticated CLI path traversal on public-facing Jenkins'),
('CVE-2024-23897','T1083',   'Discovery',              'discovery',             'mitre_official', 0.90, 9.8, 0.9756, 'network', ARRAY['CWE-22'],  TRUE, 'weaponised', 'Arbitrary file read enables filesystem enumeration'),
('CVE-2024-23897','T1552',   'Credential Access',      'credential-access',     'ai_inferred',    0.92, 9.8, 0.9756, 'network', ARRAY['CWE-22'],  TRUE, 'weaponised', 'secrets.json, credentials.xml, and heap dumps expose secrets'),
('CVE-2024-23897','T1005',   'Collection',             'collection',            'ai_inferred',    0.85, 9.8, 0.9756, 'network', ARRAY['CWE-22'],  TRUE, 'weaponised', 'Arbitrary file read used to exfiltrate build artifacts and configs'),

-- CVE-2024-27198 (TeamCity)
('CVE-2024-27198','T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.97, 9.8, 0.9734, 'network', ARRAY['CWE-288','CWE-306'], TRUE, 'weaponised', 'Auth bypass grants unauthenticated admin on CI/CD server'),
('CVE-2024-27198','T1078',   'Initial Access',         'initial-access',        'mitre_official', 0.95, 9.8, 0.9734, 'network', ARRAY['CWE-288','CWE-306'], TRUE, 'weaponised', 'Created admin account used as valid credential'),
('CVE-2024-27198','T1195.002','Initial Access',        'initial-access',        'ai_inferred',    0.88, 9.8, 0.9734, 'network', ARRAY['CWE-288','CWE-306'], TRUE, 'weaponised', 'Compromise of CI/CD enables supply chain poisoning'),
('CVE-2024-27198','T1059',   'Execution',              'execution',             'ai_inferred',    0.90, 9.8, 0.9734, 'network', ARRAY['CWE-288','CWE-306'], TRUE, 'weaponised', 'Admin access enables build script and runner command execution'),

-- CVE-2024-55591 (FortiOS auth bypass — 2025 disclosure)
('CVE-2024-55591','T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.93, 9.6, 0.8934, 'network', ARRAY['CWE-290'], TRUE, 'weaponised', 'Auth bypass via Node.js websocket on internet-facing FortiOS'),
('CVE-2024-55591','T1078',   'Persistence',            'persistence',           'ai_inferred',    0.89, 9.6, 0.8934, 'network', ARRAY['CWE-290'], TRUE, 'weaponised', 'Super-admin session established for durable access'),
('CVE-2024-55591','T1098',   'Privilege Escalation',   'privilege-escalation',  'ai_inferred',    0.85, 9.6, 0.8934, 'network', ARRAY['CWE-290'], TRUE, 'weaponised', 'Super-admin enables account manipulation and credential theft'),

-- CVE-2025-0282 (Ivanti Connect Secure)
('CVE-2025-0282','T1190',    'Initial Access',         'initial-access',        'mitre_official', 0.95, 9.0, 0.9203, 'network', ARRAY['CWE-121'], TRUE, 'weaponised', 'Stack overflow in Ivanti VPN gateway exploited pre-auth'),
('CVE-2025-0282','T1059',    'Execution',              'execution',             'ai_inferred',    0.91, 9.0, 0.9203, 'network', ARRAY['CWE-121'], TRUE, 'weaponised', 'Buffer overflow enables arbitrary command execution'),
('CVE-2025-0282','T1068',    'Privilege Escalation',   'privilege-escalation',  'ai_inferred',    0.88, 9.0, 0.9203, 'network', ARRAY['CWE-121'], TRUE, 'weaponised', 'Exploit yields elevated privileges on VPN appliance'),
('CVE-2025-0282','T1133',    'Persistence',            'persistence',           'ai_inferred',    0.82, 9.0, 0.9203, 'network', ARRAY['CWE-121'], TRUE, 'weaponised', 'Compromised VPN gateway enables persistent external access'),

-- CVE-2024-49113 (Windows LDAP — LDAPNightmare)
('CVE-2024-49113','T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.75, 9.8, 0.2341, 'network', ARRAY['CWE-122'], TRUE, 'poc', 'Network-reachable LDAP heap overflow on domain controllers'),
('CVE-2024-49113','T1210',   'Lateral Movement',       'lateral-movement',      'ai_inferred',    0.80, 9.8, 0.2341, 'network', ARRAY['CWE-122'], TRUE, 'poc', 'DC exploitation enables lateral movement via AD'),
('CVE-2024-49113','T1059',   'Execution',              'execution',             'ai_inferred',    0.82, 9.8, 0.2341, 'network', ARRAY['CWE-122'], TRUE, 'poc', 'Heap corruption enables code execution on domain controller'),

-- CVE-2024-20353 (Cisco ASA — ArcaneDoor)
('CVE-2024-20353','T1499',   'Impact',                 'impact',                'mitre_official', 0.88, 8.6, 0.9512, 'network', ARRAY['CWE-835'], TRUE, 'weaponised', 'Infinite loop causes device reload — used to disrupt operations'),
('CVE-2024-20353','T1190',   'Initial Access',         'initial-access',        'ai_inferred',    0.75, 8.6, 0.9512, 'network', ARRAY['CWE-835'], TRUE, 'weaponised', 'Exploit in ArcaneDoor campaign against network edge devices'),
('CVE-2024-20353','T1133',   'Persistence',            'persistence',           'ai_inferred',    0.70, 8.6, 0.9512, 'network', ARRAY['CWE-835'], TRUE, 'weaponised', 'Edge device compromise enables persistent external access'),

-- CVE-2024-30051 (Windows DWM — QakBot)
('CVE-2024-30051','T1068',   'Privilege Escalation',   'privilege-escalation',  'mitre_official', 0.93, 7.8, 0.7823, 'local',   ARRAY['CWE-416'], TRUE, 'weaponised', 'DWM use-after-free → SYSTEM, dropped by QakBot operators'),
('CVE-2024-30051','T1546.015','Persistence',           'persistence',           'ai_inferred',    0.70, 7.8, 0.7823, 'local',   ARRAY['CWE-416'], TRUE, 'weaponised', 'SYSTEM access via component object model hijacking for persistence'),

-- CVE-2025-21298 (Windows OLE/Outlook)
('CVE-2025-21298','T1566.001','Initial Access',        'initial-access',        'mitre_official', 0.85, 9.8, 0.1123, 'network', ARRAY['CWE-416'], FALSE, 'none', 'Malicious email triggers OLE vulnerability in Outlook'),
('CVE-2025-21298','T1203',   'Execution',              'execution',             'mitre_official', 0.88, 9.8, 0.1123, 'network', ARRAY['CWE-416'], FALSE, 'none', 'OLE use-after-free enables client-side code execution'),
('CVE-2025-21298','T1059',   'Execution',              'execution',             'ai_inferred',    0.80, 9.8, 0.1123, 'network', ARRAY['CWE-416'], FALSE, 'none', 'Post-exploitation command execution after Outlook RCE'),

-- CVE-2024-26169 (Windows Error Reporting — Black Basta)
('CVE-2024-26169','T1068',   'Privilege Escalation',   'privilege-escalation',  'mitre_official', 0.91, 7.8, 0.6342, 'local',   ARRAY['CWE-269'], TRUE, 'weaponised', 'WER improper access control → SYSTEM, used in Black Basta ransomware chain'),
('CVE-2024-26169','T1574',   'Defense Evasion',        'defense-evasion',       'ai_inferred',    0.72, 7.8, 0.6342, 'local',   ARRAY['CWE-269'], TRUE, 'weaponised', 'Hijack execution via WER binary planting'),

-- CVE-2024-47575 (FortiManager — FortiJump)
('CVE-2024-47575','T1190',   'Initial Access',         'initial-access',        'mitre_official', 0.97, 9.8, 0.9621, 'network', ARRAY['CWE-306'], TRUE, 'weaponised', 'Missing auth in fgfmd daemon → unauthenticated RCE on FortiManager'),
('CVE-2024-47575','T1059',   'Execution',              'execution',             'ai_inferred',    0.93, 9.8, 0.9621, 'network', ARRAY['CWE-306'], TRUE, 'weaponised', 'Code execution on FortiManager after unauthenticated access'),
('CVE-2024-47575','T1078',   'Persistence',            'persistence',           'ai_inferred',    0.88, 9.8, 0.9621, 'network', ARRAY['CWE-306'], TRUE, 'weaponised', 'Admin access to FortiManager enables persistent account creation'),
('CVE-2024-47575','T1195.002','Initial Access',        'initial-access',        'ai_inferred',    0.90, 9.8, 0.9621, 'network', ARRAY['CWE-306'], TRUE, 'weaponised', 'FortiManager controls MSP-managed devices — supply chain risk')

ON CONFLICT (cve_id, attack_technique_id) DO UPDATE SET
    attack_tactic_slug  = EXCLUDED.attack_tactic_slug,
    confidence_score    = EXCLUDED.confidence_score,
    cvss_score          = EXCLUDED.cvss_score,
    epss_score          = EXCLUDED.epss_score,
    exploit_maturity    = EXCLUDED.exploit_maturity;


-- ============================================================================
-- 4. cpe_dictionary — affected products for the CVEs above
-- ============================================================================

INSERT INTO cpe_dictionary (cpe_uri, vendor, product, version, cpe_title) VALUES
('cpe:2.3:o:paloaltonetworks:pan-os:10.2:*:*:*:*:*:*:*', 'paloaltonetworks', 'pan-os', '10.2', 'Palo Alto Networks PAN-OS 10.2'),
('cpe:2.3:o:paloaltonetworks:pan-os:11.0:*:*:*:*:*:*:*', 'paloaltonetworks', 'pan-os', '11.0', 'Palo Alto Networks PAN-OS 11.0'),
('cpe:2.3:o:paloaltonetworks:pan-os:11.1:*:*:*:*:*:*:*', 'paloaltonetworks', 'pan-os', '11.1', 'Palo Alto Networks PAN-OS 11.1'),
('cpe:2.3:o:fortinet:fortios:7.0:*:*:*:*:*:*:*',         'fortinet', 'fortios', '7.0', 'Fortinet FortiOS 7.0'),
('cpe:2.3:o:fortinet:fortios:7.2:*:*:*:*:*:*:*',         'fortinet', 'fortios', '7.2', 'Fortinet FortiOS 7.2'),
('cpe:2.3:o:fortinet:fortios:6.4:*:*:*:*:*:*:*',         'fortinet', 'fortios', '6.4', 'Fortinet FortiOS 6.4'),
('cpe:2.3:a:connectwise:screenconnect:23.9.7:*:*:*:*:*:*:*', 'connectwise', 'screenconnect', '23.9.7', 'ConnectWise ScreenConnect 23.9.7'),
('cpe:2.3:a:openbsd:openssh:9.7:p1:*:*:*:*:*:*',         'openbsd', 'openssh', '9.7p1', 'OpenSSH 9.7p1'),
('cpe:2.3:a:php:php:8.1.28:*:*:*:*:*:*:*',               'php', 'php', '8.1.28', 'PHP 8.1.28'),
('cpe:2.3:a:php:php:8.2.19:*:*:*:*:*:*:*',               'php', 'php', '8.2.19', 'PHP 8.2.19'),
('cpe:2.3:a:jenkins:jenkins:2.441:*:*:*:*:*:*:*',        'jenkins', 'jenkins', '2.441', 'Jenkins 2.441'),
('cpe:2.3:a:jetbrains:teamcity:2023.11.3:*:*:*:*:*:*:*', 'jetbrains', 'teamcity', '2023.11.3', 'JetBrains TeamCity 2023.11.3'),
('cpe:2.3:o:microsoft:windows_10:22h2:*:*:*:*:*:x64:*',  'microsoft', 'windows_10', '22h2', 'Microsoft Windows 10 22H2'),
('cpe:2.3:o:microsoft:windows_11:23h2:*:*:*:*:*:x64:*',  'microsoft', 'windows_11', '23h2', 'Microsoft Windows 11 23H2'),
('cpe:2.3:o:microsoft:windows_server_2022:-:*:*:*:*:*:*:*','microsoft','windows_server_2022','-','Microsoft Windows Server 2022'),
('cpe:2.3:a:ivanti:connect_secure:22.7:r2.4:*:*:*:*:*:*','ivanti','connect_secure','22.7r2.4','Ivanti Connect Secure 22.7R2.4'),
('cpe:2.3:a:cisco:adaptive_security_appliance_software:9.18:*:*:*:*:*:*:*','cisco','adaptive_security_appliance_software','9.18','Cisco ASA 9.18'),
('cpe:2.3:a:fortinet:fortimanager:7.4:*:*:*:*:*:*:*',    'fortinet', 'fortimanager', '7.4', 'Fortinet FortiManager 7.4')
ON CONFLICT (cpe_uri) DO NOTHING;


-- ============================================================================
-- 5. cve_cpe_affected — link CVEs to CPEs
-- ============================================================================

INSERT INTO cve_cpe_affected (cve_id, cpe_uri, version_start, version_end, version_end_including) VALUES
('CVE-2024-3400',  'cpe:2.3:o:paloaltonetworks:pan-os:10.2:*:*:*:*:*:*:*', '10.2.0', '10.2.9',  FALSE),
('CVE-2024-3400',  'cpe:2.3:o:paloaltonetworks:pan-os:11.0:*:*:*:*:*:*:*', '11.0.0', '11.0.4',  FALSE),
('CVE-2024-3400',  'cpe:2.3:o:paloaltonetworks:pan-os:11.1:*:*:*:*:*:*:*', '11.1.0', '11.1.2',  FALSE),
('CVE-2024-21762', 'cpe:2.3:o:fortinet:fortios:7.0:*:*:*:*:*:*:*',         '7.0.0',  '7.0.14',  FALSE),
('CVE-2024-21762', 'cpe:2.3:o:fortinet:fortios:7.2:*:*:*:*:*:*:*',         '7.2.0',  '7.2.7',   FALSE),
('CVE-2024-21762', 'cpe:2.3:o:fortinet:fortios:6.4:*:*:*:*:*:*:*',         '6.4.0',  '6.4.15',  FALSE),
('CVE-2024-1709',  'cpe:2.3:a:connectwise:screenconnect:23.9.7:*:*:*:*:*:*:*', NULL, '23.9.7',  TRUE),
('CVE-2024-6387',  'cpe:2.3:a:openbsd:openssh:9.7:p1:*:*:*:*:*:*',         '8.5p1',  '9.7p1',   FALSE),
('CVE-2024-4577',  'cpe:2.3:a:php:php:8.1.28:*:*:*:*:*:*:*',               '8.1.0',  '8.1.28',  TRUE),
('CVE-2024-4577',  'cpe:2.3:a:php:php:8.2.19:*:*:*:*:*:*:*',               '8.2.0',  '8.2.19',  TRUE),
('CVE-2024-23897', 'cpe:2.3:a:jenkins:jenkins:2.441:*:*:*:*:*:*:*',        NULL,     '2.441',   TRUE),
('CVE-2024-27198', 'cpe:2.3:a:jetbrains:teamcity:2023.11.3:*:*:*:*:*:*:*', NULL,     '2023.11.3',TRUE),
('CVE-2024-38193', 'cpe:2.3:o:microsoft:windows_10:22h2:*:*:*:*:*:x64:*',  NULL,     NULL,      FALSE),
('CVE-2024-38193', 'cpe:2.3:o:microsoft:windows_11:23h2:*:*:*:*:*:x64:*',  NULL,     NULL,      FALSE),
('CVE-2024-38193', 'cpe:2.3:o:microsoft:windows_server_2022:-:*:*:*:*:*:*:*',NULL,   NULL,      FALSE),
('CVE-2025-0282',  'cpe:2.3:a:ivanti:connect_secure:22.7:r2.4:*:*:*:*:*:*', NULL,    '22.7r2.4',TRUE),
('CVE-2024-20353', 'cpe:2.3:a:cisco:adaptive_security_appliance_software:9.18:*:*:*:*:*:*:*',NULL,NULL,FALSE),
('CVE-2024-47575', 'cpe:2.3:a:fortinet:fortimanager:7.4:*:*:*:*:*:*:*',    '6.0.0', '7.4.4',   FALSE)
ON CONFLICT (cve_id, cpe_uri) DO NOTHING;


-- ============================================================================
-- 6. cve_cache — pre-populate NVD cache stubs so API calls are skipped
-- ============================================================================

INSERT INTO cve_cache (cve_id, nvd_data, epss_data, kev_data, expires_at, source)
SELECT
    ci.cve_id,
    jsonb_build_object(
        'id',          ci.cve_id,
        'cvssScore',   ci.cvss_score,
        'cvssVector',  ci.cvss_vector,
        'description', ci.description,
        'cweIds',      to_jsonb(ci.cwe_ids),
        'publishedDate', ci.published_date
    ) AS nvd_data,
    jsonb_build_object(
        'cve',   ci.cve_id,
        'epss',  ci.epss_score,
        'percentile', round((ci.epss_score * 100)::numeric, 2)
    ) AS epss_data,
    CASE WHEN ci.kev_listed THEN
        jsonb_build_object('cveID', ci.cve_id, 'listed', TRUE)
    ELSE '{}'::jsonb END AS kev_data,
    NOW() + INTERVAL '7 days',
    'seed'
FROM cve_intelligence ci
ON CONFLICT (cve_id) DO NOTHING;

COMMIT;

-- Quick check
SELECT
    'cve_intelligence'       AS tbl, COUNT(*) FROM cve_intelligence UNION ALL
SELECT 'cve_attack_mapping',          COUNT(*) FROM cve_attack_mapping UNION ALL
SELECT 'cwe_technique_mappings',      COUNT(*) FROM cwe_technique_mappings UNION ALL
SELECT 'cpe_dictionary',              COUNT(*) FROM cpe_dictionary UNION ALL
SELECT 'cve_cpe_affected',            COUNT(*) FROM cve_cpe_affected UNION ALL
SELECT 'cve_cache',                   COUNT(*) FROM cve_cache
ORDER BY tbl;
