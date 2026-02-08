# HPCL Lead Intelligence – System Architecture

## Enterprise readiness: SAP/ERP integration

The data model and REST API are designed to be **OData/REST compatible** for future integration with HPCL’s SAP back-end:

- **Entity sets**: `Leads`, `SalesOfficers`, `LeadFeedback`, `NotificationLog`
- **REST**: `GET/PATCH /api/leads`, `GET /api/officers`; schema aligns with typical CRM/lead entities (company, industry, status, score, assigned_officer_id, etc.)
- **Extensibility**: Add `sap_customer_id`, `erp_order_ref` on leads when SAP sync is implemented

## Technical differentiators

### 1. Procurement signal “fingerprinting” (Knowledge Graph)

- **Signal engine** (`services/signal_engine.py`): Maps events (e.g. “expansion”, “marine”, “tender”, “highway”) to HPCL product categories with reasoning.
- Example: “Company X is expanding its factory” → **Expansion** → Bitumen (paving), Industrial Fuels (boilers). Not just keyword match; structured event→product→reasoning.
- Exposed in the **Lead Dossier** as “Signal fingerprint” and in the API as `signal_fingerprint`, `product_reasoning`.

### 2. Lead dossier with “Why HPCL?” (battlecard)

- **Why HPCL** (`services/why_hpcl.py`): Per product (Marine, Bitumen, Cement, ATF, etc.) auto-generates:
  - Headline (e.g. “HPCL Marine Fuels vs industry”)
  - Differentiator points (specs, compliance, logistics)
  - CTA for the sales officer
- **Sales pitch script**: Pre-filled script for the lead (company, industry, products, summary) for mobile/demo “open dossier and call”.

### 3. Feedback loop (reinforcement learning / ML)

- **Our system gets smarter every time a Sales Officer swipes.**
- **ML feedback** (`services/ml_feedback.py`): Random Forest trained on lead features (industry, source, score, confidence, intent_score, priority) and outcome (Accepted/Assigned/Converted vs Rejected). 
- Output: **Feature importances** (which signals actually lead to conversions) and **propensity score** (0–1) for new leads.
- **API**: `POST /api/ml/train` to retrain after new feedback; propensity is stored on leads and shown in dashboard/dossier.

### 4. Entity resolution

- **Entity resolution** (`services/entity_resolution.py`): Normalizes company names (“Tata Motors Ltd” ↔ “Tata Motors”) for **deduplication** and consistent display. Used in discovery so the same company from different sources is not duplicated.

### 5. Workflow (ingestion → scoring → delivery)

- **Ingestion**: RSS-based scrapers for news and tenders (GeM/Tenders24 can be added as specialized scrapers in `services/sources.py`).
- **Scoring**: Firmographics (industry), intent signals (tender, expansion, NLP key phrases), historical feedback (propensity model).
- **Delivery**: WhatsApp (text + optional **interactive buttons**: Accept Lead, Schedule Visit, Not Relevant), FCM push, and **Flutter-ready** REST API (`/api/leads`, `/api/notifications`, `/api/device-token`).

### 6. Geospatial (heat map)

- **Map view** (placeholder): Architecture supports “Heat map of leads” and “While you’re here, 2 bitumen leads within 5km.” Add `latitude`, `longitude` or `region` on leads/officers and expose `/api/leads?near=lat,lng` for the Flutter app.

### 7. Data privacy

- **We only monitor public-domain data** (tenders, news, corporate sites). No scraping of private PII without consent. Data schema and retention can be aligned to GDPR/local policy.

### 8. Why not just LinkedIn Sales Navigator?

- **Sales Navigator finds people; we find procurement signals.** We track Indian government tenders and industrial fuel requirements from factory expansion news, and map them to HPCL products with a Signal Engine and “Why HPCL?” battlecards.
