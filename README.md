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

ERA ERP utilizes a **Two-Container Architecture** designed to run alongside an existing local Baserow instance (e.g., managed via Dockge/WSL or standalone Docker):

```
┌─────────────────────────────────────────────────────────────┐
│                       Browser / Client                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
       HTTP Port 3000                  HTTP Port 5000
               ▼                               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │  Frontend Container  │        │   Backend Container  │
    │    (Nginx + Vite)    │        │  (Python Flask API)  │
    └──────────────────────┘        └──────────┬───────────┘
                                               │
                                       REST API Token Auth
                                               ▼
                                    ┌──────────────────────┐
                                    │   Baserow Instance   │
                                    │    (Database API)    │
                                    └──────────────────────┘
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

ERA ERP includes a native **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** server implemented with the Python FastMCP SDK. The MCP server allows AI coding and engineering assistants (such as **Google Antigravity**, **Claude Desktop**, **Cursor**, or custom LLM sidecars) to directly query and manipulate manufacturing data, BOM trees, work instructions, and quality diagnostics.

### 🚀 Launch Modes & Backend Integration

The MCP server is **enabled and started with the backend by default** over Server-Sent Events (SSE HTTP transport on `http://127.0.0.1:8001/sse`).

| Command | Description |
| :--- | :--- |
| `python backend/run.py` | **Default:** Starts Flask Backend (port `5000`) **AND** MCP SSE Server (port `8001`) concurrently in the background. |
| `python backend/run.py --NoMCP` | Runs the Flask backend **only** (disables background MCP server). |
| `python backend/run.py --mcp` | Dedicated **`stdio`** transport mode for direct CLI / desktop AI agent integration. |
| `python backend/run.py --mcp-sse` | Runs standalone MCP SSE server only on `http://127.0.0.1:8001/sse` (without Flask). |
| `python backend/run.py --mcp-port 8005` | Customizes the MCP SSE listening port (defaults to `8001` or `MCP_PORT` env var). |

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

### ⚙️ Claude Desktop / AI Agent Configuration Example

Add the following to your `claude_desktop_config.json` or Antigravity MCP settings:

```json
{
  "mcpServers": {
    "era-erp": {
      "command": "python",
      "args": ["C:/Users/SlavaThereshin/Personal Projects/ERA_BaseRow_Manager/backend/run.py", "--mcp"]
    }
  }
}
```

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
Builds container images (`era-backend:latest` and `era-frontend:latest`) without starting them. You can optionally export them as `.tar` archives for distribution.

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

---

## 💻 Local Development & Testing

If developing natively without Docker:

### 1. Run Development Servers
* **PowerShell:**
  ```powershell
  .\scripts\Run-Dev.ps1
  ```
  *Starts Python Flask backend (port 5000) with MCP Server (port 8001) and Vite development server (port 3000) concurrently. To launch the backend without MCP, run `python backend/run.py --NoMCP`.*

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
├── docker-compose.yml         # Multi-container Docker Compose definition
├── backend/
│   ├── Dockerfile             # Python Flask backend container image
│   ├── requirements.txt       # Python dependencies
│   ├── app/                   # Backend application logic & Baserow API client
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
