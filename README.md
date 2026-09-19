# ERA ERP / BaseRow Manager

> **A specialized, agile Manufacturing ERP and Bill of Materials (BOM) management platform built on top of Baserow for ERA internal operations.**

---

> [!WARNING]
> ### ⚠️ Important Scope & Intended Use Disclaimer
> **This software was custom-developed specifically for the internal needs and unique manufacturing processes of ERA.**
>
> - **Not a General Commercial ERP:** This tool is strictly tailored to ERA's hardware assembly workflow and does **not** compete with commercial ERP platforms.
> - **External Use Not Advised:** The use of this system by other startups or third-party businesses is **strongly discouraged**. Every hardware startup possesses unique organizational structures, accounting rules, procurement practices, and manufacturing lifecycles. This system intentionally omits standard business modules in favor of bespoke assembly mechanics.

---

## 📖 Table of Contents

- [Why ERA ERP? (The Inception Story)](#-why-era-erp-the-inception-story)
- [Comparison: ERA ERP vs. ERPNext vs. Priority ERP](#-comparison-era-erp-vs-erpnext-vs-priority-erp)
- [Capabilities of This Specialized ERP](#-capabilities-of-this-specialized-erp)
- [What This ERP Does NOT Do (Out-of-Scope Capabilities)](#-what-this-erp-does-not-do-out-of-scope-capabilities)
- [System Architecture](#-system-architecture)
- [Setup & Environment Configuration](#-setup--environment-configuration)
- [Model Context Protocol (MCP) Server](#-model-context-protocol-mcp-server)
- [OAuth 2.1 Authorization Server (Remote MCP Clients)](#-oauth-21-authorization-server-remote-mcp-clients)
- [Docker Packaging & Execution](#-docker-packaging--execution)
- [Local Development & Testing](#-local-development--testing)
- [Project Structure](#-project-structure)

---

## 💡 Why ERA ERP? (The Inception Story)

Traditional commercial and open-source enterprise ERP solutions—most notably **ERPNext**—are notoriously heavy, complex, and rigid. While ERPNext provides an expansive monolithic suite, its learning curve is steep, and customizing its DocType hierarchy for rapid, iterative hardware engineering and assembly proved overly complex and slow for a nimble engineering team.

**ERA ERP** was created to address this gap:
* **Zero Bloat & Maximum Customization:** Instead of wrestling with monolithic frameworks, ERA ERP utilizes **[Baserow](https://baserow.io/)** as an open, relational, no-code/low-code single source of truth.
* **Purpose-Built for Hardware Assembly:** Specifically designed for electronics and mechanical hardware assembly, multi-tier BOM trees, dynamic Work Instructions (WIs), tolling quantities, and part lifecycle states.
* **Agile Orchestration Layer:** A lightweight Python Flask backend and modern web frontend serve as an intelligent orchestration layer on top of Baserow's API, enabling instant modifications to data structures and views.

---

## ⚖️ Comparison: ERA ERP vs. ERPNext vs. Priority ERP

| Dimension | ERA ERP (Internal Tool) | ERPNext (Open-Source Monolith) | Priority ERP (Enterprise Commercial) |
| :--- | :--- | :--- | :--- |
| **Primary Target** | ERA internal hardware & assembly teams | Broad SMEs needing all-in-one operations | Mid-to-large industrial manufacturers |
| **BOM / Assembly Model** | Dynamic multi-tier tree, live assembly graph, step-by-step SOP/WI generation | Multi-level BOM with routing & operations | Complex industrial BOM with work centers & capacity scheduling |
| **SOP & Work Instructions** | Native step builder, tolling math, step photos, automated DOCX export | Basic rich text instructions / task attachments | Comprehensive ECO/EWM shop-floor tracking & quality gates |
| **BOM Balance & Validation** | Automated BOM equilibrium check & problem rule scanner | Standard quantity rollups | Rigorous MRP II explosion & capacity validation |
| **Learning Curve** | Minimal (intuitive web UI for shop floor) | High (extensive Frappe framework concepts) | Very High (requires specialized consultants/training) |
| **Customization Effort** | Instant (via Baserow tables & Python API) | Moderate-High (Python/JS DocTypes, Frappe apps) | High (requires proprietary SDK, triggers, forms) |
| **Accounting & Financials** | ❌ None | ✅ Full general ledger, AP/AR, taxes, banking | ✅ Enterprise GL, multi-currency, audit trails |
| **HR & Payroll** | ❌ None | ✅ Complete HRMS & payroll | ✅ Enterprise HRMS, time & attendance |
| **CRM & Sales Pipeline** | ❌ None | ✅ Full CRM, leads, quotes, customer portal | ✅ Comprehensive enterprise CRM & quotes |
| **MRP & Capacity Planning**| ❌ None (manual / threshold-based) | ✅ Full automated MRP engine | ✅ Advanced finite capacity scheduling & MRP II |

---

## ✨ Capabilities of This Specialized ERP

- **Interactive Multi-Level BOM Tree:** Algorithmically converts flat relational tables into nested, interactive, multi-tiered BOM hierarchies with parent/child quantity cascading.
- **Assembly Nexus & Graph Explorer:** Visualizes relational assembly dependencies and bidirectional parent/child node relationships.
- **Dynamic Work Instruction (WI) & SOP Engine:** Author step-by-step assembly instructions, assign tolling item quantities, upload step-specific imagery, and export polished DOCX work instructions using customized templates.
- **Automated BOM Equilibrium (Balance) Check:** Mathematically verifies that every child component in an assembly hierarchy is fully accounted for across instruction sets.
- **Problem & Quality Scanner:** Automated rule engine highlighting missing datasheets, missing images, invalid lifecycle states, or broken assembly connections.
- **Part Number (PN) Categorization & Revision Tracking:** Prefix-based categorization (e.g., Raw Materials, Mechanical COTS, Electrical Custom, Packaging) and alphanumeric revision management.
- **Item Lifecycle State Management:** Clear status gating (*Production Use*, *Engineering Use*, *Finish Stock*, *EOL*, *Discard*).
- **Manufacturer & Supplier Directory:** Contact, vendor, and manufacturer directory linking parts directly to external distributors and datasheets.

---

## 🚫 What This ERP Does NOT Do (Out-of-Scope Capabilities)

Because this tool was built exclusively for assembly engineering and BOM management, standard commercial ERP domains are intentionally excluded:

1. **No Financial Accounting or Bookkeeping:**
   - No General Ledger (GL), Accounts Payable (AP), Accounts Receivable (AR).
   - No tax calculations, VAT reporting, bank reconciliation, or financial statements (P&L, Balance Sheet).
2. **No HRMS or Payroll:**
   - No employee directory, payroll calculations, leave requests, or timesheet logging.
3. **No CRM, Sales & Quoting:**
   - No customer relationship management, sales pipeline, lead scoring, or customer-facing quotation generation.
4. **No Automated MRP II & Shop-Floor Machine Scheduling:**
   - No automated material requirements planning (MRP) explosion across procurement orders.
   - No work center loading, machine downtime scheduling, or shift management.
5. **No Multi-Warehouse Logistics & Barcode Scanning:**
   - No bin/shelf location tracking, automated pick-and-pack workflows, or carrier/shipping API integrations.
6. **No Formal Invoicing & Purchasing Workflows:**
   - No multi-level Purchase Order (PO) approval hierarchies, automated 3-way invoice matching, or electronic data interchange (EDI).

---

## 🏗 System Architecture

ERA ERP utilizes a **Three-Container Architecture** designed to run alongside an existing local Baserow instance (e.g., managed via Dockge/WSL or standalone Docker):

- **`era-frontend` (Port 3000:80):** High-performance Nginx web server hosting the compiled Vite/React single-page application.
- **`era-backend` (Ports 5000:5000 & 8001:8001):** Core Python service providing the Flask REST API (port 5000) and native Model Context Protocol (MCP) server over SSE (port 8001). Handles business logic, BOM tree generation, Work Instructions, tolling equilibrium, and Baserow API communication.
- **`era-oauth` (Port 10000:10000):** Dedicated OAuth 2.1 authorization server container running the backend image with an alternative entrypoint (`--oauth-server`). Implements RFC 8414 metadata, Dynamic Client Registration (RFC 7591 DCR), CIMD validation, and PKCE authorization for remote MCP clients.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Browser / Client / Remote AI Agents                      │
└───────┬──────────────────────┬──────────────────────┬────────────────┬──────┘
        │                      │                      │                │
  HTTP Port 3000         HTTP Port 5000         SSE Port 8001    HTTP Port 10000
        ▼                      ▼                      ▼                ▼
┌───────────────┐      ┌───────────────────────────────────┐    ┌───────────────┐
│ era-frontend  │      │            era-backend            │    │   era-oauth   │
│(Nginx + Vite) │      │   (Flask API 5000 / MCP SSE 8001) │    │  (OAuth 2.1)  │
└───────────────┘      └─────────────────┬─────────────────┘    └───────────────┘
                                         │
                                 REST API Token Auth
                                         ▼
                              ┌─────────────────────┐
                              │  Baserow Instance   │
                              │   (Database API)    │
                              └─────────────────────┘
```

---

## ⚙️ Setup & Environment Configuration

All Baserow database connection credentials and table IDs are supplied to the application and Docker containers via environment variables.

### 1. Create your `.env` file

Copy the provided `.env.example` template:

```bash
# On Linux / macOS / WSL
cp .env.example .env

# On Windows PowerShell
Copy-Item .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` to match your Baserow deployment:

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `BASEROW_API_URL` | Base URL of your running Baserow instance | `http://localhost:7070` |
| `BASEROW_TOKEN` | Database API Token generated in Baserow | `<your-baserow-api-token>` |
| `BASEROW_ADMIN_EMAIL` | Baserow administrative email *(optional / migrations)* | `admin@example.com` |
| `BASEROW_ADMIN_PASSWORD` | Baserow administrative password *(optional / migrations)* | `********` |
| `BASEROW_TABLE_BOM` | Table ID for BOM items | `508` |
| `BASEROW_TABLE_ASSEMBLY` | Table ID for parent/child assembly relations | `701` |
| `BASEROW_TABLE_INSTRUCTIONS`| Table ID for assembly instruction steps | `5770` |
| `BASEROW_TABLE_PN_CATEGORIES`| Table ID for part number categories | `42471` |
| `BASEROW_TABLE_ITEM_STATES` | Table ID for item lifecycle states | `48537` |
| `BASEROW_TABLE_WI_TEMPLATES`| Table ID for Work Instruction docx templates | `48538` |
| `BASEROW_TABLE_MANUFACTURERS`| Table ID for manufacturers | `683` |
| `BASEROW_TABLE_SUPPLIERS` | Table ID for suppliers | `682` |
| `BASEROW_TABLE_CONTACTS` | Table ID for supplier/manufacturer contacts | `684` |
| `VITE_API_URL` | URL used by the frontend to communicate with backend | `http://localhost:5000` |
| `FRONTEND_PORT` | Host port mapped to frontend container | `3000` |
| `BACKEND_PORT` | Host port mapped to backend container | `5000` |
| `MCP_PORT` | Host port mapped to MCP SSE server on backend | `8001` |
| `MCP_AUTH_TOKEN` | Secret token for static MCP Bearer/API-key/Query auth | `<your-mcp-auth-token>` |
| `OAUTH_CLIENT_ID` | Pre-configured confidential OAuth client ID | `<client-id>` |
| `OAUTH_CLIENT_SECRET` | Pre-configured confidential OAuth client secret | `<client-secret>` |
| `OAUTH_CLIENT_REDIRECT_URIS` | Comma-separated redirect URI allowlist for DCR (fail-closed) | `https://...` |
| `OAUTH_CLIENT_AUTH_METHOD` | OAuth client authentication method (`client_secret_basic` or `client_secret_post`) | `client_secret_basic` |
| `OAUTH_CIMD_ALLOWED_HOSTS` | Comma-separated allowlist of hosts permitted to serve CIMD client documents | `accountlinking.google.com` |
| `OAUTH_ISSUER_URL` | Base issuer and RFC 8414 metadata URL for OAuth server | `https://era-server.tail3cb3be.ts.net:10000` |
| `OAUTH_HOST` | Listening host for the OAuth authorization server container | `0.0.0.0` |
| `OAUTH_PORT` | Listening port for the OAuth authorization server container | `10000` |
| `MCP_RESOURCE_URL` | Protected resource URL pointing to the remote MCP endpoint | `https://era-server.tail3cb3be.ts.net:8443/mcp` |

### 3. Automated Table Discovery & Schema Initialization (`Baserow_init`)

If any `BASEROW_TABLE_*` ID is omitted from your `.env` file, ERA ERP will **automatically query the Baserow API upon startup to discover the table IDs** and populate them into both root `.env` and `backend/.env`.

To manually trigger schema validation, table creation, and default data seeding:

* **PowerShell (Windows):**
  ```powershell
  .\scripts\Baserow-Init.ps1
  ```

* **Bash (Linux / WSL / macOS):**
  ```bash
  ./scripts/Baserow-Init.sh
  ```

#### Authentication & Diagnostic Fallback:
- The initialization engine connects using your `BASEROW_TOKEN` (API Token).
- If your Baserow database token does not possess schema-creation permissions to create missing tables/fields, `Baserow-Init` prints a **clear, structured diagnostic notice** detailing all required tables, field names, and types to configure in the Baserow UI.
- Alternatively, providing `BASEROW_ADMIN_EMAIL` and `BASEROW_ADMIN_PASSWORD` allows the script to automatically provision missing tables, link_row relationships, and default seed data (PN categories & lifecycle states).

---

## 🤖 Model Context Protocol (MCP) Server

ERA ERP includes a native **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** server implemented in [`backend/app/mcp_server.py`](backend/app/mcp_server.py) (~1,258 lines) and started by `backend/run.py`. Built directly on the low-level MCP Python SDK using the core `Server` class and `@server.tool()` decorators (not the FastMCP helper), it exposes **exactly 14 domain tools**, URI resources, and guided prompt workflows. The MCP server allows AI assistants (such as **Google Antigravity**, **Claude Desktop**, **Cursor**, or remote agents like **Google Gemini Spark**) to directly query and manipulate manufacturing data, BOM trees, work instructions, and quality diagnostics.

### 🚀 Launch Modes & Backend Integration

The MCP server is **enabled and started with the backend by default** over Server-Sent Events (SSE HTTP transport on `http://127.0.0.1:8001/sse`), or via `stdio` mode for CLI integration.

| Command | Description |
| :--- | :--- |
| `python backend/run.py` | **Default:** Starts Flask Backend (port `5000`) **AND** MCP SSE Server (port `8001`) concurrently in the background. |
| `python backend/run.py --NoMCP` | Runs the Flask backend **only** (disables background MCP server). |
| `python backend/run.py --mcp` | Dedicated **`stdio`** transport mode for direct CLI / desktop AI agent integration. |
| `python backend/run.py --mcp-sse` | Runs standalone MCP SSE server only on `http://127.0.0.1:8001/sse` (without Flask). |
| `python backend/run.py --mcp-port 8005` | Customizes the MCP SSE listening port (defaults to `8001` or `MCP_PORT` env var). |
| `python backend/run.py --mcp-token <secret>` | Sets the secret authentication token (defaults to `MCP_AUTH_TOKEN` env var). |
| `python backend/run.py --oauth-server --oauth-host 0.0.0.0 --oauth-port 10000` | Starts the standalone OAuth 2.1 authorization server (entrypoint for `era-oauth`). |

### 🔒 Authentication & Internet Exposure

When exposing the MCP server for external or remote AI access, ERA ERP provides **two distinct authentication paths**:

1. **Static Token Authentication (Simpler Clients & Local Dev):**
   Supported directly on `backend/app/mcp_server.py` using a shared secret configured via `MCP_AUTH_TOKEN`:
   * **Authorization Header:** `Authorization: Bearer <MCP_AUTH_TOKEN>`
   * **API Key Header:** `X-API-Key: <MCP_AUTH_TOKEN>`
   * **Query Parameter:** `https://your-domain.com/sse?token=<MCP_AUTH_TOKEN>` or `?api_key=<MCP_AUTH_TOKEN>`
   *(Note: If `MCP_AUTH_TOKEN` is left empty or unset, authentication is bypassed for convenient offline local development).*

2. **OAuth 2.1 with DCR & PKCE (Remote Clients / Gemini Spark):**
   Handled by the dedicated `era-oauth` authorization server container (`backend/app/oauth_server.py` on port 10000). The OAuth path is **required for clients that cannot attach custom headers to the event-stream handshake** (such as **Google Gemini Spark**) and for clients mandating standards-compliant discovery and token exchange. It implements RFC 8414 metadata discovery, RFC 9728 protected-resource metadata, Authorization Code flow with PKCE (S256), RFC 7591 Dynamic Client Registration gated on an approved `redirect_uri` allowlist (fail-closed), and Client ID Metadata Documents (CIMD) with an SSRF guard.

#### 🐳 Deploying with Dockge:
In **Dockge Web UI**:
1. Open your ERA ERP stack.
2. In the **`.env` pane** on the right, enter your production secrets:
   ```env
   MCP_AUTH_TOKEN=your_secure_mcp_auth_token_here
   MCP_PORT=8001
   OAUTH_ISSUER_URL=https://era-server.tail3cb3be.ts.net:10000
   MCP_RESOURCE_URL=https://era-server.tail3cb3be.ts.net:8443/mcp
   ```
3. Click **Save** and **Deploy**. Dockge automatically injects the configuration into the backend and oauth containers at runtime without committing secrets to Git.

### 🛠️ Capabilities & Tool Catalog

The MCP server exposes 14 specialized domain tools:

* **Item & Catalog Management:**
  * `search_items(query, category, lifecycle_state, limit)`: Search parts by keyword, prefix, or state.
  * `get_item_details(part_number_or_id)`: Retrieve full part specifications, pricing, vendor info, and metadata.
  * `create_item(part_number, name, category, ...)`: Register a new item in the catalog.
  * `update_item(part_number_or_id, ...)`: Edit lifecycle state, description, unit price, or notes.
* **BOM Trees & Assembly Graph:**
  * `get_bom_tree(part_number_or_id, max_depth)`: Explode multi-tier nested Bill of Materials.
  * `get_where_used(part_number_or_id)`: Identify all parent assemblies using a specific component.
* **BOM Equilibrium & Quality Diagnostics:**
  * `audit_bom_balance(part_number_or_id)`: Mathematically audit assembly child component requirements against step tolling usage to verify zero component leakage.
  * `run_quality_scan(part_number_or_id)`: Scan for missing datasheets, missing images, unassigned states, or broken links.
* **Work Instructions (WI) & Tolling:**
  * `get_work_instructions(part_number_or_id, set_index)`: Fetch step-by-step SOPs and tolling allocations.
  * `create_or_update_wi_step(assembly_pn_or_id, step_number, instruction_text, ...)`: Author or update instruction steps.
* **Inventory & Reference Data:**
  * `get_inventory_summary(part_number_or_id, target_build_qty)`: Calculate total parts demand and unit BOM cost for production runs.
  * `list_pn_categories()`: Return PN prefixes and classification rules.
  * `list_item_lifecycle_states()`: Return valid lifecycle states.
  * `list_manufacturers_and_suppliers()`: List contact directory.

### 📦 URI Resources & Guided Prompts

* **Resources:** Direct read endpoints for agents via `era://items/{pn}`, `era://bom/{pn}`, `era://wi/{pn}`, `era://inventory/{pn}`, `era://categories`, and `era://states`.
* **Prompt Templates:** Pre-configured engineering workflows:
  * `audit_bom_balance(part_number)`: Interactive audit for resolving component discrepancies.
  * `create_assembly_wi(part_number)`: Step-by-step SOP authoring guide.
  * `hardware_problem_scan(part_number)`: Quality remediation checklist generator.

### ⚙️ Client Configuration Examples

#### 1. Claude Desktop / Antigravity (Local stdio):
```json
{
  "mcpServers": {
    "era-erp": {
      "command": "python",
      "args": ["backend/run.py", "--mcp"]
    }
  }
}
```

#### 2. Remote AI Client via Static Token (Authenticated SSE):
* **SSE URL:** `http://127.0.0.1:8001/sse` (or reverse proxy endpoint)
* **Auth Type:** `Bearer Token` or `API Key`
* **Token:** `<MCP_AUTH_TOKEN>`
* *(Or direct fallback URL: `https://your-domain.com/sse?token=<MCP_AUTH_TOKEN>`)*

#### 3. Google Gemini Spark / Remote DCR Clients (OAuth 2.1):
* **Remote MCP Endpoint:** `https://era-server.tail3cb3be.ts.net:8443/mcp` (via Tailscale Funnel to local port `8001`)
* **OAuth 2.1 Issuer / Metadata Base:** `https://era-server.tail3cb3be.ts.net:10000`
* **Protected-Resource Metadata:** `https://era-server.tail3cb3be.ts.net:8443/.well-known/oauth-protected-resource/mcp`
* **Handshake Protocol:** RFC 8414 metadata discovery (`/.well-known/oauth-authorization-server`) + RFC 7591 Dynamic Client Registration (DCR) + Authorization Code Grant with PKCE (`S256`).

---

## 🔐 OAuth 2.1 Authorization Server (Remote MCP Clients)

ERA ERP includes a dedicated **OAuth 2.1 Authorization Server** container (`era-oauth`) providing standards-compliant discovery, registration, and authorization for remote Model Context Protocol (MCP) clients.

### 🎯 Purpose & Client Compatibility
Modern remote AI environments (such as **Google Gemini Spark**) cannot inject custom static headers during the Server-Sent Events (SSE) stream handshake and require standard OAuth 2.1 protocol flows for dynamic client registration and authorization code exchange. 

The authorization server satisfies these requirements without compromising security:
* **Google Gemini Spark & DCR Clients:** Full support via Dynamic Client Registration (RFC 7591) and Authorization Code Grant with PKCE.
* **Simpler Clients & Local CLI:** The static bearer token (`MCP_AUTH_TOKEN`) remains concurrently supported directly on the MCP server for simpler integrations.

### 📦 Source File & Entrypoint
* **Source File:** [`backend/app/oauth_server.py`](backend/app/oauth_server.py)
* **Runner Entrypoint:** Started via `backend/run.py`:
  ```bash
  python run.py --oauth-server --oauth-host 0.0.0.0 --oauth-port 10000
  ```
* **Container Execution:** Runs inside the `era-oauth` Docker container, which reuses the `era-backend` image with the dedicated OAuth entrypoint command above.

### 🌐 Endpoints & Standards Specification

The authorization server implements modern OAuth 2.1 and MCP security specifications:

| Standard / Role | Endpoint / URL | Description |
| :--- | :--- | :--- |
| **Issuer / Metadata Base** | `https://era-server.tail3cb3be.ts.net:10000` | Canonical issuer URL and OAuth metadata base |
| **RFC 8414 AS Metadata** | `/.well-known/oauth-authorization-server` | Authorization server capabilities, grant types, and endpoints |
| **RFC 7517 JWKS** | `/.well-known/jwks.json` | Public cryptographic JSON Web Key Set for token validation |
| **RFC 9728 Resource Metadata** | `https://era-server.tail3cb3be.ts.net:8443/.well-known/oauth-protected-resource/mcp` | Protected-resource metadata advertising the OAuth server and scopes for MCP |
| **Remote MCP Endpoint** | `https://era-server.tail3cb3be.ts.net:8443/mcp` | Remote MCP endpoint exposed via Tailscale Funnel to local port `8001` |
| **Authorization Endpoint** | `/authorize` | Interactive consent and authorization code issuance |
| **Token Endpoint** | `/token` | Code exchange for signed access and refresh tokens |
| **Dynamic Registration (DCR)** | `/register` | RFC 7591 dynamic client registration endpoint |

### 🛡️ Security Mechanisms
* **Authorization Code with PKCE (RFC 7636):** Mandates Proof Key for Code Exchange using the `S256` code challenge method on all authorization code flows.
* **Dynamic Client Registration Gated by Allowlist:** Dynamic Client Registration (RFC 7591) is strictly gated on an approved `redirect_uri` allowlist (`OAUTH_CLIENT_REDIRECT_URIS`). Any registration request presenting a redirect URI not explicitly listed in the allowlist is rejected immediately (**fail-closed**).
* **Client ID Metadata Documents (CIMD) with SSRF Guard:** Supports client identification via HTTPS Client ID Metadata Documents. CIMD hostnames are checked against `OAUTH_CIMD_ALLOWED_HOSTS` (defaults to `accountlinking.google.com`). All resolved IP addresses are verified through an SSRF guard that blocks loopback, private, link-local, multicast, and reserved IP ranges.

### 🚢 Three-Container Stack & Port Allocation

The ERA ERP production and local stack is partitioned into three containers:

| Container | Host : Container Port | Service / Transport | Role & Entrypoint |
| :--- | :--- | :--- | :--- |
| **`era-frontend`** | `3000:80` | Web UI (Nginx + Vite) | Manufacturing dashboard, BOM visualizer, and WI authoring interface |
| **`era-backend`** | `5000:5000`<br>`8001:8001` | Flask REST API<br>MCP Server (SSE) | Core business logic, Baserow data access, and low-level MCP SDK server (`backend/run.py`) |
| **`era-oauth`** | `10000:10000` | OAuth 2.1 Auth Server | RFC 8414 metadata, RFC 7591 DCR, CIMD, and PKCE (`backend/run.py --oauth-server`) |

---

## 🐳 Docker Packaging & Execution

The repository includes dedicated orchestration scripts for both **PowerShell** (Windows) and **Bash** (Linux/WSL/macOS).

### Quick Start with Docker Compose

Run containers with live builds:

```bash
docker compose up --build -d
```

### Using Provided Automation Scripts

#### 1. Pack / Build Docker Images
Builds container images (`era-backend:latest` and `era-frontend:latest`) without starting them (the `era-oauth` container uses the `era-backend` image with the dedicated `--oauth-server` entrypoint). You can optionally export them as `.tar` archives for distribution.

* **PowerShell (Windows):**
  ```powershell
  # Standard build
  .\scripts\Pack-Docker.ps1

  # Custom tag and export tar archives to ./dist-docker
  .\scripts\Pack-Docker.ps1 -Tag "v1.0.0" -ExportTar
  ```

* **Bash (Linux / WSL / macOS):**
  ```bash
  # Standard build
  ./scripts/Pack-Docker.sh

  # Custom tag and export tar archives
  ./scripts/Pack-Docker.sh v1.0.0 --export-tar
  ```

#### 2. Run / Stop Docker Containers
Launches the full multi-container stack via Docker Compose, validating `.env` configuration automatically.

* **PowerShell (Windows):**
  ```powershell
  # Start containers in background
  .\scripts\Run-Docker.ps1

  # Stop containers
  .\scripts\Run-Docker.ps1 -Down
  ```

* **Bash (Linux / WSL / macOS):**
  ```bash
  # Start containers
  ./scripts/Run-Docker.sh

  # Stop containers
  ./scripts/Run-Docker.sh down
  ```

Once running:
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:5000](http://localhost:5000)
- **MCP Server (SSE):** [http://localhost:8001/sse](http://localhost:8001/sse)
- **OAuth 2.1 Authorization Server:** [http://localhost:10000](http://localhost:10000)

---

## 💻 Local Development & Testing

If developing natively without Docker:

### 1. Run Development Servers
* **PowerShell:**
  ```powershell
  .\scripts\Run-Dev.ps1
  ```
  *Starts Python Flask backend (port 5000) with MCP Server (port 8001) and Vite development server (port 3000) concurrently. To launch the backend without MCP, run `python backend/run.py --NoMCP`. To start the standalone OAuth 2.1 server, run `python backend/run.py --oauth-server --oauth-port 10000`.*

### 2. Run Test Suite
* **PowerShell:**
  ```powershell
  .\scripts\Run-Tests.ps1
  ```
  *Runs full backend unit & integration tests (`pytest` with coverage report) and frontend test suites (`vitest`).*

---

## 📁 Project Structure

```
.
├── .env.example               # Template for environment variables and Baserow config
├── docker-compose.yml         # Three-container Docker Compose definition (frontend, backend, oauth)
├── backend/
│   ├── Dockerfile             # Python Flask & OAuth server container image
│   ├── requirements.txt       # Python dependencies
│   ├── run.py                 # Multi-service entrypoint (Flask API, MCP SSE/stdio, OAuth server)
│   ├── app/                   # Backend application logic & Baserow API client
│   │   ├── mcp_server.py      # Low-level MCP SDK server (14 domain tools, resources, prompts)
│   │   ├── oauth_server.py    # OAuth 2.1 authorization server (RFC 8414, RFC 7591 DCR, CIMD)
│   │   ├── baserow_client.py  # Baserow database client & schema manager
│   │   ├── main.py            # Flask API app factory (all REST routes)
│   │   ├── wi_export.py       # Work Instruction .docx export (inline image embedding)
│   │   ├── inventory_report.py# Build-quantity inventory requirement report
│   │   ├── backup_manager.py  # Baserow data backup/snapshot helper
│   │   └── baserow_init.py    # Table discovery & schema initialization
│   └── tests/                 # Backend pytest test suite
├── frontend/
│   ├── Dockerfile             # Multi-stage Vite build + Nginx production image
│   ├── package.json           # Frontend dependencies & scripts
│   ├── src/                   # Single-page UI modules & API client
│   └── tests/                 # Frontend vitest suite
├── scripts/
│   ├── Pack-Docker.ps1 / .sh  # Image packaging and archiving scripts
│   ├── Run-Docker.ps1 / .sh   # Docker deployment orchestration scripts
│   ├── Run-Dev.ps1            # Local native development runner
│   └── Run-Tests.ps1          # Comprehensive test runner
└── README.md                  # Project documentation and setup guide
```
