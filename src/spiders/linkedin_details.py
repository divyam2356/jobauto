import json
import os
import random
import re

import scrapy


LINKEDIN_GUEST_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class LinkedInDetailsSpider(scrapy.Spider):
    name = "linkedin_details"

    def __init__(self, search_results_file=None, output_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_results_file = search_results_file or "linkedin_search.json"
        self.output_file = output_file or "linkedin_details.json"
        self.results = []

    def start_requests(self):
        input_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", self.search_results_file)
        input_path = os.path.normpath(input_path)

        if not os.path.exists(input_path):
            self.logger.error(f"Search results file not found: {input_path}")
            return

        with open(input_path, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        self.logger.info(f"Fetching details for {len(jobs)} LinkedIn jobs")

        for job in jobs:
            job_id = job.get("job_id", "")
            if not job_id:
                continue

            url = LINKEDIN_GUEST_DETAIL.format(job_id=job_id)
            yield scrapy.Request(
                url=url,
                callback=self.parse_detail,
                dont_filter=True,
                meta={"job": job},
            )

    def parse_detail(self, response):
        job = response.meta["job"]

        description_html = response.css("div.description__text").get("")
        description_text = self._clean_html(description_html)

        seniority = ""
        employment_type = ""
        job_function = ""
        industries = ""

        criteria_items = response.css("li.job-criteria__item")
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
        self.results.append(job)

    def _clean_html(self, html):
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def closed(self, reason):
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", self.output_file)
        output_path = os.path.normpath(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        self.logger.info(f"LinkedIn details: saved {len(self.results)} jobs to {output_path}")
