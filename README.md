# cqai
AI app

Your WhatsApp AI Summary Project is now at the correct transition point: data ingestion is complete; intelligence layer begins.

## Deployment / AWS Lightsail Notes

- The repository is designed to run on a Linux host such as an AWS Lightsail Ubuntu instance.
- Use environment variables to override local paths and OpenClaw configuration.
- The collector reads the OpenClaw gateway logs and writes messages into `messages.db`.
- The normaliser and AI enricher both use `DB_PATH` so they can share the same SQLite database.

### Recommended environment variables

```bash
export DB_PATH="$HOME/whatsapp-summary/data/messages.db"
export OPENCLAW_BINARY="/usr/bin/openclaw"
export OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
export AWS_REGION="ap-south-1"
export BEDROCK_MODEL="bedrock/global.anthropic.claude-sonnet-4-6"
# Optionally use an inference profile ID or ARN for Bedrock models that require it
export BEDROCK_INFERENCE_PROFILE="arn:aws:bedrock:..."
export BATCH_SIZE="50"
export SLEEP_SECONDS="30"
# Feature toggles
export ENABLE_TEXT_ENRICHMENT="false"
```

### Run the pipeline

```bash
python3 scripts/collector.py
python3 scripts/normaliser.py
python3 scripts/ai_enricher.py
```

### Notes for Lightsail / OpenClaw

- Install OpenClaw and configure the gateway token at `~/.openclaw/openclaw.json`.
- If your OpenClaw binary is not at `/usr/bin/openclaw`, set `OPENCLAW_BINARY`.
- Keep the same `DB_PATH` across collector, normaliser, and enricher.

Current Pipeline Status
WhatsApp
   |
   v
OpenClaw Channel
   |
   v
collector.py                 ✅ DONE
   |
   v
messages.db                  ✅ DONE
   |
   v
normaliser.py                ✅ DONE
   |
   v
ai_enricher.py               ⏳ NEXT
   |
   v
summarizer.py                ⏳ NEXT
   |
   v
AI Search / Reports / Alerts
Completed Components
1. Message Collection ✅

whatsapp-collector.service

Captures:

Type	Status
Text	✅
Image	✅
Image captions	✅
Video	✅
Audio	✅
PDF/Documents	✅
Media paths	✅

Raw data stored:

body
message_type
media_path
media_type
media_filename
timestamp
sender
group_id
2. Normalisation Layer ✅

whatsapp-normaliser.service

Converts raw messages into AI input.

Example:

Image

Before:

body:
Important

message_type:
image

media_filename:
photo.jpg

After:

normalized_content:

IMAGE

Filename:
photo.jpg

Caption:
Important

AI Description:
Pending AI analysis
3. Database Layer ✅

Final schema supports:

messages

├── Raw Content
│   ├── body
│   ├── message_type
│   ├── media_path
│   └── media_filename
│
├── Processing
│   ├── normalized_content
│   ├── enrichment_status
│   ├── enriched_at
│
└── AI Results
    ├── ai_content
    ├── ai_metadata
    ├── ocr_text
    ├── transcript
    └── ai_caption
Next Component: ai_enricher.py

Recommended design:

ai_enricher.py

Read:

SELECT *
FROM messages
WHERE enrichment_status='pending'


        |
        |

Detect type


        |
        +----------------+
        |                |
        v                v

IMAGE              DOCUMENT
Vision Model       OCR


        |
        v

Extracted Content


        |
        v

LLM Processing


        |
        v

Update Database
Processing Logic
Text

Input:

body:
Meeting tomorrow at 3 PM with supplier

AI:

ai_content:

Event:
Supplier meeting

Date:
Tomorrow 3 PM

Category:
Business
Image

Flow:

image file
   |
   v
Vision Model
   |
   v
ai_caption
   |
   v
LLM summary

Example:

Input:

invoice.jpg

Output:

ai_caption:

Invoice from ABC Traders

Detected:
Invoice number
Amount
Date


ai_content:

Purchase invoice received.
Amount ₹45,000.
Supplier ABC Traders.
PDF

Flow:

PDF
 |
 +--> pdftotext
 |
 +--> OCR if scanned
 |
 v

ocr_text

 |
 v

LLM
 |
 v

Summary
Audio

Flow:

audio file
 |
 v
Whisper
 |
 v
transcript
 |
 v
LLM
 |
 v
summary

Example:

transcript:

"Please send quotation by Friday"


ai_content:

Action Item:
Send quotation

Deadline:
Friday
Suggested Additional Columns

For production, add:

ALTER TABLE messages ADD COLUMN ai_model TEXT;

ALTER TABLE messages ADD COLUMN processing_time INTEGER;

ALTER TABLE messages ADD COLUMN error_message TEXT;

ALTER TABLE messages ADD COLUMN category TEXT;

ALTER TABLE messages ADD COLUMN priority TEXT;

ALTER TABLE messages ADD COLUMN entities TEXT;

This enables:

model tracking
retries
analytics
search
workflow automation
Recommended AI Architecture

Since you already use AWS/OpenClaw:

ai_enricher.py

        |
        |
        +--> Amazon Bedrock
        |       |
        |       +--> Claude Vision
        |       +--> Claude Sonnet
        |
        |
        +--> Whisper
        |
        +--> OCR Engine

Alternative:

OpenAI GPT-4.1 / GPT-4o Vision
+
Whisper
After AI Enrichment

You can build:

1. Daily WhatsApp Intelligence Report

Example:

Group:
Purchase Team

Today:

12 messages analyzed

Important:

1. Supplier ABC sent quotation
2. Raw material price increased
3. Delivery delayed

Action Items:

John:
Follow up supplier

Manager:
Approve PO
2. Semantic Search

Example:

User asks:

"What did supplier ABC say last month?"

AI searches:

messages.db
     |
embeddings
     |
vector database
     |
answer
3. ERP Integration

For Cogniquaint:

WhatsApp →

AI →

ERPNext/Cogniquaint:

Invoice received
        |
        v
Create Purchase Invoice


Customer enquiry
        |
        v
Create Lead


Payment message
        |
        v
Payment Entry reminder
Current Project Maturity
Layer	Status
WhatsApp ingestion	✅ 100%
Media capture	✅ 100%
Database	✅ 100%
Normalisation	✅ 100%
AI enrichment	⏳ 0%
Summaries	⏳ 0%
Semantic search	⏳ 0%
ERP automation	⏳ Future

The foundation is ready. The next milestone is implementing ai_enricher.py as a worker service, similar to your collector and normaliser.