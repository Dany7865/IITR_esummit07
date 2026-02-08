# HPCL B2B Lead Discovery & Recommendation System

**Enterprise-ready pipeline: Signal fingerprinting, “Why HPCL?” battlecards, ML feedback loop, entity resolution, and Flutter/WhatsApp delivery.**

## Demo flow (for judges)

1. **Before**: “Sales Officers manually browse tender portals and newspapers. Leads are often cold by the time they reach out.”
2. **Live signal**: Go to **Run Discovery** → system fetches news/tenders, runs NLP + Signal Engine, builds dossiers.
3. **Intelligent recommendation**: Open a **Lead Dossier** → see “Signal fingerprint” (e.g. highway → Bitumen VG-30) and “Why HPCL?” battlecard.
4. **Mobile close**: Notification (WhatsApp + optional interactive buttons: Accept / Schedule Visit / Not Relevant); SO clicks Accept → dossier opens with **Sales pitch script** ready.

## Judge Q&A

**Q: Data privacy / GDPR?**  
We only monitor public-domain data (tenders, news, corporate sites). No scraping of private PII without consent.

**Q: How is this better than LinkedIn Sales Navigator?**  
Sales Navigator finds people; we find **procurement signals**. We track Indian government tenders and industrial fuel requirements from expansion news and map them to HPCL products with a Signal Engine and “Why HPCL?” battlecards.

---

# HPCL B2B Lead Discovery & Recommendation System (details)

AI-powered lead discovery for **HP Direct Sales (HPCL)**. The system monitors public web sources (news, tenders, directories), extracts procurement signals, predicts HPCL products (industrial fuels, bitumen, marine fuels, specialty products, etc.), and generates **Lead Dossiers** with confidence scores and suggested sales actions. Sales officers are notified via **WhatsApp** and can update lead status; feedback (accepted/rejected/converted) improves future recommendations.

## Features

- **Web intelligence**: News RSS and tender RSS (configurable); placeholder for directory sources
- **Intelligent extraction**: Industry and product signals from text; requirement clues for dossiers
- **Lead scoring**: Score, confidence, priority (HIGH/MEDIUM/LOW) with optional feedback-based weights
- **Lead Dossier**: Company, industry, product recommendations, requirement clues, suggested actions
- **Notifications**: WhatsApp (Meta Cloud API); placeholder for mobile app push
- **Feedback loop**: Assign / Reject / Convert updates scoring weights for better future leads
- **Mobile-ready API**: REST API for mobile app (list leads, get dossier, update status)

## Setup

1. **Python 3.10+** recommended.

2. **Install dependencies** (from this folder):
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure** (optional): Copy `.env.example` to `.env` and set:
   - `WHATSAPP_TOKEN`, `PHONE_ID`, `SALES_NUMBER` for WhatsApp
   - `SECRET_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD` for web login
   - `DATABASE_PATH` if not using default `leads.db`

4. **Run**:
   ```bash
   python app.py
   ```
   Open http://127.0.0.1:5000 → Login → Dashboard. Use **Run discovery now** to fetch and score leads.

## Scheduled discovery

Run discovery on a schedule (cron or Windows Task Scheduler) so new leads are added automatically:

```bash
# Example: every 6 hours (Linux/Mac cron)
0 */6 * * * cd /path/to/application.py && python -c "from app import run_discovery; run_discovery()"
```

Or call the `/discover` URL (when logged in) or a small script that imports `run_discovery` from `app`.

## Notifications

- **New lead**: When discovery adds a lead that meets confidence/priority thresholds, the default officer gets WhatsApp + (if configured) FCM push. All sends are logged in `notification_log`.
- **Assigned**: When a lead is assigned to an officer, that officer gets WhatsApp + FCM with “Lead assigned to you” and a link to the lead.
- **Config**: `NOTIFY_ON_NEW_LEAD`, `NOTIFY_ON_ASSIGN`, `FCM_SERVER_KEY`, `BASE_URL`, `MAX_WHATSAPP_BODY` in config / `.env`.
- **Mobile**: Register device tokens via `POST /api/device-token`; poll `GET /api/notifications?officer_id=<id>` to show in-app notification list.

## API (for mobile app)

- `GET /api/leads` – list all leads (dossiers)
- `GET /api/leads/<id>` – single lead dossier
- `PATCH /api/leads/<id>` – update status: `{"status": "Assigned"|"Rejected"|"Converted"|"Accepted", "assigned_officer_id": 1, "notes": "..."}`
- `GET /api/officers` – list sales officers (for assignment)
- `POST /api/device-token` – register FCM token: `{"officer_id": 1, "token": "<fcm_token>", "platform": "android"|"ios"}`
- `GET /api/notifications?officer_id=1&limit=50` – list notifications for that officer (for in-app inbox)

## Database

- **leads**: Full dossier (company, industry, product_recommendations, requirement_clues, score, confidence, priority, suggested_actions, status, assigned_officer_id, source, source_url)
- **sales_officers**: Name, phone, email, region (for assignment and WhatsApp)
- **lead_feedback**: Outcome and notes (drives weight updates)
- **scoring_weights**: Learned weights per industry/signal for adaptive scoring

## NLP

The app includes an NLP layer (`services/nlp.py`) that:

- **Cleans text**: Strips HTML and normalizes whitespace before analysis.
- **Tokenization**: Uses NLTK when available (with fallback to regex) and stopword removal.
- **Key phrase extraction**: Extracts 2–3 word phrases (e.g. "marine fuel", "cement expansion") that overlap industry/product/procurement terms and adds them as requirement clues and for industry detection.
- **Scoring boost**: When NLP finds 2+ key phrases or organization entities, the lead score gets a small boost (up to +5).
- **Optional spaCy**: If `spacy` and `en_core_web_sm` are installed, `extract_entities()` returns ORG and PRODUCT entities for richer clues; otherwise the pipeline runs without them.

First-time NLTK use will download `punkt` and `stopwords` automatically. Optional spaCy: `pip install spacy && python -m spacy download en_core_web_sm`.

## Extending

- **More sources**: Implement directory scrapers in `services/sources.py` (same item shape: company, raw_text, source, source_url).
- **LLM**: Add an optional LLM call in `services/nlp.py` or `services/dossier.py` for summarization or extra product suggestions.
- **Mobile push**: Implement `send_mobile_push()` in `services/notifications.py` (e.g. FCM/APNs).
