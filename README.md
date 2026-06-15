# Job Aggregator

Automated job scraper that fetches entry-level ML/AI/Software Engineer/Data Scientist jobs from multiple sources and pushes them to a Notion database. Runs daily via GitHub Actions.

## Sources

- **LinkedIn** — Public guest API (no login required), via Scrapy
- **Adzuna** — India job aggregator API
- **RemoteOK** — Global remote jobs API
- **Arbeitnow** — Germany/Europe jobs API
- **Greenhouse** — Anthropic, Hugging Face career pages
- **Ashby** — Modal, Together AI, Anyscale career pages

## Setup

### 1. Create Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Name it "Job Aggregator"
4. Copy the "Internal Integration Secret" (starts with `ntn_`)
5. Create a `.env` file: `cp .env.example .env`
6. Add your token: `NOTION_TOKEN=ntn_xxx`

### 2. Create Notion Database (auto)

```bash
python setup_notion.py
```

This will:
- Show you your Notion pages to pick from (or create at workspace root)
- Create a "Job Aggregator" database with all columns pre-configured
- Save the `NOTION_DATABASE_ID` to your `.env` automatically

### 3. Get Adzuna API Key

1. Go to https://developer.adzuna.com/signup
2. Register for a free account
3. Copy your App ID and App Key
4. Add to `.env`: `ADZUNA_APP_ID=xxx` and `ADZUNA_APP_KEY=xxx`

### 4. Run Locally

```bash
pip install -r requirements.txt
python -m src.main
```

### 5. Deploy to GitHub Actions

1. Push this repo to GitHub
2. Add secrets in Settings → Secrets → Actions:
   - `NOTION_TOKEN`
   - `NOTION_DATABASE_ID`
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
3. The workflow runs daily at 9:00 AM UTC automatically

## Project Structure

```
jobautomation/
├── .github/workflows/daily_jobs.yml   # GitHub Actions cron
├── setup_notion.py                    # Auto-create Notion database
├── src/
│   ├── main.py                        # Entry point
│   ├── scrapy_run.py                  # Scrapy subprocess runner
│   ├── middlewares.py                  # User-agent rotation
│   ├── filters.py                     # Entry-level filtering
│   ├── notion_client.py               # Notion DB read/write
│   ├── spiders/
│   │   ├── linkedin_search.py         # LinkedIn search spider
│   │   └── linkedin_details.py        # LinkedIn detail spider
│   └── api_fetchers/
│       ├── adzuna.py
│       ├── remoteok.py
│       ├── arbeitnow.py
│       ├── greenhouse.py
│       └── ashby.py
├── config.yaml                        # Search queries, company list
├── settings.py                        # Scrapy settings
├── requirements.txt
└── .env.example
```

## Configuration

Edit `config.yaml` to customize:

- **linkedin.search_queries** — keywords and locations to search
- **greenhouse.boards** — companies using Greenhouse ATS
- **ashby.boards** — companies using Ashby ATS
- **adzuna.countries** — countries to search on Adzuna
- **entry_level.include/exclude** — title keywords for filtering

## Adding More Companies

### Greenhouse companies
Find the board token from the company's careers URL: `https://boards.greenhouse.io/{board_token}`

### Ashby companies
Find the slug from the company's careers URL: `https://jobs.ashbyhq.com/{slug}`

Add them to `config.yaml` under the respective sections.

## Maintenance

If LinkedIn changes their HTML structure, use the Scrapy MCP server to debug:

```bash
uvx scrapy-mcp-server
```

Then ask your AI assistant to inspect and fix the spiders.
