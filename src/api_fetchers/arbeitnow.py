import logging

import requests

logger = logging.getLogger(__name__)

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


def fetch(config):
    try:
        resp = requests.get(ARBEITNOW_API, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Arbeitnow error: {e}")
        return []

    all_jobs = data.get("data", [])

    jobs = []
    for item in all_jobs:
        title = item.get("title", "").strip()
        company = item.get("company_name", "").strip()
        location = item.get("location", "") or "Remote"
        url = item.get("url", item.get("apply_url", ""))
        posted = item.get("created_at", "")
        description = item.get("description", "")

        tags = item.get("tags", [])

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": posted,
            "source": "arbeitnow",
            "description": description,
        })

    logger.info(f"Arbeitnow: fetched {len(jobs)} jobs")
    return jobs
