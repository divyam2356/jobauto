import logging

import requests

logger = logging.getLogger(__name__)

ASHBY_API_BASE = "https://api.ashbyhq.com/posting-api/job-board"


def fetch(config):
    boards = config.get("ashby", {}).get("boards", [])

    jobs = []
    for board in boards:
        name = board.get("name", "")
        slug = board.get("slug", "")
        if not slug:
            continue

        url = f"{ASHBY_API_BASE}/{slug}"

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Ashby error for {name}: {e}")
            continue

        board_jobs = data.get("jobs", [])
        for item in board_jobs:
            title = item.get("title", "").strip()
            location = item.get("location", "")
            job_url = item.get("jobUrl", "")
            apply_url = item.get("applyUrl", "")
            posted = item.get("publishedAt", "")
            department = item.get("department", "")
            employment_type = item.get("employmentType", "")

            desc_plain = item.get("descriptionPlain", "")
            desc_html = item.get("descriptionHtml", "")
            description = desc_plain or desc_html

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "url": apply_url or job_url,
                "posted_date": posted,
                "source": "ashby",
                "description": description,
            })

    logger.info(f"Ashby: fetched {len(jobs)} jobs from {len(boards)} boards")
    return jobs
