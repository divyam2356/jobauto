import json
import logging
import os
import re
import time
import random

import requests
from parsel import Selector

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LINKEDIN_GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_GUEST_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

LINKEDIN_LOCATION_GEOIDS = {
    "india": "102717330",
    "remote": "92000000",
    "united states": "103644278",
    "united kingdom": "101165590",
    "germany": "101282230",
    "canada": "101174742",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def _get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return session


def _search_jobs(session, queries):
    all_jobs = []
    for query in queries:
        keywords = query["keywords"]
        locations = query.get("locations", ["remote"])

        for location in locations:
            geo_id = LINKEDIN_LOCATION_GEOIDS.get(location.lower().strip(), "")
            params = {
                "keywords": keywords,
                "location": location,
                "f_E": "2",
                "f_TPR": "r604800",
                "start": "0",
            }
            if geo_id:
                params["geoId"] = geo_id
            if location.lower() == "remote":
                params["f_WT"] = "2"

            logger.info("LinkedIn search: '%s' in %s", keywords, location)

            for page in range(5):
                params["start"] = str(page * 25)
                param_str = "&".join(f"{k}={v}" for k, v in params.items() if v)
                url = f"{LINKEDIN_GUEST_SEARCH}?{param_str}"

                try:
                    resp = session.get(url, timeout=15)
                    if resp.status_code != 200:
                        logger.warning("LinkedIn search HTTP %d for '%s' page %d", resp.status_code, keywords, page)
                        break

                    selector = Selector(text=resp.text)
                    job_cards = selector.css("li")

                    if not job_cards:
                        break

                    count = 0
                    for card in job_cards:
                        title = card.css("h3.base-search-card__title::text").get("").strip()
                        company = card.css("h4.base-search-card__subtitle::text").get("").strip()
                        location_text = card.css("span.job-search-card__location::text").get("").strip()
                        job_url = card.css("a.base-card__full-link::attr(href)").get("")
                        posted = card.css("time::attr(datetime)").get("")

                        if not title or not job_url:
                            continue

                        job_id_match = re.search(r"view/(\d+)", job_url)
                        job_id = job_id_match.group(1) if job_id_match else ""

                        all_jobs.append({
                            "title": title,
                            "company": company,
                            "location": location_text or location,
                            "url": job_url.split("?")[0],
                            "job_id": job_id,
                            "posted_date": posted,
                            "source": "linkedin",
                            "search_keywords": keywords,
                            "search_location": location,
                        })
                        count += 1

                    logger.info("Found %d jobs for '%s' in %s (page %d)", count, keywords, location, page)
                    time.sleep(random.uniform(3.0, 6.0))

                except Exception as e:
                    logger.warning("LinkedIn search error for '%s': %s", keywords, e)
                    break

    return all_jobs


def _fetch_details(session, jobs):
    detailed = []
    for i, job in enumerate(jobs):
        job_id = job.get("job_id", "")
        if not job_id:
            detailed.append(job)
            continue

        url = LINKEDIN_GUEST_DETAIL.format(job_id=job_id)
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                logger.warning("LinkedIn detail HTTP %d for job %s", resp.status_code, job_id)
                detailed.append(job)
                continue

            selector = Selector(text=resp.text)

            description_html = selector.css("div.description__text").get("")
            description_text = _clean_html(description_html)

            seniority = ""
            employment_type = ""
            job_function = ""
            industries = ""

            criteria_items = selector.css("li.job-criteria__item")
            for item in criteria_items:
                header = item.css("h3.job-criteria__subheader::text").get("").strip().lower()
                value = item.css("span.job-criteria__text::text").get("").strip()

                if "seniority" in header:
                    seniority = value
                elif "employment" in header or "type" in header:
                    employment_type = value
                elif "function" in header:
                    job_function = value
                elif "industries" in header or "industry" in header:
                    industries = value

            job.update({
                "description": description_text,
                "seniority": seniority,
                "employment_type": employment_type,
                "job_function": job_function,
                "industries": industries,
            })
            detailed.append(job)

            if (i + 1) % 20 == 0:
                logger.info("Fetched details for %d/%d jobs", i + 1, len(jobs))

            time.sleep(random.uniform(1.5, 3.5))

        except Exception as e:
            logger.warning("LinkedIn detail error for %s: %s", job_id, e)
            detailed.append(job)

    return detailed


def _clean_html(html):
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_spiders(queries, output_dir=None):
    if output_dir is None:
        output_dir = PROJECT_ROOT

    total_queries = sum(len(q.get("locations", ["remote"])) for q in queries)
    logger.info("Running LinkedIn spider (%d queries, ~%ds)...", total_queries, total_queries * 8)

    session = _get_session()

    search_jobs = _search_jobs(session, queries)
    logger.info("LinkedIn search: found %d jobs", len(search_jobs))

    search_path = os.path.join(output_dir, "linkedin_search.json")
    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(search_jobs, f, indent=2, ensure_ascii=False)

    detailed_jobs = _fetch_details(session, search_jobs)
    logger.info("LinkedIn details: fetched %d jobs", len(detailed_jobs))

    details_path = os.path.join(output_dir, "linkedin_details.json")
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(detailed_jobs, f, indent=2, ensure_ascii=False)

    logger.info("LinkedIn: got %d jobs", len(detailed_jobs))
    return detailed_jobs
