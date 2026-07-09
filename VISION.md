# Vision & System Architecture: Manufacturing ERP & BOM Tool

## 1. Core Objective (The "Why")
The ultimate goal of this project is to build an internal, production-grade manufacturing ERP and Assembly Management Web Application. It serves as an intelligent layer on top of our existing Baserow database, transforming a flat Bill of Materials (BOM) into structured, highly actionable assembly data. 

The system will orchestrate manufacturing logistics, generate dynamic Standard Operating Procedures (SOPs), automate component data ingestion, and manage local inventory lifecycles.

---

## 2. Target Architecture & Scope

### Container Strategy & Deployment
* **Infrastructure:** The application will run entirely containerized alongside our existing local `Baserow` instance managed by Dockge in WSL (Ubuntu). 
* **Multi-Container vs. Single-Container:** We use a **Two-Container Approach** (plus the existing Baserow container) to keep concerns separated:
    1.  **Backend Container:** A lightweight, high-performance API (e.g., Python FastAPI) communicating directly with Baserow's API, parsing files, and running scraping/data-enrichment routines.
    2.  **Frontend Container:** A clean, responsive single-page web dashboard serving the user interface.
* **Networking & Gateway:** The existing `Nginx` container serves as our reverse proxy. Both the backend and frontend containers must route through it to provide a unified local address/port interface, avoiding cross-origin (CORS) friction and messy port mappings.
* **Deployment Pipeline:** While development occurs natively on Windows 11 targeting the WSL backend, deployment must be fully automated. The workflow should target automated image building via local docker registries, direct WSL image loads, or private Docker Hub pushes optimized for fast updates in Dockge.

---

## 3. High-Level Feature Roadmap (The Functional Milestones)

The agent should prioritize development patterns that support these core pillars:

### Phase 1: BOM Hierarchy Parsing & Enrichment
* **Hierarchical BOM Constructor:** Ingest flat relational tables from Baserow and algorithmically construct an interactive, nested, multi-tiered BOM tree structure.
* **Octopart Integration:** Implement a web-scraping or API-ingestion processor to look up component pages automatically, pulling down real-time datasheets, lead times, packaging data, and specifications to enrich flat Baserow rows.

### Phase 2: Assembly Choreography & SOP Generation
* **Prerequisite Dependency Graph:** Provide an interface to explicitly define strict physical assembly prerequisites (e.g., Part $A$ must be populated/soldered/fastened onto Subassembly $X$ *before* Part $B$ can be attached).
* **Dynamic SOP Engine:** Generate human-readable Standard Operating Procedures (SOPs) organized logically by subassembly tiers based on the dependency graph.

### Phase 3: Inventory Control & Supply Chain Automation
* **Stock Tracking & Thresholds:** Track physical component counts against minimum safety stock metrics calculated directly from top-level assembly demands.
* **Automated Procurement:** Generate formatted purchase request emails ready to send to logistics when stock drops below threshold milestones.

---

## 4. What This Project Is NOT (System Boundaries)
* We are **NOT** migrating away from Baserow. Baserow remains the single source of truth for raw data; our backend is an orchestration and translation layer.
* We are **NOT** designing a multi-tenant cloud application. This tool is built specifically for a highly localized, high-trust single-deployment environment.
* We are **NOT** adding heavy database layers on our backend container unless absolutely necessary for ephemeral session caching. Data integrity lives in the Baserow container.