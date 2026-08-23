# ERA ERP / BaseRow Manager

> **A specialized, agile Manufacturing ERP and Bill of Materials (BOM) management platform built on top of Baserow.**

---

## 📖 Table of Contents

- [Why ERA ERP? (The Inception Story)](#-why-era-erp-the-inception-story)
- [Key Features & Capabilities](#-key-features--capabilities)
- [System Architecture](#-system-architecture)
- [Setup & Environment Configuration](#-setup--environment-configuration)
- [Docker Packaging & Execution](#-docker-packaging--execution)
- [Local Development & Testing](#-local-development--testing)
- [Project Structure](#-project-structure)

---

## 💡 Why ERA ERP? (The Inception Story)

Traditional enterprise ERP solutions—most notably **ERPNext**—are notoriously heavy, complex, and rigid. While ERPNext offers extensive monolithic features, its learning curve is exceptionally steep and customizing it for specialized hardware manufacturing and assembly workflows is cumbersome, fragile, and slow.

**ERA ERP** was incepted to solve this exact problem:
* **Zero Bloat & Maximum Customization:** Instead of struggling against rigid DocTypes and heavyweight monolithic frameworks, ERA ERP uses **[Baserow](https://baserow.io/)** as a flexible, transparent, single source of truth for relational data.
* **Purpose-Built for Manufacturing:** Tailored specifically for electronics and mechanical hardware assembly, multi-level BOM trees, dynamic Work Instructions (WIs), component lifecycle states, and supply chain tracking.
* **Agile Orchestration Layer:** Python backend and modern web frontend act as an intelligent orchestration layer on top of Baserow's API, giving engineering and manufacturing teams instant agility without losing data integrity.

---

## ✨ Key Features & Capabilities

- **Interactive Multi-Level BOM Tree:** Algorithmically converts flat relational tables into nested, interactive, multi-tiered BOM hierarchies with parent/child quantity cascading.
- **Dynamic Work Instruction (WI) & SOP Builder:** Compose step-by-step assembly instructions, annotate component tolling quantities, attach step photos, and export branded DOCX work instructions directly from customizable templates.
- **BOM Equilibrium & Problem Scanner:** Automated rule engine verifying that all assembly components are accounted for in assembly instructions (BOM equilibrium balance) and highlighting missing metadata, photos, or datasheets.
- **Part Number (PN) Categorization & Lifecycle Management:** Smart prefix-based categorizations (e.g., Raw Materials, COTS, Custom Mechanical, Electrical) and lifecycle states (*Production Use*, *Engineering Use*, *EOL*, *Discard*).
- **Manufacturer & Supplier Directory:** Comprehensive contact, supplier, and manufacturer tracking with live part associations.

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
| `BASEROW_TOKEN` | Database API Token generated in Baserow | `C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L` |
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
  *Starts Python Flask backend (port 5000) and Vite development server (port 3000) concurrently.*

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
