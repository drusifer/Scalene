# **Codename: Project Scalene**

**Rationale:** The "Triangle of Doom" relies on a symmetrical, closed loop of trust exploitation between a sensitive source, the agent context, and an untrusted destination. By intercepting arguments and decoupling data provenance from payload execution, we break the symmetry of the exploit. We transform a dangerous closed loop into a heavily managed, irregular boundary—effectively shattering the triangle.

## **1\. Business Requirements Document (BRD)**

### **1.1 Executive Summary**

As organizations rapidly integrate autonomous AI software engineering tools (e.g., Claude Code, Cursor) into production environments, the risk of accidental data exfiltration has spiked significantly. Current Data Loss Prevention (DLP) tools rely heavily on post-hoc content inspection, which introduces high latency and processing overhead.  
**Project Scalene** establishes a lightweight, deterministic, protocol-agnostic data-provenance framework. By tracking where data originated instead of parsing what it contains, Project Scalene prevents the "Triangle of Doom" scenario—ensuring sensitive enterprise data is never leaked to untrusted external tool endpoints.

### **1.2 Business Objectives & Value Drivers**

* **Mitigate Modern Agentic Risks:** Directly address emerging Agentic AI Security Risks, specifically tool misuse, exploitation, and cross-tool state leakage.  
* **Maximize Engineering Velocity:** Replace disruptive binary blocks with adaptive, structural masking, ensuring developer workflows continue uninterrupted within corporate guardrails.  
* **Zero Overhead Compliance:** Maintain a continuously updated, git-attributable local inventory of trusted and sensitive data boundaries to simplify compliance audits (e.g., SOC2, ISO 27001).

### **1.3 Scope of System**

| In Scope | Out of Scope |
| :---- | :---- |
| Application-level tool hooks (pre\_tool\_call, post\_tool\_call). | Deep semantic or natural-language analysis of LLM outputs. |
| Configuration via project-level YAML files using JSONPath. | Enforcing endpoint restrictions at the OS/Kernel level (e.g., eBPF/Landlock). |
| Blind, schema-driven structural payload masking. | Remediation of historical logs or data breaches. |
| Developer interactive workflow for explicit rule onboarding. | Identity and Access Management (IAM) role provisioning. |

### **1.4 High-Level Functional Requirements (FR)**

* **FR-1:** The system must maintain stateful taint labels (has\_sensitive\_data, has\_untrusted\_data) tied directly to the lifetime of an agent's execution context.  
* **FR-2:** The system must intercept every tool call and evaluate parameters using JSONPath against configured rule inventories.  
* **FR-3:** When an agent attempts to route sensitive data to an untrusted destination, the tool must automatically strip or mask the parameter data payload without throwing a runtime error.  
* **FR-4:** New allow/trust patterns added by a developer must trigger an automated verification check (data/threat scan) before updating configurations.

### **1.5 Non-Functional Requirements (NFR)**

* **Performance:** Pre-tool argument evaluation and rule matching must complete in under **15 milliseconds** to preserve real-time developer interactions.  
* **Security & Isolation:** The scanning infrastructure must run in an isolated memory space to avoid "scanner reflection loops."  
* **Portability:** Hooks must follow standard cross-platform conventions, executing seamlessly across local environments, Docker containers, and cloud development environments.

## **2\. Product Requirements Document (PRD)**

### **2.1 User Persona**

* **Role:** AI-Enabled Software Engineer / DevOps Engineer.  
* **Needs:** Wants autonomous AI coding assistants to handle repetitive tasks (refactoring, dependency management, web research) without the risk of leaking local configuration variables, source code, or private credentials.  
* **Frustration:** Traditional corporate security tools block tools aggressively, breaking agent context loops and forcing constant manual restarts.

### **2.2 System Data Flow**

\[Agent Initiates Tool Use\]  
             │  
             ▼  
   \[pre\_tool\_call\_hook\]  
             │  
   (Is Context Tainted & Target Untrusted?)  
          ├── YES ──\> \[Apply Structural Masking\] ──\> (Execute Safely)  
          └── NO  ──\> (Execute Directly)  
             │  
             ▼  
   \[post\_tool\_call\_hook\]  
             │  
   (Update Taint Labels via JSONPath Provenance)  
             │  
             ▼  
\[Return Sanitized Output to Context Window\]

### **2.3 Feature Specifications**

#### **2.3.1 Stateful Context Taint Machine**

* **Description:** A session-level memory layer tracking two sticky booleans: has\_sensitive\_data and has\_untrusted\_data.  
* **Behavior:** Once a flag is flipped to True, it persists through the entire agent lifecycle until the context window is explicitly cleared or reset by the system.  
* **Rule Engine:** \* If data is read from a tool matching the sensitive inventory, has\_sensitive\_data is marked True.  
  * If data is read from a tool *not* matching the trusted inventory, has\_untrusted\_data is marked True.

#### **2.3.2 Structural Metadata Rule Mapping (scalene\_policy.yaml)**

* **Description:** Project-specific configuration files defining parameters via JSONPath expressions.  
* **Capabilities:** Must support matching nested JSON parameters, terminal shell strings ($.command), full URL paths, file systems paths, and database targets (tables/columns).

YAML  
version: "1.0"  
project: "scalene-managed-workspace"

defaults:  
  sensitive\_by\_default: true  
  untrusted\_by\_default: true

non\_sensitive\_allowlist:  
  \- tool: "view\_file"  
    jsonpath: "$.path"  
    pattern: "^/workspaces/project/public/.\*"  
    description: "Public asset directories"

trusted\_sources\_list:  
  \- tool: "read\_file"  
    jsonpath: "$.path"  
    pattern: "^/workspaces/project/config/environments/.\*\\\\.json$"  
    description: "Sanitized local configuration"

#### **2.3.3 Blind Structural Masking (Maximal Allowance)**

* **Description:** Rather than scanning parameters for text markers (like regex or PII identifiers), Project Scalene utilizes a mapping schema to determine fields carrying raw payloads.  
* **Behavior:** When the Triangle of Doom boundary is breached, the hook automatically overwrites target data payload arguments (e.g., the body of an HTTP request or the text content parameter of a file writer) with a static string placeholder: \[MASKED\_BY\_POLICY\_PROVENANCE\_GUARD\]. This strips data out of the call while keeping the execution syntax intact.

#### **2.3.4 Dynamic Onboarding & Verification Loops**

* **Description:** When an agent triggers a block, developers can run an onboarding command to whitelist a narrow rule pattern.  
* **Automated Scans:** Before writing to the project’s local YAML configuration or the global enterprise tracking ledger, Project Scalene initiates target asset checks:  
  * **Allowlist Onboarding:** Runs a rapid static check (e.g., credentials/secrets scanning) on the destination asset. If sensitive keys are found, onboarding fails to ensure no sensitive data is mixed with untrusted data.  
  * **Trust List Onboarding:** Runs automated reputation/threat-intelligence lookups on the target resource or domain.

### **2.4 Lifecycle Error & Exception Handling**

* **Malformed JSONPath Handling:** If an agent generates arguments that fail to match expected JSONPath patterns, the rule evaluations fail-safe to sensitive \= true and trusted \= false.  
* **Scanner Loop Prevention:** Scanner workflows must use specific context bypass tokens (SCALENE\_BYPASS=1) to prevent their actions from triggering the interception hooks recursively.