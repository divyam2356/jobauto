import logging

import requests

logger = logging.getLogger(__name__)

GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"


def fetch(config):
    boards = config.get("greenhouse", {}).get("boards", [])

    jobs = []
    for board in boards:
        name = board.get("name", "")
        token = board.get("token", "")
        if not token:
            continue

        url = f"{GREENHOUSE_API_BASE}/{token}/jobs"
        params = {"content": "true"}

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Greenhouse error for {name}: {e}")
            continue

        board_jobs = data.get("jobs", [])
        for item in board_jobs:
            title = item.get("title", "").strip()
            location = item.get("location", {}).get("name", "")
            absolute_url = item.get("absolute_url", "")
            updated = item.get("updated_at", "")
            content = item.get("content", "")

            departments = item.get("departments", [])
            dept_name = departments[0].get("name", "") if departments else ""

            jobs.append({
                "title": title,
                "company": name,
                "location": location,
                "url": absolute_url,
                "posted_date": updated,
                "source": "greenhouse",
                "description": content,
            })

    logger.info(f"Greenhouse: fetched {len(jobs)} jobs from {len(boards)} boards")
    return jobs
