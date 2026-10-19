let lastClickedElement = null;
document.addEventListener("contextmenu", (e) => {
    lastClickedElement = e.target;
}, true);
document.addEventListener("click", (e) => {
    lastClickedElement = e.target;
}, true);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "scrape_clicked_job") {
        try {
            const extractTitleFromText = (raw, comp = "") => {
                if (!raw) return null;
                let clean = raw.replace(/^\(\d+\)\s*/, '').replace(/\s*\|\s*LinkedIn.*$/i, '').trim();

                // 1. "... hiring <Title> in <Location>" or "... hires <Title> in ..."
                const hiringMatch = clean.match(/(?:hiring|hires)\s+(.+?)(?:\s+in\s+[^\n|]+|\s*$)/i);
                if (hiringMatch && hiringMatch[1].trim()) {
                    return hiringMatch[1].trim();
                }

                // 2. "<Title> at <Company>"
                const atMatch = clean.match(/^(.+?)\s+at\s+/i);
                if (atMatch && atMatch[1].trim()) {
                    return atMatch[1].trim();
                }

                // 3. "<Title> | <Company>"
                if (clean.includes(' | ')) {
                    const parts = clean.split(' | ').map(s => s.trim()).filter(Boolean);
                    if (parts.length > 0 && parts[0].toLowerCase() !== (comp || "").toLowerCase()) {
                        return parts[0];
                    }
                }

                // 4. "<Title> - <Company>"
                if (clean.includes(' - ')) {
                    const parts = clean.split(' - ').map(s => s.trim()).filter(Boolean);
                    if (parts.length > 0 && parts[0].toLowerCase() !== (comp || "").toLowerCase()) {
                        return parts[0];
                    }
                }

                return (clean && clean.toLowerCase() !== "linkedin") ? clean : null;
            };

            const extractCompanyFromText = (raw) => {
                if (!raw) return null;
                let clean = raw.replace(/^\(\d+\)\s*/, '').replace(/\s*\|\s*LinkedIn.*$/i, '').trim();

                const hiringMatch = clean.match(/^(.+?)\s+(?:hiring|hires)\b/i);
                if (hiringMatch && hiringMatch[1].trim()) {
                    return hiringMatch[1].trim();
                }

                const atMatch = clean.match(/\bat\s+([^|\-]+)/i);
                if (atMatch && atMatch[1].trim()) {
                    return atMatch[1].trim();
                }

                if (clean.includes(' | ')) {
                    const parts = clean.split(' | ').map(s => s.trim()).filter(Boolean);
                    if (parts.length > 1) return parts[1];
                }

                return null;
            };

            const getDetailsPane = () => {
                return document.querySelector('.scaffold-layout__detail') ||
                       document.querySelector('.jobs-search__job-details') ||
                       document.querySelector('.job-view-layout') ||
                       document.querySelector('.jobs-details') ||
                       document.querySelector('.jobs-search-two-pane__details') ||
                       document.querySelector('main') ||
                       document;
            };

            const getCompany = () => {
                const pane = getDetailsPane();
                const selectors = [
                    '.job-details-jobs-unified-top-card__company-name',
                    '.jobs-unified-top-card__company-name',
                    '.job-details-jobs-unified-top-card__primary-description-container a[href*="/company/"]',
                    'a.topcard__org-name-link',
                    '[data-tracking-control-name="public_jobs_topcard-org-name"]',
                    '.topcard__flavor--black-link',
                    'a[href*="/company/"]',
                    '[aria-label^="Company,"]'
                ];
                for (const sel of selectors) {
                    const el = pane.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        return el.innerText.trim();
                    }
                }
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        return el.innerText.trim();
                    }
                }

                // Check JSON-LD
                try {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const s of scripts) {
                        const data = JSON.parse(s.innerText);
                        const comp = data?.hiringOrganization?.name;
                        if (comp && typeof comp === 'string' && comp.trim()) {
                            return comp.trim();
                        }
                    }
                } catch (e) {}

                // Check meta & title
                const metaTitle = document.querySelector('meta[property="og:title"]')?.content || document.title;
                const fromTitle = extractCompanyFromText(metaTitle);
                if (fromTitle) return fromTitle;

                return "Unknown Company";
            };

            const getTitle = (company = "") => {
                const pane = getDetailsPane();

                // 1. Detailed selectors within the details pane
                const paneSelectors = [
                    '.job-details-jobs-unified-top-card__job-title h1',
                    '.job-details-jobs-unified-top-card__job-title h2',
                    '.job-details-jobs-unified-top-card__job-title a',
                    '.job-details-jobs-unified-top-card__job-title',
                    '.jobs-unified-top-card__job-title h1',
                    '.jobs-unified-top-card__job-title h2',
                    '.jobs-unified-top-card__job-title a',
                    '.jobs-unified-top-card__job-title',
                    'h1.top-card-layout__title',
                    'h2.top-card-layout__title',
                    'h1.topcard__title',
                    'h1.t-24',
                    'h2.t-24',
                    '.jobs-details__main-content h1',
                    '.jobs-details__main-content h2',
                    '[class*="job-details"] h1',
                    '[class*="job-details"] h2',
                    '[class*="top-card__job-title"]',
                    '[class*="topcard__title"]',
                    '.scaffold-layout__detail a[href*="/jobs/view/"]',
                    '.jobs-search__job-details a[href*="/jobs/view/"]'
                ];

                for (const sel of paneSelectors) {
                    const el = pane.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        const candidate = el.innerText.replace(/\s+/g, ' ').trim();
                        if (!candidate.toLowerCase().includes("search results") && 
                            candidate.toLowerCase() !== (company || "").toLowerCase()) {
                            return candidate;
                        }
                    }
                }

                // 2. Check JSON-LD
                try {
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const s of scripts) {
                        const data = JSON.parse(s.innerText);
                        if (data && (data['@type'] === 'JobPosting' || data.title)) {
                            if (data.title && typeof data.title === 'string' && data.title.trim()) {
                                return data.title.trim();
                            }
                        }
                    }
                } catch (e) {}

                // 3. OpenGraph / Twitter meta tags
                const ogTitle = document.querySelector('meta[property="og:title"]')?.content ||
                                document.querySelector('meta[name="twitter:title"]')?.content;
                if (ogTitle) {
                    const fromOg = extractTitleFromText(ogTitle, company);
                    if (fromOg && fromOg.toLowerCase() !== "unknown title") {
                        return fromOg;
                    }
                }

                // 4. document.title fallback
                if (document.title) {
                    const fromDoc = extractTitleFromText(document.title, company);
                    if (fromDoc && fromDoc.toLowerCase() !== "unknown title") {
                        return fromDoc;
                    }
                }

                // 5. Broader document-wide fallback
                const docSelectors = [
                    'h1.top-card-layout__title',
                    'h1.topcard__title',
                    'h1.t-24',
                    'h2.top-card-layout__title',
                    'h3.sub-nav-cta__header',
                    'a[href*="/jobs/view/"]'
                ];
                for (const sel of docSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 0) {
                        const candidate = el.innerText.replace(/\s+/g, ' ').trim();
                        if (!candidate.toLowerCase().includes("search results") && 
                            candidate.toLowerCase() !== (company || "").toLowerCase()) {
                            return candidate;
                        }
                    }
                }

                return "Unknown Title";
            };

            const getDesc = () => {
                const pane = getDetailsPane();

                // 1. Expand the description if button exists
                const expandButtons = [
                    '#job-details button',
                    'button[aria-label*="Show more" i]',
                    'button[aria-label*="see more" i]',
                    'button[aria-label*="expand" i]',
                    'button.jobs-description__footer-button',
                    '[data-testid="expandable-text-button"]',
                    'button[data-tracking-control-name="public_jobs_show-more-html-btn"]',
                    'button.show-more-less-html__button',
                    '.jobs-description button'
                ];
                for (const sel of expandButtons) {
                    const btn = pane.querySelector(sel) || document.querySelector(sel);
                    if (btn && typeof btn.click === 'function') {
                        try { btn.click(); } catch (e) {}
                        break;
                    }
                }

                // 2. Extract description from candidate containers
                const descSelectors = [
                    '#job-details',
                    '.jobs-description__content',
                    '.jobs-box__html-content',
                    '.jobs-description-content__text',
                    '.show-more-less-html__markup',
                    '[id^="JobDetails_AboutTheJob"]',
                    '[data-testid="expandable-text-box"]',
                    'article.jobs-description__container',
                    '.jobs-description',
                    '.description__text'
                ];
                for (const sel of descSelectors) {
                    const el = pane.querySelector(sel) || document.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim().length > 50) {
                        return el.innerText.trim();
                    }
                }

                if (pane && pane !== document && pane.innerText && pane.innerText.trim().length > 100) {
                    return pane.innerText.trim();
                }
                return "";
            };

            const getJobUrl = () => {
                const urlParams = new URLSearchParams(window.location.search);
                const currentJobId = urlParams.get('currentJobId');
                if (currentJobId) {
                    return `https://www.linkedin.com/jobs/view/${currentJobId}/`;
                }

                const match = window.location.pathname.match(/\/jobs\/view\/(\d+)/);
                if (match) {
                    return `https://www.linkedin.com/jobs/view/${match[1]}/`;
                }

                const pane = getDetailsPane();
                const activeJobLink = pane.querySelector('a[href*="/jobs/view/"]');
                if (activeJobLink && activeJobLink.href) {
                    const linkMatch = activeJobLink.href.match(/\/jobs\/view\/(\d+)/);
                    if (linkMatch) {
                        return `https://www.linkedin.com/jobs/view/${linkMatch[1]}/`;
                    }
                }

                return window.location.href.split('?')[0];
            };

            const company = getCompany();
            const title = getTitle(company);
            const description = getDesc();

            if (!description || description.length < 50) {
                alert("⚠️ Skippy: Could not find job description text. Ensure the right-hand panel is loaded.");
                return;
            }

            const jobUrl = getJobUrl();

            const payload = {
                source: "linkedin_extension",
                url: jobUrl,
                title: title.replace(/\s+/g, ' ').trim(),
                company: company.replace(/\s+/g, ' ').trim(),
                raw_text: description
            };

            let toast = document.createElement("div");
            toast.innerText = "⏳ Sending to Skippy...";
            toast.style.cssText = "position:fixed; bottom:24px; right:24px; background:#0a66c2; color:white; padding:12px 24px; border-radius:8px; z-index:999999; font-weight:bold; font-family:sans-serif; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: opacity 0.3s;";
            document.body.appendChild(toast);

            chrome.runtime.sendMessage({ action: "sendToSkippy", payload: payload }, (response) => {
                if (chrome.runtime.lastError) {
                    toast.innerText = "❌ Failed: Extension Error";
                    toast.style.background = "#cc1016";
                } else if (response && response.success) {
                    toast.innerText = `✅ In Inbox: "${title}"`;
                    toast.style.background = "#057642"; 
                } else {
                    const errMsg = (response && response.error) ? response.error : "Is Skippy running?";
                    toast.innerText = `❌ Failed: ${errMsg}`;
                    toast.style.background = "#cc1016";
                }
                setTimeout(() => toast.remove(), 4000);
            });

        } catch (error) {
            alert("❌ Skippy Script Error: " + error.message);
        }
    }
});
