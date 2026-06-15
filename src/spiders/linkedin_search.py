import json
import os
import re
import time
import random

import scrapy


LINKEDIN_GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

EXPERIENCE_LEVEL_MAP = {
    "internship": "1",
    "entry": "2",
    "associate": "3",
    "mid-senior": "4",
    "director": "5",
    "executive": "6",
}

LINKEDIN_LOCATION_GEOIDS = {
    "india": "102717330",
    "remote": "92000000",
    "united states": "103644278",
    "united kingdom": "101165590",
    "germany": "101282230",
    "canada": "101174742",
}


class LinkedInSearchSpider(scrapy.Spider):
    name = "linkedin_search"

    def __init__(self, queries_json=None, output_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if queries_json:
            self.queries = json.loads(queries_json)
        else:
            self.queries = []
        self.output_file = output_file or "linkedin_search.json"
        self.results = []

    def start_requests(self):
        self.logger.info("Starting LinkedIn search with %d queries", len(self.queries))
        for qi, query in enumerate(self.queries):
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

                self.logger.info("Searching: '%s' in %s", keywords, location)
                yield scrapy.Request(
                    url=LINKEDIN_GUEST_SEARCH,
                    callback=self.parse_search,
                    cb_kwargs={"keywords": keywords, "location": location, "page": 0},
                    dont_filter=True,
                    meta={
                        "params": params,
                        "keywords": keywords,
                        "location": location,
                    },
                )

    def parse_search(self, response, keywords, location, page):
        job_cards = response.css("li")

        if not job_cards:
            self.logger.info("No more results for '%s' in %s at page %d", keywords, location, page)
            return

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

            item = {
                "title": title,
                "company": company,
                "location": location_text or location,
                "url": job_url.split("?")[0],
                "job_id": job_id,
                "posted_date": posted,
                "source": "linkedin",
                "search_keywords": keywords,
                "search_location": location,
            }
            self.results.append(item)
            count += 1

        self.logger.info("Found %d jobs for '%s' in %s (page %d, total: %d)", count, keywords, location, page, len(self.results))

        max_pages = int(self.meta.get("max_pages", 5)) if hasattr(self, "meta") else 5
        if page < max_pages - 1:
            next_page = (page + 1) * 25
            params = response.meta["params"].copy()
            params["start"] = str(next_page)

            next_url = f"{LINKEDIN_GUEST_SEARCH}?{self._encode_params(params)}"
            delay = random.uniform(3.0, 6.0)

            yield scrapy.Request(
                url=next_url,
                callback=self.parse_search,
                cb_kwargs={
                    "keywords": keywords,
                    "location": location,
                    "page": page + 1,
                },
                dont_filter=True,
                meta={
                    "params": params,
                    "keywords": keywords,
                    "location": location,
                },
                priority=1,
            )

    def _encode_params(self, params):
        parts = []
        for k, v in params.items():
            if v:
                parts.append(f"{k}={v}")
        return "&".join(parts)

    def closed(self, reason):
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", self.output_file)
        output_path = os.path.normpath(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        self.logger.info(f"LinkedIn search: saved {len(self.results)} jobs to {output_path}")
