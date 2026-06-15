import os
import logging

import requests

logger = logging.getLogger(__name__)

ADZUNA_API_BASE = "https://api.adzuna.com/v1/api"


def fetch(config):
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")

    if not app_id or not app_key or app_id == "xxx" or app_key == "xxx":
        logger.warning("ADZUNA_APP_ID or ADZUNA_APP_KEY not properly set, skipping Adzuna")
        return []

    countries = config.get("adzuna", {}).get("countries", ["in"])
    search_terms = config.get("adzuna", {}).get("search_terms", ["software engineer"])

    jobs = []
    for country in countries:
        for term in search_terms:
            page = 1
            max_pages = 3
            while page <= max_pages:
                url = f"{ADZUNA_API_BASE}/jobs/{country}/search/{page}"
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": term,
                    "results_per_page": 50,
                    "content-type": "application/json",
                }
                try:
                    resp = requests.get(url, params=params, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.error(f"Adzuna error for {country}/{term} page {page}: {e}")
                    break

                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    loc = item.get("location", {})
                    display_name = ", ".join(loc.get("area", [])[-2:]) if loc.get("area") else ""

                    jobs.append({
                        "title": item.get("title", "").strip(),
                        "company": item.get("company", {}).get("display_name", "").strip(),
                        "location": display_name,
                        "url": item.get("redirect_url", ""),
                        "posted_date": item.get("created", ""),
                        "source": "adzuna",
                        "description": item.get("description", ""),
                    })

                if len(results) < 50:
                    break
                page += 1

    logger.info(f"Adzuna: fetched {len(jobs)} jobs")
    return jobs
