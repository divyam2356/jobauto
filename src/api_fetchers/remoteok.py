import logging

import requests

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"


def fetch(config):
    tags = config.get("remoteok", {}).get("tags", [])

    try:
        resp = requests.get(REMOTEOK_API, timeout=15)
        resp.raise_for_status()
        all_jobs = resp.json()
    except Exception as e:
        logger.error(f"RemoteOK error: {e}")
        return []

    if not isinstance(all_jobs, list) or len(all_jobs) < 2:
        return []

    all_jobs = all_jobs[1:]

    jobs = []
    seen_ids = set()

    for item in all_jobs:
        job_id = item.get("id", "")
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        position = item.get("position", "").strip()
        company = item.get("company", "").strip()
        location = item.get("location", "").strip() or "Remote"
        url = item.get("url", "") or item.get("apply_url", "")
        posted = item.get("date", "")
        description = item.get("description", "")
        job_tags = item.get("tags", [])

        if tags:
            tag_match = any(
                tag.lower() in [t.lower() for t in job_tags]
                for tag in tags
            )
            if not tag_match:
                continue

        jobs.append({
            "title": position,
            "company": company,
            "location": location,
            "url": url,
            "posted_date": posted,
            "source": "remoteok",
            "description": description,
        })

    logger.info(f"RemoteOK: fetched {len(jobs)} jobs")
    return jobs
