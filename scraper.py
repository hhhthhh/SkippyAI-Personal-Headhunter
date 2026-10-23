import html
import ipaddress
import random
import re
import socket
import time
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, urlencode, parse_qs, urljoin

import requests
from requests.adapters import HTTPAdapter
import streamlit as st
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

from posting_guard import guard as run_posting_guard

LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting"
LINKEDIN_HOST_RE = re.compile(r"(^|\.)linkedin\.com$", re.I)

FREEHIRE_BASE_URL = "https://freehire.me"
FREEHIRE_AGENT_SEARCH_PATH = "/api/v1/agent/jobs/search"
FREEHIRE_REGION_VALUES = (
    "global",
    "north_america",
    "latam",
    "eu",
    "uk",
    "mena",
    "africa",
    "apac",
    "cis",
    "none",
)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB upper bound for scraped HTML/JSON payloads
_BLOCKED_CONTENT_PREFIXES = (
    "application/octet-stream",
    "application/zip",
    "application/pdf",
    "image/",
    "video/",
    "audio/",
)

_SHARED_HTTP_SESSION: Optional[requests.Session] = None


def _get_http_session() -> requests.Session:
    """Returns a shared HTTP session with keep-alive connection pooling."""
    global _SHARED_HTTP_SESSION
    if _SHARED_HTTP_SESSION is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _SHARED_HTTP_SESSION = session
    return _SHARED_HTTP_SESSION


def _http_get(url: str, **kwargs) -> requests.Response:
    """Uses the pooled Session in production while honoring unittest.mock patches on requests.get."""
    if getattr(requests.get, "__module__", "") != "requests.api":
        return requests.get(url, **kwargs)
    return _get_http_session().get(url, **kwargs)


def is_safe_url(url: str, allow_unresolved: bool = True) -> bool:
    """
    Validates that a URL is a safe public HTTP or HTTPS URL.
    Blocks SSRF targets including loopback, local network, link-local (cloud metadata),
    and non-HTTP schemes (file://, javascript:, data:, etc.).
    """
    if not url or not isinstance(url, str):
        return False
        
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        hostname_lower = hostname.lower()
        
        # Block localhost and local development aliases
        blocked_names = {
            "localhost", "localhost.localdomain", "broadcasthost",
            "metadata.google.internal", "instance-data"
        }
        if hostname_lower in blocked_names:
            return False
            
        if hostname_lower.endswith((".localhost", ".local", ".internal")):
            return False
            
        # Check if the hostname is a direct IP address
        try:
            ip = ipaddress.ip_address(hostname_lower)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
            return True
        except ValueError:
            pass
            
        # For domain names, resolve to IP addresses and ensure none point to internal/metadata IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip = ipaddress.ip_address(item[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
        except (socket.gaierror, socket.herror, OSError):
            # If DNS lookup is unavailable (e.g. offline sandbox), permit domains with a valid structure
            if allow_unresolved and "." in hostname_lower:
                return True
            return False
            
        return True
    except Exception:
        return False


def normalize_linkedin_job_id(input_str: str) -> Optional[str]:
    """
    Accepts a raw LinkedIn job ID, a job URN, a LinkedIn job-view or search URL
    (e.g. linkedin.com/jobs/view/... or ?currentJobId=...), or a slug ending in the ID.
    Rejects URLs from any non-LinkedIn host so numeric IDs on other job boards are never misrouted.
    """
    if not input_str or not isinstance(input_str, str):
        return None
    trimmed = input_str.strip()
    if not trimmed:
        return None

    urn_match = re.search(r"urn:li:jobPosting:(\d{6,})", trimmed)
    if urn_match:
        return urn_match.group(1)

    if re.match(r"^\d{6,}$", trimmed):
        return trimmed

    has_scheme = bool(re.match(r"^https?://", trimmed, re.I))
    if has_scheme or re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", trimmed, re.I):
        try:
            parsed = urlparse(trimmed if has_scheme else f"https://{trimmed}")
        except Exception:
            return None
        hostname = parsed.hostname or ""
        if not LINKEDIN_HOST_RE.search(hostname):
            return None
        path_match = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})/?$", parsed.path)
        if path_match:
            return path_match.group(1)
        qs = parse_qs(parsed.query)
        if "currentJobId" in qs and qs["currentJobId"]:
            cid = qs["currentJobId"][0].strip()
            if re.match(r"^\d{6,}$", cid):
                return cid
        return None

    slug_match = re.match(r"^[a-z0-9-]*-(\d{6,})$", trimmed, re.I)
    return slug_match.group(1) if slug_match else None


def _linkedin_guest_fetch(url: str, max_retries: int = 4) -> str:
    """Fetches HTML from LinkedIn's public jobs-guest endpoints with connection pooling and exponential backoff on 429/5xx."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SkippyJobSearch/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    }
    delay = 0.5
    for attempt in range(max_retries + 1):
        resp = _http_get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            return ""
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt == max_retries:
                raise RuntimeError(f"LinkedIn guest endpoint rate-limited or unavailable (HTTP {resp.status_code}).")
            jitter = random.uniform(0.0, 0.4)
            time.sleep(delay + jitter)
            delay = min(delay * 2, 6.0)
            continue
        resp.raise_for_status()
        text = resp.text or ""
        return text[:MAX_RESPONSE_BYTES]
    return ""


def _clean_inline_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", raw_html)
    unescaped = html.unescape(stripped)
    return re.sub(r"\s+", " ", unescaped).strip()


def _extract_div_content(markup: str, class_name: str) -> Optional[str]:
    """Extracts the inner HTML of a <div> with `class_name`, tracking nested <div> depth."""
    escaped = re.escape(class_name)
    open_re = re.compile(rf'<div[^>]*class="[^"]*{escaped}[^"]*"[^>]*>', re.I)
    match = open_re.search(markup)
    if not match:
        return None

    i = match.end()
    depth = 1
    lower_markup = markup.lower()
    while depth > 0 and i < len(markup):
        next_open = lower_markup.find("<div", i)
        next_close = lower_markup.find("</div>", i)
        if next_close == -1:
            return None
        if next_open != -1 and next_open < next_close:
            depth += 1
            i = next_open + 4
        else:
            depth -= 1
            i = next_close + 6

    return markup[match.end():i - 6]


def parse_linkedin_guest_cards(raw_html: str) -> List[Dict[str, Any]]:
    """Parses LinkedIn jobs-guest search response HTML into a list of job card dicts."""
    if not raw_html:
        return []
    results: List[Dict[str, Any]] = []
    chunks = re.split(r'data-entity-urn="urn:li:jobPosting:', raw_html)[1:]

    for chunk in chunks:
        id_match = re.match(r"^(\d+)", chunk)
        if not id_match:
            continue
        job_id = id_match.group(1)

        link_match = re.search(r'class="base-card__full-link[^"]*"[^>]*href="([^"]+)"', chunk, re.I)
        url = html.unescape(link_match.group(1)).split("?")[0] if link_match else f"https://www.linkedin.com/jobs/view/{job_id}"

        title = None
        h3_match = re.search(r'class="base-search-card__title"[^>]*>([\s\S]*?)</h3>', chunk, re.I)
        if h3_match:
            title = _clean_inline_html(h3_match.group(1))
        if not title:
            sr_match = re.search(r'class="sr-only"[^>]*>([\s\S]*?)</span>', chunk, re.I)
            if sr_match:
                title = _clean_inline_html(sr_match.group(1))
        if not title:
            continue

        company = None
        company_url = None
        sub_match = re.search(r'class="base-search-card__subtitle"[^>]*>([\s\S]*?)</h4>', chunk, re.I)
        if sub_match:
            a_match = re.search(r'href="([^"]+)"', sub_match.group(1), re.I)
            if a_match:
                company_url = html.unescape(a_match.group(1)).split("?")[0]
            company = _clean_inline_html(sub_match.group(1)) or None

        loc_match = re.search(r'class="job-search-card__location"[^>]*>([\s\S]*?)</span>', chunk, re.I)
        location = _clean_inline_html(loc_match.group(1)) if loc_match else None

        dt_match = re.search(r'class="job-search-card__listdate[^"]*"[^>]*datetime="([^"]+)"', chunk, re.I)
        posted_date = dt_match.group(1) if dt_match else None

        results.append({
            "id": job_id,
            "title": title,
            "company": company or "Unknown Company",
            "company_url": company_url,
            "location": location or "",
            "date": posted_date or "",
            "url": f"https://www.linkedin.com/jobs/view/{job_id}",
            "original_url": url,
            "source_board": "LinkedIn",
        })
    return results


def parse_linkedin_guest_detail(raw_html: str, job_id: str) -> Dict[str, Any]:
    """Parses a LinkedIn jobs-guest single posting HTML page and runs Posting Guard."""
    title_match = re.search(
        r'class="(?:top-card-layout__title|topcard__title)[^"]*"[^>]*>([\s\S]*?)</h[12]>',
        raw_html,
        re.I,
    )
    title = _clean_inline_html(title_match.group(1)) if title_match else "(Untitled Role)"

    org_match = re.search(
        r'class="topcard__org-name-link[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
        raw_html,
        re.I,
    )
    company = _clean_inline_html(org_match.group(2)) if org_match else None
    if not company:
        org_fallback = re.search(r'class="topcard__flavor"[^>]*>([\s\S]*?)</span>', raw_html, re.I)
        if org_fallback:
            company = _clean_inline_html(org_fallback.group(1))

    loc_match = re.search(
        r'class="topcard__flavor topcard__flavor--bullet"[^>]*>([\s\S]*?)</span>',
        raw_html,
        re.I,
    )
    location = _clean_inline_html(loc_match.group(1)) if loc_match else None

    desc_html = (
        _extract_div_content(raw_html, "show-more-less-html__markup")
        or _extract_div_content(raw_html, "description__text")
        or ""
    )
    cleaned_desc, guard_findings = run_posting_guard(desc_html, mode="html")

    criteria: Dict[str, str] = {}
    item_re = re.compile(
        r'class="description__job-criteria-subheader"[^>]*>([\s\S]*?)</h3>[\s\S]*?'
        r'class="description__job-criteria-text[^"]*"[^>]*>([\s\S]*?)</span>',
        re.I,
    )
    for cm in item_re.finditer(raw_html):
        criteria[_clean_inline_html(cm.group(1)).lower()] = _clean_inline_html(cm.group(2))

    desc_start = re.search(r'class="(?:show-more-less-html__markup|description__text)', raw_html, re.I)
    topcard = raw_html[:desc_start.start()] if desc_start else raw_html
    is_active = not bool(re.search(r"closed-job__flavor|no longer accepting applications", topcard, re.I))

    canonical_url = f"https://www.linkedin.com/jobs/view/{job_id}"
    header_lines = [
        f"Job Title: {title}",
        f"Company: {company or 'Unknown'}",
        f"Location: {location or 'Unspecified'}",
    ]
    if criteria.get("seniority level"):
        header_lines.append(f"Seniority: {criteria['seniority level']}")
    if criteria.get("employment type"):
        header_lines.append(f"Employment Type: {criteria['employment type']}")
    if criteria.get("job function"):
        header_lines.append(f"Job Function: {criteria['job function']}")
    if criteria.get("industries"):
        header_lines.append(f"Industries: {criteria['industries']}")
    header_lines.append(f"Posting Status: {'ACTIVE' if is_active else 'CLOSED / NO LONGER ACCEPTING APPLICATIONS'}")
    header_lines.append("")
    header_lines.append(cleaned_desc or "(No description text found)")

    security_flags = list(guard_findings.get("security_flags") or [])
    if not is_active:
        security_flags.append("⚠️ Posting Status: LinkedIn indicates this job is CLOSED / no longer accepting applications.")

    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "url": canonical_url,
        "description": cleaned_desc,
        "seniority": criteria.get("seniority level"),
        "employment_type": criteria.get("employment type"),
        "job_function": criteria.get("job function"),
        "industries": criteria.get("industries"),
        "is_active": is_active,
        "raw_text": "\n".join(header_lines),
        "security_flags": security_flags,
        "guard_findings": guard_findings,
    }


def fetch_linkedin_guest_detail(job_id_or_url: str) -> Optional[Dict[str, Any]]:
    """Fetches a single LinkedIn job posting via the unauthenticated jobs-guest API."""
    job_id = normalize_linkedin_job_id(job_id_or_url)
    if not job_id:
        return None
    raw_html = _linkedin_guest_fetch(f"{LINKEDIN_DETAIL_URL}/{job_id}")
    if not raw_html:
        return None
    return parse_linkedin_guest_detail(raw_html, job_id)


def search_linkedin_guest(
    query: str = "",
    location: str = "United States",
    remote: str = "",
    jobage_days: int = 0,
    page: int = 1,
    limit: int = 25,
    evaluated_ids: Optional[set] = None,
    seen_ids: Optional[set] = None,
    max_search_pages: int = 10,
) -> List[Dict[str, Any]]:
    """
    Searches live LinkedIn job postings using the unauthenticated jobs-guest endpoint.
    Pages through search results until `limit` NEW (unevaluated, unseen) postings are
    discovered or `max_search_pages` is reached. Returns all encountered postings
    tagged with their respective status ('evaluated', 'seen', 'new').
    """
    work_type_map = {
        "remote": "2",
        "hybrid": "3",
        "onsite": "1",
        "on-site": "1",
    }
    wt = work_type_map.get((remote or "").strip().lower())
    tpr = f"r{int(jobage_days) * 86400}" if jobage_days and int(jobage_days) > 0 else None

    target_new = max(1, int(limit))
    new_count = 0
    collected: List[Dict[str, Any]] = []
    seen_in_batch = set()
    current_page = max(1, int(page))
    eval_set = evaluated_ids or set()
    seen_set = seen_ids or set()

    for _ in range(max_search_pages):
        params: Dict[str, str] = {}
        if query and query.strip():
            params["keywords"] = query.strip()
        if location and location.strip():
            params["location"] = location.strip()
        if tpr:
            params["f_TPR"] = tpr
        if wt:
            params["f_WT"] = wt
        params["start"] = str((current_page - 1) * 10)

        url = f"{LINKEDIN_SEARCH_URL}?{urlencode(params)}"
        raw_html = _linkedin_guest_fetch(url)
        cards = parse_linkedin_guest_cards(raw_html)
        if not cards:
            break

        for card in cards:
            cid = card["id"]
            if cid not in seen_in_batch:
                seen_in_batch.add(cid)
                if cid in eval_set:
                    status = "evaluated"
                elif cid in seen_set:
                    status = "seen"
                else:
                    status = "new"

                card["status"] = status
                card["is_evaluated"] = (status == "evaluated")
                card["is_seen"] = (status == "seen")
                card["is_new"] = (status == "new")
                collected.append(card)

                if status == "new":
                    new_count += 1
                    if new_count >= target_new:
                        return collected

        if len(cards) < 10:
            break
        current_page += 1
        time.sleep(0.35)

    return collected


def _format_freehire_salary(enrichment: Dict[str, Any]) -> str:
    if not enrichment:
        return ""
    s_min = enrichment.get("salary_min")
    s_max = enrichment.get("salary_max")
    if s_min is None and s_max is None:
        return ""
    cur = f"{enrichment.get('salary_currency')} " if enrichment.get("salary_currency") else ""
    per = f"/{enrichment.get('salary_period')}" if enrichment.get("salary_period") else ""
    if s_min is not None and s_max is not None:
        return f"{cur}{s_min}-{s_max}{per}"
    return f"{cur}{s_min if s_min is not None else s_max}{per}"


def search_freehire_jobs(
    query: str = "",
    work_mode: str = "",
    region: str = "",
    country: str = "",
    seniority: str = "",
    jobage_days: int = 0,
    page: int = 1,
    limit: int = 25,
    evaluated_ids: Optional[set] = None,
    seen_ids: Optional[set] = None,
    max_search_pages: int = 10,
) -> List[Dict[str, Any]]:
    """
    Searches tech job postings via the free, unauthenticated FreeHire REST API
    (https://freehire.me/api/v1/agent/jobs/search).
    Returns full descriptions directly in the search response for instant evaluation.
    Pages through search results until `limit` NEW postings are discovered or
    `max_search_pages` is reached. Returns all encountered postings tagged with
    their respective status ('evaluated', 'seen', 'new').
    """
    base_url = FREEHIRE_BASE_URL.rstrip("/")
    target_new = max(1, int(limit))
    page_size = min(50, max(1, int(limit)))
    current_offset = max(0, (page - 1) * limit)
    new_count = 0
    collected: List[Dict[str, Any]] = []
    seen_in_batch = set()
    eval_set = evaluated_ids or set()
    seen_set = seen_ids or set()

    for _ in range(max_search_pages):
        params: List[Tuple[str, str]] = []
        if query and query.strip():
            params.append(("q", query.strip()))
        params.append(("limit", str(page_size)))
        params.append(("offset", str(current_offset)))
        params.append(("description_format", "text"))

        if jobage_days and int(jobage_days) > 0:
            params.append(("posted_within_days", str(int(jobage_days))))
        if work_mode and work_mode.strip().lower() in ("remote", "hybrid", "onsite"):
            params.append(("work_mode", work_mode.strip().lower()))
        if region and region.strip().lower() in FREEHIRE_REGION_VALUES:
            params.append(("regions", region.strip().lower()))
        if country and country.strip():
            params.append(("countries", country.strip().upper()))
        if seniority and seniority.strip().lower() not in ("", "any"):
            params.append(("seniority", seniority.strip().lower()))

        url = f"{base_url}{FREEHIRE_AGENT_SEARCH_PATH}?{urlencode(params)}"
        headers = {
            "User-Agent": "SkippyJobSearch/1.0 (freehire-search)",
            "Accept": "application/json",
        }

        delay = 0.5
        payload = None
        for attempt in range(4):
            resp = _http_get(url, headers=headers, timeout=15)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == 3:
                    raise RuntimeError(f"FreeHire API rate-limited or unavailable (HTTP {resp.status_code}).")
                time.sleep(delay + random.uniform(0.0, 0.3))
                delay = min(delay * 2, 5.0)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break

        if not payload or not isinstance(payload, dict):
            break

        raw_jobs = payload.get("data") or []
        if not raw_jobs:
            break

        for item in raw_jobs:
            if not isinstance(item, dict):
                continue
            title = html.unescape(item.get("title") or "").strip() or "(Untitled Role)"
            company = (item.get("company") or "Unknown Company").strip()
            location = (item.get("location") or "").strip()
            posted_at = (item.get("posted_at") or "")[:10]
            job_url = (item.get("url") or "").strip()
            slug = (item.get("public_slug") or "").strip()
            if not job_url and slug:
                job_url = f"{base_url}/jobs/{slug}"

            norm_url = job_url.split("?")[0].split("#")[0].rstrip("/").lower() if job_url else ""
            job_key = slug or norm_url or title

            if job_key in seen_in_batch:
                continue
            seen_in_batch.add(job_key)

            if job_key in eval_set or norm_url in eval_set:
                status = "evaluated"
            elif job_key in seen_set or norm_url in seen_set:
                status = "seen"
            else:
                status = "new"

            enrichment = item.get("enrichment") or {}
            salary_str = _format_freehire_salary(enrichment)
            sen = enrichment.get("seniority") or ""
            emp_type = enrichment.get("employment_type") or ""
            w_mode = item.get("work_mode") or ""
            skills_list = item.get("skills") or []

            raw_desc = item.get("description") or ""
            cleaned_desc, guard_findings = run_posting_guard(raw_desc, mode="auto")
            security_flags = list(guard_findings.get("security_flags") or [])

            reality = item.get("reality") or {}
            if item.get("closed_at"):
                security_flags.append("⚠️ Posting Status: FreeHire indicates this job listing is CLOSED.")
            elif reality.get("fake_freshness"):
                repost_cnt = reality.get("repost_count", 1)
                security_flags.append(
                    f"⚠️ Repost / Ghost Job Notice: Flagged for fake freshness (reposted {repost_cnt} times)."
                )

            header_lines = [
                f"Job Title: {title}",
                f"Company: {company}",
                f"Location: {location or 'Unspecified'}",
            ]
            if w_mode:
                header_lines.append(f"Workplace Mode: {w_mode}")
            if sen:
                header_lines.append(f"Seniority: {sen}")
            if emp_type:
                header_lines.append(f"Employment Type: {emp_type}")
            if salary_str:
                header_lines.append(f"Salary: {salary_str}")
            if skills_list:
                header_lines.append(f"Listed Skills: {', '.join(str(s) for s in skills_list)}")
            header_lines.append("")
            header_lines.append(cleaned_desc or "(No description text provided)")

            collected.append({
                "id": slug or job_url,
                "title": title,
                "company": company,
                "location": location,
                "date": posted_at,
                "url": job_url,
                "work_mode": w_mode,
                "seniority": sen,
                "salary": salary_str,
                "skills": skills_list,
                "description": cleaned_desc,
                "raw_text": "\n".join(header_lines),
                "security_flags": security_flags,
                "source_board": "FreeHire",
                "status": status,
                "is_evaluated": (status == "evaluated"),
                "is_seen": (status == "seen"),
                "is_new": (status == "new"),
            })

            if status == "new":
                new_count += 1
                if new_count >= target_new:
                    return collected

        if len(raw_jobs) < page_size:
            break
        current_offset += len(raw_jobs)
        time.sleep(0.35)

    return collected


def _extract_guarded_text_from_html(html_content: str) -> Tuple[str, List[str]]:
    """
    Removes structural navigation chrome (<script>, <style>, <nav>, <footer>, <header>, <aside>),
    then runs Posting Guard's deterministic HTML cleaner to strip hidden CSS elements and
    invisible Unicode characters while scanning for prompt-injection lines.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.extract()
    cleaned_text, findings = run_posting_guard(str(soup), mode="html")
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    return "\n".join(lines), list(findings.get("security_flags") or [])


def scrape_job_with_guard(url: str, page: Page = None) -> Tuple[str, List[str]]:
    """
    Scrapes a job URL and returns (cleaned_text, security_flags).
    Automatically routes LinkedIn job URLs to the unauthenticated LinkedIn Guest API,
    and runs Posting Guard on all scraped HTML.
    """
    if not is_safe_url(url):
        return f"Error: Disallowed or unsafe URL ({url}). Only public HTTP/HTTPS URLs are allowed.", []

    # 0. FAST PATH: LinkedIn Public Guest Detail API (bypasses login wall)
    linkedin_id = normalize_linkedin_job_id(url)
    if linkedin_id:
        try:
            detail = fetch_linkedin_guest_detail(linkedin_id)
            if detail and detail.get("description"):
                return detail["raw_text"], detail.get("security_flags", [])
        except Exception:
            pass  # Fall through to standard scraper if guest endpoint fails

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # 1. OPTIMIZED BATCH MODE: If an active Playwright page is passed, use it directly
    if page:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            current_url = getattr(page, "url", None)
            if isinstance(current_url, str) and current_url and not is_safe_url(current_url):
                return f"Error: URL redirected to a disallowed address: {current_url}", []
            html_content = page.content()
            return _extract_guarded_text_from_html(html_content)
        except Exception as e:
            return f"Error scraping URL via persistent browser context: {str(e)}", []

    # 2. STANDARD / MANUAL MODE: Attempt fast static fetch first with per-hop SSRF validation & size cap
    try:
        current_target = url
        response = None
        for _hop in range(6):
            if not is_safe_url(current_target):
                return f"Error: URL redirected to a disallowed address: {current_target}", []
            resp = _http_get(current_target, headers=headers, timeout=8, allow_redirects=False)
            if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                current_target = urljoin(current_target, resp.headers["Location"])
                continue
            response = resp
            break

        if response is not None:
            # Also validate any history/final URL if underlying transport followed redirects
            for hist_resp in getattr(response, "history", []) or []:
                hist_url = getattr(hist_resp, "url", "")
                if hist_url and not is_safe_url(hist_url):
                    return f"Error: URL redirected through a disallowed address: {hist_url}", []
            if getattr(response, "url", "") and not is_safe_url(response.url):
                return f"Error: URL redirected to a disallowed address: {response.url}", []

            content_type = (getattr(response, "headers", {}) or {}).get("Content-Type", "").lower()
            if any(content_type.startswith(prefix) for prefix in _BLOCKED_CONTENT_PREFIXES):
                return f"Error: Unsupported binary Content-Type ({content_type}).", []

            if response.status_code == 200:
                raw_body = (response.text or "")[:MAX_RESPONSE_BYTES]
                cleaned_text, sec_flags = _extract_guarded_text_from_html(raw_body)
                if len(cleaned_text) > 300:
                    return cleaned_text, sec_flags
    except Exception:
        pass

    # 3. MANUAL MODE FALLBACK: Spin up a temporary headless browser
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            temp_page = browser.new_page(user_agent=headers["User-Agent"])
            temp_page.goto(url, wait_until="domcontentloaded", timeout=15000)
            current_url = getattr(temp_page, "url", None)
            if isinstance(current_url, str) and current_url and not is_safe_url(current_url):
                browser.close()
                return f"Error: URL redirected to a disallowed address: {current_url}", []
            html_content = temp_page.content()
            browser.close()

            return _extract_guarded_text_from_html(html_content)
    except Exception as e:
        return f"Error scraping URL via temporary browser: {str(e)}", []


def scrape_job_text(url: str, page: Page = None) -> str:
    """Robust scraper using requests with a Playwright fallback. Enforces SSRF, scheme validation, and Posting Guard."""
    cleaned_text, _ = scrape_job_with_guard(url, page=page)
    return cleaned_text


def _log_scraper_error(message: str):
    """Outputs an error cleanly to Streamlit UI if in a request context, otherwise prints."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is not None:
            st.error(message)
            return
    except Exception:
        pass
    print(f"[Scraper Error] {message}")


def scrape_universal_search_results(search_url: str) -> list[str]:
    """Attempts to auto-discover job links from ANY job board search page with URL validation."""
    if not is_safe_url(search_url):
        _log_scraper_error(f"Disallowed or unsafe search URL: {search_url}")
        return []

    job_urls = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            # Tell Playwright not to wait for background analytics/ads
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            
            # Wait specifically for links to appear
            page.wait_for_selector("a", timeout=10000)
            
            all_links = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            valid_keywords = [
                '/job/', '/jobs/', '/careers/', '/posting/', '/position/',
                'reqid=', '/role/', '/opening/', '/openings/', '/opportunity/',
                '/opportunities/', '/remote-jobs/', '/remote-job/'
            ]
            
            for link in all_links:
                if any(keyword in link.lower() for keyword in valid_keywords):
                    if is_safe_url(link):
                        job_urls.append(link)
                    
            job_urls = list(dict.fromkeys(job_urls))
            browser.close()
    except Exception as e:
        _log_scraper_error(f"Error scraping search page: {str(e)}")
        
    return job_urls
