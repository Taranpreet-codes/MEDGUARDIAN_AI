# 🛡️ MedGuardian AI — Proactive Medication Digital Twin

[![Django](https://img.shields.io/badge/Backend-Django%204.2%20%7C%20DRF-092E20?logo=django)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20Vite%20%7C%20TS-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Styling-Tailwind%20CSS-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Celery](https://img.shields.io/badge/Queue-Celery%20%2B%20Redis-37814A?logo=celery)](https://docs.celeryq.dev/)
[![ChromaDB](https://img.shields.io/badge/Vector%20Store-ChromaDB-FF6F00)](https://www.trychroma.com/)
[![Google Gemini](https://img.shields.io/badge/AI%20Vision%20%26%20RAG-Gemini%202.5%20%2F%202.0-4285F4?logo=google)](https://ai.google.dev/)

**MedGuardian AI** is a clinical decision support (CDS) platform engineered as a proactive **Medication Digital Twin**. It continuously audits patient health profiles, active drug cabinets, and renal biomarkers against clinical guidelines, structured interaction databases, and FDA package inserts.

The platform combines **multimodal AI vision** for prescription ingestion, a **pluggable clinical data provider architecture** for deterministic drug safety audits, **local vector retrieval (ChromaDB)** for evidence-grounded clinical rationale, and an **asynchronous event-driven Celery pipeline** that streams proactive safety alerts to the browser in real time.

---

## 📐 System Architecture

MedGuardian AI implements a decoupled, resilient architecture separating presentation, clinical orchestration, background auditing, and external clinical intelligence:

```mermaid
graph TD
    subgraph Client ["Frontend Client (React 18 + Vite + TypeScript + Tailwind CSS)"]
        UI["Clinical Portal (Dashboard, Cabinet, Chat, History, Reports)"]
        SSE["Live Alert Stream Listener (EventSource SSE / Polling Fallback)"]
        AUTH["JWT Session & Demo Profile Switcher"]
    end
    
    subgraph Backend ["Backend Service (Django REST Framework)"]
        API["REST Endpoints & Model ViewSets"]
        OCR["Prescription Ingestion Engine (Gemini 2.5 Flash Vision)"]
        CDS["ClinicalDataService (Central Orchestration)"]
        REPORTS["PDF Report Generation Engine (ReportLab)"]
    end

    subgraph Providers ["Pluggable Clinical Provider Layer"]
        P_NORM["RxNavNormalizerProvider (NLM RxNorm Active APIs)"]
        P_COMP["CompositeInteractionProvider (Multi-Tier Interaction Engine)"]
        P_DDI["CuratedDDIProvider (Validated DDInter 2.0 / ONCHigh Dataset)"]
        P_FDA["OpenFDALabelProvider (Live FDA SPL Warnings & Precautions)"]
        P_CHROMA["ChromaGuidelineProvider (ChromaDB + Gemini Embeddings)"]
        P_FALLBACK["FallbackClinicalProvider (Offline Circuit Breaker)"]
    end

    subgraph Worker ["Asynchronous Task Pipeline"]
        SIG["Django Post-Save Signals (Profile / Cabinet Changes)"]
        QUEUE["Celery Task Queue (Worker / Redis Broker)"]
        LOCK["Atomic Redis Debounce Lock (10s Window)"]
    end

    subgraph Storage ["Persistent Stores"]
        VEC[("ChromaDB (Guideline Vector Embeddings)")]
        SQL[("PostgreSQL / SQLite3 (Patients, Cabinets, Alerts, Logs)")]
    end

    subgraph External ["External Intelligence & Clinical APIs"]
        GEMINI["Google Gemini API (2.5 Flash, 2.0 Flash, gemini-embedding-001)"]
        RXNAV["NLM RxNav Active APIs (/approximateTerm, /rxcui)"]
        OPENFDA["openFDA Drug Label API (Structured Product Labeling)"]
    end

    %% Client Interactions
    UI -->|"Prescription Upload / Vitals Update / Chat Queries"| API
    AUTH -->|"JWT Token Authentication"| API
    API -->|"Streams Unread Alerts via SSE"| SSE

    %% Ingestion Flow
    API -->|"Extracts handwriting & medications"| OCR
    OCR -->|"Multimodal Vision Schema"| GEMINI

    %% Asynchronous Pipeline
    API -->|"Triggers on Model Save"| SIG
    SIG -->|"Enqueues Background Audit"| QUEUE
    QUEUE -->|"Acquires 10s Debounce Lock"| LOCK
    QUEUE -->|"Executes Async Audit"| CDS

    %% Clinical Provider Layer Orchestration
    CDS --> P_NORM
    P_NORM -->|"Resolves Brand to Generic & RxCUI"| RXNAV
    CDS --> P_COMP
    P_COMP --> P_DDI
    P_COMP --> P_FDA
    P_FDA -->|"Fetches Boxed Warnings & Contraindications"| OPENFDA
    CDS --> P_CHROMA
    P_CHROMA -->|"768-dim Query Embedding"| GEMINI
    P_CHROMA -->|"Retrieves Guideline Passages"| VEC
    CDS -.->|"Network Failure Circuit Breaker"| P_FALLBACK

    %% Persistence & Alerts
    CDS -->|"Persists Assessment & Publishes ProactiveAlert"| SQL
    SQL -->|"Delivers SSE data frames"| SSE

    %% Reports & Export
    API -->|"Renders Patient & Clinician Dossiers"| REPORTS
    REPORTS -->|"Generates Downloadable PDF"| UI
```

---

## 🌟 Core Features

### 1. 📸 Multimodal Prescription Ingestion (OCR & Medical NER)
*   **Camera & File Uploads**: Upload smartphone photos, scanned documents, or digital prescription files (PNG, JPG, WEBP).
*   **Structured Medical NER**: Uses Google Gemini 2.5 Flash multimodal vision bound to a strict Pydantic schema (`ExtractionResult`) to parse drug names, dosages, strengths, and administration frequencies.
*   **Interactive Medication Staging**: Parsed medications are presented in a confirmation modal where patients or clinicians can verify, edit, or select items before importing them into the active cabinet.
*   **Offline / No-Key Fallback**: In development or offline mode, automatically provides a realistic mock prescription parser so workflows remain testable without an active API key.

### 2. 🧩 Pluggable Clinical Provider Architecture
MedGuardian AI routes all clinical safety logic through a modular provider interface (`backend/services/providers/`), insulating the system from upstream API changes and ensuring 100% testable uptime:

*   **NLM RxNav Drug Normalization (`RxNavNormalizerProvider`)**:
    *   Integrates active NLM RxNorm REST APIs (`/REST/approximateTerm.json` and `/REST/rxcui.json`).
    *   Resolves trade names (e.g., *Glucophage*, *Prinivil*, *Lipitor*) into canonical generic names (*metformin*, *lisinopril*, *atorvastatin*) and standard RxCUIs.
    *   Features an internal pre-warmed dictionary and memory cache for zero-latency local resolution.
    *   *(Note: The legacy NLM RxNav Drug-Drug Interaction API was retired on Jan 2, 2024; MedGuardian AI deliberately routes all interaction audits through dedicated interaction providers).*
*   **Tiered Interaction Screening (`CompositeInteractionProvider`)**:
    *   **Tier 1 (`CuratedDDIProvider`)**: Validated, deterministic clinical interaction dataset (`curated_ddi_database.json`) derived from DDInter 2.0, ONCHigh, and FDA package inserts. Provides standardized severity tiers (`Contraindicated`, `Severe`, `Moderate`, `Minor`), pharmacological mechanisms, and recommended clinical management actions.
    *   **Tier 2 (`OpenFDALabelProvider`)**: Queries live FDA Structured Product Labeling (SPL) package inserts for official boxed warnings, contraindications, precautions, and adverse reactions.
*   **Offline Circuit Breaker (`FallbackClinicalProvider`)**:
    *   Guarantees continuous operation during external network failures, rate-limiting (HTTP 429), or missing API credentials.

### 3. 🧠 Grounded Evidence RAG & Clinical Assistant
*   **ChromaDB Vector Store (`ChromaGuidelineProvider`)**:
    *   Chunks and indexes clinical guidelines (KDIGO renal guidelines, ADA diabetes standards, WHO hypertension protocols, FDA package inserts).
    *   Generates 768-dimensional embeddings using `gemini-embedding-001`.
    *   Features a localized BM25 / keyword fallback for semantic matching in offline environments.
*   **Evidence Traceability**:
    *   Every retrieved evidence chunk returns its source document name, page number, quoted excerpt, and normalized relevance score ($0.00$ to $1.00$).
*   **Clinical Chat Assistant**:
    *   Interactive conversational assistant powered by `gemini-2.0-flash`.
    *   Strict anti-hallucination prompting: answers are grounded strictly in the retrieved guideline context and patient profile. If guidelines are insufficient, the model safely demurs.

### 4. ⚡ Proactive Digital Twin & Asynchronous Alerts
*   **Event-Driven Synchronization**:
    *   Django `post_save` and `post_delete` signals monitor modifications to patient biomarkers (`PatientProfile`: eGFR, serum creatinine, pregnancy, allergies) and medications (`MedicationCabinet`: additions, edits, deactivations).
*   **Debounced Celery Queue**:
    *   Background tasks execute out-of-process using a 10-second atomic Redis cache lock. Rapid consecutive updates (e.g., updating multiple medications) collapse into a single unified analysis.
    *   Runs in full asynchronous mode with Redis, or gracefully falls back to synchronous inline execution (`CELERY_TASK_ALWAYS_EAGER=True`) if Redis is unavailable.
*   **Risk Escalation Detection**:
    *   Compares the new risk evaluation against historical runs (`Safe` $\rightarrow$ `Low` $\rightarrow$ `Moderate` $\rightarrow$ `Severe`).
    *   Automatically publishes a `ProactiveAlert` when patient risk deteriorates.
*   **Real-Time Server-Sent Events (SSE)**:
    *   HTTP `text/event-stream` endpoint (`/api/alerts/stream/`) pushes unacknowledged alerts to the frontend client instantaneously with a client-side polling fallback.

### 5. 📊 Longitudinal Risk Timeline & Analytics
*   **Recharts Safety Graphing**:
    *   Interactive longitudinal area chart visualizing patient risk level progression across historical safety assessments.
    *   Tracks renal clearance trends (eGFR and Creatinine) alongside medication adjustments to identify adverse drug events before they escalate.

### 6. 📄 Dual-Audience Dynamic PDF Reports
Rendered on-the-fly using ReportLab with custom typography and safety color palettes:
*   **Patient Safety Summary**: Plain-language report detailing active medications, dosing schedules, cautionary advice, and allergy notices.
*   **Clinician Safety Dossier**: High-density clinical dossier detailing renal impairment staging (KDIGO), drug-drug interaction mechanisms, FDA boxed warnings, and verified clinical citations.

---

## 🛠️ Technology Stack

| Layer | Technologies | Purpose |
|---|---|---|
| **Backend Framework** | Python 3.10+, Django 4.2.x, Django REST Framework | Core REST APIs, ORM, ModelViewSets, and signal architecture |
| **Authentication** | `djangorestframework-simplejwt` | Stateless JWT authentication with query-param support for SSE streams |
| **Generative AI & Vision** | `google-genai` SDK, `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-embedding-001` | Multimodal prescription OCR, clinical RAG embedding, grounded CDS chat |
| **Vector Database** | ChromaDB (PersistentClient) | Local vector storage and semantic retrieval for clinical guidelines |
| **Task Queue & Broker** | Celery 5.3+, Redis | Background safety audits, atomic debouncing, and fault-tolerant retries |
| **Clinical APIs & Data** | NLM RxNav, openFDA Drug Label API, DDInter 2.0 Curated Dataset | Drug normalization, RxCUI mapping, label warnings, structured DDI |
| **Report Generation** | ReportLab, pypdf | PDF document rendering and guideline parsing |
| **Frontend Framework** | React 18, Vite, TypeScript | Type-safe Single-Page Application (SPA) |
| **Styling & Icons** | Tailwind CSS, Lucide React | Glassmorphic clinical UI with dark and light mode themes |
| **Data Visualization** | Recharts | Longitudinal risk timeline and renal function tracking charts |

---

## 📁 Repository Structure

```
MedGuardian_AI/
├── backend/                               # Django Backend Service
│   ├── manage.py                          # Django CLI entrypoint
│   ├── medguardian/                       # Project configuration & settings
│   │   ├── settings.py                    # App settings, Celery, JWT, & CORS
│   │   ├── urls.py                        # Root URL routing & health check
│   │   ├── wsgi.py / asgi.py              # Server gateway interfaces
│   │   └── test_providers.py              # Unit tests for clinical provider architecture
│   ├── accounts/                          # User registration & profile bootstrap
│   ├── patients/                          # Patient profile, cabinet, alerts & tasks
│   │   ├── models.py                      # PatientProfile, MedicationCabinet, ProactiveAlert
│   │   ├── views.py                       # ViewSets (Profile, Cabinet, Alerts, SSE stream)
│   │   ├── tasks.py                       # Asynchronous Celery safety audit task
│   │   ├── signals.py                     # Django post-save safety re-evaluation hooks
│   │   └── serializers.py                 # DRF serializers
│   ├── prescriptions/                     # Prescription upload & confirm workflow
│   ├── evidence/                          # Management commands for guideline indexing
│   │   └── management/commands/
│   │       └── ingest_evidence.py         # Parses & embeds PDFs/TXTs into ChromaDB
│   ├── services/                          # Core Clinical & Generative Services
│   │   ├── clinical_service.py            # Central clinical orchestration service
│   │   ├── risk_engine.py                 # Backwards-compatible RiskEngine adapter
│   │   ├── ingestion.py                   # Multimodal Gemini vision OCR & NER
│   │   ├── rag.py                         # ChromaDB retriever & openFDA label client
│   │   ├── reports.py                     # ReportLab PDF report generators
│   │   └── providers/                     # Pluggable clinical data provider layer
│   │       ├── base.py                    # Abstract base provider classes
│   │       ├── models.py                  # Standardized clinical data transfer models
│   │       ├── rxnav_normalizer.py        # Active NLM RxNorm normalizer & RxCUI resolver
│   │       ├── curated_ddi_provider.py    # Curated clinical DDI dataset provider
│   │       ├── openfda_provider.py        # Official openFDA drug label warning provider
│   │       ├── composite_interaction_provider.py # Multi-tier composite DDI evaluator
│   │       ├── chroma_provider.py         # ChromaDB guideline evidence provider
│   │       └── fallback_provider.py       # Resilient offline circuit breaker
│   └── data/                              # Clinical guidelines, benchmarks & datasets
│       ├── curated_ddi_database.json      # Structured interaction reference database
│       ├── who_guidelines.txt             # WHO hypertension guideline excerpts
│       └── who_patient_safety_factsheet.txt
├── frontend/                              # React + Vite + TypeScript Frontend
│   ├── src/
│   │   ├── App.tsx                        # Master clinical dashboard SPA (5 main tabs)
│   │   ├── AuthView.tsx                   # Auth forms & demo patient quick-switcher
│   │   ├── api.ts                         # Typed API client, SSE stream, & download helpers
│   │   ├── types.ts                       # TypeScript interfaces for models and alerts
│   │   ├── index.css                      # Tailwind styling, dark/light themes, scrollbars
│   │   └── main.tsx                       # React application root
│   ├── package.json                       # Frontend dependencies & scripts
│   ├── tailwind.config.js                 # Tailwind CSS configuration
│   └── vite.config.ts                     # Vite build configuration & proxy settings
├── docker-compose.yml                     # Multi-container orchestration (DB, Web, Worker, Redis)
├── requirements.txt                       # Backend Python dependencies
└── start-dev.ps1                          # Automated Windows local dev startup script
```

---

## 🚀 Getting Started

### Prerequisites
*   **Python**: Version 3.10, 3.11, or 3.12.
*   **Node.js**: Version 18+ (with `npm`).
*   **Redis** *(Optional for local dev)*: Required for asynchronous background Celery tasks. If absent, the backend automatically runs in synchronous eager mode.

---

### 1. Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Configure your environment variables:

```ini
# Django Configuration
DEBUG=True
SECRET_KEY=your-secure-dev-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (falls back to local SQLite3 if DATABASE_URL is not set)
DATABASE_URL=postgres://postgres:postgres@localhost:5432/medguardian

# Generative AI Credentials (runs in offline/mock mode if left empty)
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere

# Optional openFDA Key (standard openFDA endpoints allow 240 req/min without a key)
OPENFDA_API_KEY=your_openfda_key_here

# ChromaDB Storage Location
CHROMA_DB_PATH=./chroma_db
```

---

### 2. Backend Setup & Evidence Ingestion

#### A. Create & Activate Virtual Environment

Create an isolated Python virtual environment (`.venv`) in the project root directory:

**1. Create the virtual environment:**
```bash
# Windows / macOS / Linux
python -m venv .venv
```
*(On systems with multiple Python installations or Linux/macOS, use `python3 -m venv .venv`)*

**2. Activate the virtual environment:**

*   **Windows (PowerShell):**
    ```powershell
    .\.venv\Scripts\Activate.ps1
    ```
    > **Note:** If PowerShell restricts script execution (`PSSecurityException`), run this command for the current process and re-activate:
    > ```powershell
    > Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
    > .\.venv\Scripts\Activate.ps1
    > ```

*   **Windows (Command Prompt / CMD):**
    ```cmd
    .\.venv\Scripts\activate.bat
    ```

*   **Linux / macOS (bash / zsh):**
    ```bash
    source .venv/bin/activate
    ```

**3. Upgrade `pip` (Recommended):**
```bash
python -m pip install --upgrade pip
```

---

#### B. Install Dependencies & Ingest Clinical Evidence

With the virtual environment active (`(.venv)` visible in your prompt):

```bash
# 1. Install backend requirements
pip install -r requirements.txt

# 2. Enter backend directory and apply database migrations
cd backend
python manage.py migrate

# 3. Seed authoritative clinical evidence into ChromaDB
python manage.py ingest_evidence
```

---

### 3. Running the Application

#### Method A: Automated PowerShell Startup (Windows — Recommended)
Run the bundled PowerShell orchestrator from the project root:

```powershell
./start-dev.ps1
```

This script automatically:
1. Detects or starts local Redis (checks `PATH`, standard Program Files locations, and bundled binaries).
2. Sets Celery mode (`async` if Redis is active, or `eager` inline mode if Redis is missing).
3. Launches the Django REST API on `http://localhost:8000`.
4. Launches the Celery worker (if Redis is running).
5. Starts the Vite frontend on `http://localhost:5173`.

#### Method B: Manual Execution (Separate Terminals)

**Terminal 1 — Redis Server** *(Optional)*:
```bash
redis-server
```

**Terminal 2 — Django REST Backend**:
```bash
# Activate .venv (.venv\Scripts\Activate.ps1 or source .venv/bin/activate)
cd backend
python manage.py runserver 0.0.0.0:8000
```

**Terminal 3 — Celery Worker** *(If Redis is available)*:
```bash
# Activate .venv (.venv\Scripts\Activate.ps1 or source .venv/bin/activate)
cd backend
# Windows:
celery -A medguardian worker --loglevel=info -P solo
# Linux/macOS:
celery -A medguardian worker --loglevel=info
```

**Terminal 4 — React Frontend**:
```bash
cd frontend
npm install
npm run dev
```

The web application will be accessible at `http://localhost:5173`.

#### Method C: Containerized Execution (Docker Compose)

Run the full stack (PostgreSQL, Redis, Django, Celery, and Vite) via Docker:

```bash
docker-compose up --build
```

---

## 🧪 Testing & Verification

MedGuardian AI includes automated test coverage for the provider architecture, clinical risk engine, prescription ingestion, and event-driven signals:

```bash
cd backend
python manage.py test
```

To run provider architecture tests specifically:
```bash
python manage.py test medguardian.test_providers
```

---

## 📡 API Endpoint Reference

### Health & Status
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/` | Service health status, API version, and clinical disclaimer |

### Authentication (`/api/auth/`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register/` | Register a new user and automatically initialize a blank patient profile |
| `POST` | `/api/auth/token/` | Authenticate and obtain JWT access & refresh tokens |
| `POST` | `/api/auth/token/refresh/` | Refresh expired access token |

### Patient Profile & Clinical Digital Twin (`/api/patients/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/patients/profile/me/` | Retrieve current patient's clinical profile (age, gender, eGFR, creatinine, allergies, conditions) |
| `PUT / PATCH` | `/api/patients/profile/me/` | Update profile biomarkers. *Automatically enqueues asynchronous Celery safety re-evaluation* |
| `GET` | `/api/patients/profile/safety-check/` | Trigger an immediate, synchronous clinical safety evaluation |
| `POST` | `/api/patients/profile/chat-ask/` | Ask clinical assistant a question grounded in ChromaDB guidelines and patient context |
| `GET` | `/api/patients/profile/report-patient/` | Download plain-language Patient Safety Summary PDF |
| `GET` | `/api/patients/profile/report-clinician/` | Download high-density Clinician Safety Dossier PDF |
| `GET` | `/api/patients/me/safety-history/` | Fetch historical safety evaluations for risk timeline charting |

### Medication Cabinet (`/api/patients/cabinet/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/patients/cabinet/` | List all medications in the patient's active cabinet |
| `POST` | `/api/patients/cabinet/` | Add a medication (name, dosage, frequency). *Triggers background safety audit* |
| `GET` | `/api/patients/cabinet/{id}/` | Retrieve details for a specific cabinet medication |
| `PUT / PATCH` | `/api/patients/cabinet/{id}/` | Modify dosage, frequency, or active status. *Triggers background safety audit* |
| `DELETE` | `/api/patients/cabinet/{id}/` | Remove medication from cabinet. *Triggers background safety audit* |

### Prescriptions & Vision Ingestion (`/api/prescriptions/`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/prescriptions/upload/` | Upload prescription image. Runs Gemini 2.5 Flash OCR + NER. Returns parsed drug entities |
| `POST` | `/api/prescriptions/{id}/confirm/` | Confirm parsed medications and transfer them to cabinet. *Triggers background safety audit* |

### Proactive Safety Alerts (`/api/alerts/`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/alerts/unread/` | Retrieve all active, unacknowledged safety alerts for current patient |
| `POST` | `/api/alerts/{id}/acknowledge/` | Acknowledge and dismiss a proactive safety alert |
| `GET` | `/api/alerts/stream/` | Server-Sent Events (SSE) push stream. Pushes live alerts as `data: {"alerts": [...], "count": N}` |

---

## 🛡️ Clinical Safety Notice & Disclaimer

> [!WARNING]
> **Educational & Decision Support Disclaimer**
> 
> MedGuardian AI is designed solely as an educational and clinical decision support tool. It is **NOT** an FDA-cleared diagnostic device, does **NOT** provide definitive medical diagnosis or treatment plans, and must **NEVER** replace professional evaluation by a licensed physician or pharmacist.
> 
> Patients should never initiate, discontinue, or alter drug dosages based on software outputs without direct physician supervision.
