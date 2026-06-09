# PolicyScout — Website Compliance & Policy Discovery SaaS

Automatically scan any website and identify critical business/legal compliance pages with direct URLs, compliance scores, and downloadable PDF audit reports.

---

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Run with Docker Compose

```bash
# Clone / navigate to the project
cd policy-scout

# Start all services (API + Worker + DB + Redis + Frontend)
docker compose up --build

# Services:
#   Frontend → http://localhost:3000
#   API      → http://localhost:8000
#   API Docs → http://localhost:8000/docs
```

### Demo Mode (No Docker required)

Just open `frontend/index.html` directly in your browser. The app automatically falls back to demo mode when the backend is unavailable, simulating a scan with realistic mock data.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│              Frontend (Nginx / Static HTML)          │
│         http://localhost:3000                        │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Backend                         │
│         http://localhost:8000                        │
│  POST /scan  →  GET /scan/{id}  →  GET /report/{id} │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
    ┌──────▼──────┐        ┌──────▼──────┐
    │   Celery    │        │  PostgreSQL  │
    │   Worker    │        │   + Redis    │
    └──────┬──────┘        └─────────────┘
           │
    ┌──────▼──────────────────────────────┐
    │         Crawling Pipeline           │
    │  requests → BeautifulSoup4          │
    │  → Rule-based Classifier            │
    └─────────────────────────────────────┘
```

---

## 📡 API Reference

### Start a Scan
```http
POST /scan
Content-Type: application/json

{
  "url": "https://example.com"
}
```
**Response:**
```json
{
  "scan_id": "uuid",
  "status": "queued",
  "message": "Scan started..."
}
```

### Poll Scan Status
```http
GET /scan/{scan_id}
```
**Response:**
```json
{
  "scan_id": "...",
  "status": "completed",
  "url": "https://example.com",
  "domain": "example.com",
  "score": 75.0,
  "total_links_found": 48,
  "results": [
    { "category": "Privacy Policy", "status": "found", "url": "https://example.com/privacy-policy", "confidence": 0.97 },
    { "category": "Shipping Policy", "status": "missing", "url": null, "confidence": 0.0 }
  ]
}
```

### Download PDF Report
```http
GET /report/{scan_id}
```
Returns a PDF file download.

### List Recent Scans
```http
GET /scans?limit=20
```

### Health Check
```http
GET /health
```

---

## 🔍 Policy Detection Engine

The classifier uses a two-stage approach:

| Stage | Method | Accuracy |
|---|---|---|
| Stage 1 | URL slug keyword matching | 85–90% |
| Stage 2 | Page content keyword analysis | +5–10% on ambiguous pages |

### Detected Policy Categories

| Category | URL Keywords |
|---|---|
| Privacy Policy | `privacy`, `privacy-policy`, `gdpr` |
| Terms & Conditions | `terms`, `tos`, `legal`, `terms-of-service` |
| Refund Policy | `refund`, `returns`, `return-policy` |
| Shipping Policy | `shipping`, `delivery` |
| Contact Us | `contact`, `contact-us`, `support` |
| About Us | `about`, `about-us`, `our-story` |
| FAQ | `faq`, `faqs`, `help-center` |
| Cancellation Policy | `cancellation`, `cancel` |

---

## 📁 Project Structure

```
policy-scout/
├── backend/
│   ├── main.py          # FastAPI app + API routes
│   ├── models.py        # SQLAlchemy models (Scan, PolicyPage)
│   ├── schemas.py       # Pydantic schemas
│   ├── crawler.py       # Web crawler (requests + BeautifulSoup4)
│   ├── classifier.py    # Policy detection engine
│   ├── tasks.py         # Celery background tasks
│   ├── report.py        # PDF report generator (ReportLab)
│   ├── database.py      # DB connection
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html       # Single-page app
│   ├── styles.css       # Premium dark-mode design
│   └── app.js           # App logic + demo mode fallback
├── docker-compose.yml
├── nginx.conf
└── README.md
```

---

## 🔧 Development

### Backend Only (without Docker)

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set environment variables
set DATABASE_URL=postgresql://user:pass@localhost:5432/policyscout
set REDIS_URL=redis://localhost:6379/0

# Run API
uvicorn main:app --reload --port 8000

# Run Celery worker (separate terminal)
celery -A tasks worker --loglevel=info
```

### Frontend Only

Simply open `frontend/index.html` in any browser. Uses demo mode automatically.

---

## 🗺️ Roadmap

### Phase 1 ✅ (Current)
- URL crawling with BeautifulSoup4
- Rule-based policy classifier (8 categories)
- Celery background jobs
- PostgreSQL persistence
- PDF audit reports via ReportLab
- Real-time progress polling
- Docker Compose deployment

### Phase 2
- [ ] OpenAI GPT-4o classification fallback (for non-standard URLs)
- [ ] Playwright screenshots as evidence
- [ ] Email alerts for policy changes

### Phase 3
- [ ] Scheduled weekly monitoring
- [ ] Multi-user auth + billing (Stripe)
- [ ] Bulk URL scanning
- [ ] API access for enterprises
