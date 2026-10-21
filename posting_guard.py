"""Deterministic integrity gate for fetched or pasted job postings.

Cleans and scans untrusted job descriptions before they touch an LLM:
  1. Hidden HTML (display:none, visibility:hidden, opacity:0, font-size:0,
     color:transparent, clip/clip-path, off-screen positioning, `hidden`,
     `aria-hidden="true"`, comments, script/style/noscript/svg/template)
     is deterministically stripped from the text while its contents are
     still scanned for hidden prompt-injection instructions.
  2. Invisible Unicode characters (zero-width spaces, bidirectional controls
     and overrides, soft hyphens, BOM) are stripped and counted; tampering
     patterns (zero-width chars inside words or bidi overrides/isolates)
     are flagged.
  3. Instruction-shaped prompt-injection lines aimed at hijacking the AI
     evaluator are detected and quoted.
  4. Words mixing Latin with Cyrillic or Greek letters (homoglyph spoofing)
     are detected and listed.
"""

import html
import re
from typing import Tuple, Dict, Any, List

EXCERPT = 120
LINE_MAX = 200

ZERO_WIDTH = "\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064"
BIDI = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
BIDI_TAMPER = "\u202d\u202e\u2066\u2067\u2068\u2069"  # overrides and isolates
FORMAT = "\u00ad\u2028\u2029"  # soft hyphen, line/paragraph separators
BOM = "\ufeff"
INVISIBLE = ZERO_WIDTH + BIDI + FORMAT + BOM

HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none"
    r"|visibility\s*:\s*hidden"
    r"|opacity\s*:\s*0(?![.\d]*[1-9])"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?(?![\d.])"
    r"|font-size\s*:\s*1px(?=[^;]*line-height\s*:\s*0)"
    r"|color\s*:\s*transparent"
    r"|clip\s*:\s*rect\(\s*0"
    r"|clip-path\s*:\s*inset\(\s*100%"
    r"|transform\s*:\s*scale\(\s*0(?:\.0+)?\s*\)"
    r"|max-(?:height|width)\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?(?![\d.])"
    r"|(?:left|top|text-indent)\s*:\s*-\d{4,}px",
    re.I,
)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
PRESTRIP = re.compile(r"<!DOCTYPE[^>]*>|<\?[^>]*\?>", re.I)
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
DROP_BLOCKS = re.compile(r"<(script|style|noscript|svg|template)\b[^>]*>.*?(?:</\1\s*>|\Z)", re.I | re.S)
TAG = re.compile(r"<(/?)([a-zA-Z][\w:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
ATTR = re.compile(r"([^\s=/\"'>]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>\"']+)))?")
VOID = {"br", "img", "input", "meta", "link", "hr", "wbr", "source", "area", "base", "col", "embed", "param", "track"}
BLOCK = {
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "section", "article",
    "header", "footer", "table", "thead", "tbody", "blockquote", "pre", "dd", "dt", "dl", "nav", "main",
    "aside", "figure", "form", "fieldset", "legend", "address", "hr", "td", "th", "option"
}
IMPLIED_END = {"p", "li", "dd", "dt", "tr", "td", "th", "option"}
CLOSES_P = BLOCK - {"br"}
HTML_HINT = re.compile(r"<\s*(html|body|div|p|span|section|article|ul|li|h[1-6])\b", re.I)

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")

INSTRUCTION_PATTERNS = [re.compile(p, re.I) for p in (
    r"\b(?:ignore|disregard|forget)\s+(?:all|any|the|previous|prior|above|earlier)\s*(?:instructions?|rules?|prompts?|directions?|constraints?)?\b",
    r"\byou are (?:an?|the) (?:ai(?![\w-])|ai (?:assistant|agent|model|language model|evaluator)|assistant|llm|language model)\b",
    r"\bsystem prompt\b",
    r"\bdo not (?:tell|inform|mention)(?: this)? to the user\b",
    r"\b(?:run|execute) the following (?:command|commands|script|code|shell|instruction|instructions|steps)\b",
    r"\bas an ai(?![\w-])",
    r"^\s*(?:assistant|system|user)\s*:",
    r"<\|(?:im_start|im_end|system|user|assistant|endoftext)\|?>",
    r"\[INST\]|\[/INST\]",
    r"###\s*(?:system|instruction)",
    r"\b(?:match_score|is_eligible)\s*[:=]\s*(?:100|true)\b",
    r"\b(?:give|assign|rate|score)\s+(?:this\s+)?(?:candidate|resume|applicant|job)\s+(?:a\s+)?(?:100|perfect|maximum)\b",
)]

WORD = re.compile(r"\w+", re.UNICODE)
LATIN = re.compile(r"[A-Za-z]")
CONFUSABLE = re.compile(r"[\u0400-\u04ff\u0370-\u03ff]")  # Cyrillic and Greek


def _fold(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\xa0\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> Tuple[str, Dict[str, Any]]:
    """Remove invisible characters and count tampering signals."""
    if not text:
        return "", {"invisible_chars": {}, "invisible_flagged": 0}

    counts = {}
    flagged = 0
    for key, chars in (("zero_width", ZERO_WIDTH), ("bidi", BIDI), ("format", FORMAT), ("bom", BOM)):
        n = sum(text.count(c) for c in chars)
        if n:
            counts[key] = n

    for i, ch in enumerate(text):
        if ch in BIDI_TAMPER:
            flagged += 1
        elif ch in ZERO_WIDTH or ch == BOM:
            before = text[i - 1] if i else ""
            after = text[i + 1] if i + 1 < len(text) else ""
            if before.isalpha() and after.isalpha():
                flagged += 1

    cleaned = text.translate({ord(c): None for c in INVISIBLE})
    return _fold(cleaned), {"invisible_chars": counts, "invisible_flagged": flagged}


def _attrs(raw: str) -> Dict[str, str]:
    out = {}
    for m in ATTR.finditer(raw):
        value = m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None else (m.group(4) or "")
        out[m.group(1).lower()] = value
    return out


def _is_hidden(raw_attrs: str) -> bool:
    attrs = _attrs(raw_attrs)
    if "hidden" in attrs or attrs.get("aria-hidden", "").strip().lower() == "true":
        return True
    raw_style = html.unescape(attrs.get("style", ""))
    normalized_style = CSS_COMMENT.sub("", raw_style)
    return bool(HIDDEN_STYLE.search(normalized_style))


def clean_html(markup: str) -> Tuple[str, Dict[str, Any]]:
    """Extract visible text from HTML while removing and recording hidden elements."""
    if not markup:
        return "", {"hidden_blocks": [], "hidden_text": ""}

    hidden_parts: List[str] = []
    hidden_blocks: List[str] = []

    def collect(match):
        inner = re.sub(r"<!--|-->", " ", match.group(0))
        inner = re.sub(r"<[^>]+>", " ", inner)
        hidden_parts.append(html.unescape(inner))
        return " "

    markup = PRESTRIP.sub(" ", markup)
    markup = COMMENT.sub(collect, markup)
    markup = DROP_BLOCKS.sub(collect, markup)

    visible: List[str] = []
    hidden_buf: List[str] = []
    stack: List[str] = []
    hidden_at = None
    pos = 0

    def emit(text_chunk: str):
        (visible if hidden_at is None else hidden_buf).append(text_chunk)

    def flush_hidden():
        nonlocal hidden_at
        block = _fold(html.unescape("".join(hidden_buf)))
        hidden_buf.clear()
        hidden_at = None
        if block:
            hidden_blocks.append(block[:EXCERPT])
            hidden_parts.append(block)

    def pop_to(index: int):
        del stack[index:]
        if hidden_at is not None and hidden_at >= len(stack):
            flush_hidden()

    def last_index(name: str):
        for i in range(len(stack) - 1, -1, -1):
            if stack[i] == name:
                return i
        return None

    for m in TAG.finditer(markup):
        emit(markup[pos:m.start()])
        pos = m.end()
        closing, name, raw_attrs = m.group(1), m.group(2).lower(), m.group(3)
        if name in BLOCK:
            emit("\n")
        if closing:
            index = last_index(name)
            if index is not None:
                pop_to(index)
            continue
        if name in VOID:
            continue
        if name in IMPLIED_END and stack and stack[-1] == name:
            pop_to(len(stack) - 1)
        elif name in CLOSES_P and stack and stack[-1] == "p":
            pop_to(len(stack) - 1)
        stack.append(name)
        if hidden_at is None and _is_hidden(raw_attrs):
            hidden_at = len(stack) - 1

    emit(markup[pos:])
    if hidden_at is not None:
        flush_hidden()

    text = html.unescape("".join(visible))
    return _fold(text), {"hidden_blocks": hidden_blocks, "hidden_text": "\n".join(hidden_parts)}


def _excerpt(line: str, at: int) -> str:
    if len(line) <= LINE_MAX:
        return line
    lead = LINE_MAX // 3
    start = max(0, at - lead)
    end = min(len(line), start + LINE_MAX)
    start = max(0, end - LINE_MAX)
    head = "\u2026" if start else ""
    tail = "\u2026" if end < len(line) else ""
    return f"{head}{line[start:end]}{tail}"


def scan(visible: str, hidden: str = "") -> Dict[str, Any]:
    """Scan visible and removed hidden text for prompt-injection and homoglyphs."""
    seen = set()
    instruction_like: List[str] = []
    for line in (visible or "").splitlines() + (hidden or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        match = next((m for m in (p.search(stripped) for p in INSTRUCTION_PATTERNS) if m), None)
        if match:
            seen.add(stripped)
            instruction_like.append(_excerpt(stripped, match.start()))

    hidden_urls: List[str] = []
    for u in URL_RE.findall(hidden or ""):
        if u not in hidden_urls:
            hidden_urls.append(u)

    homoglyphs: List[str] = []
    for word in WORD.findall((visible or "") + "\n" + (hidden or "")):
        if LATIN.search(word) and CONFUSABLE.search(word) and word not in homoglyphs:
            homoglyphs.append(word)

    return {
        "instruction_like": instruction_like,
        "hidden_urls": hidden_urls,
        "visible_url_count": len(URL_RE.findall(visible or "")),
        "homoglyph_runs": homoglyphs,
    }


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def verdict(findings: Dict[str, Any]) -> str:
    alarms = []
    n = len(findings.get("instruction_like") or [])
    if n:
        alarms.append(_plural(n, "instruction-like line", "instruction-like lines"))
    n = int(findings.get("invisible_flagged") or 0)
    if n:
        alarms.append(_plural(n, "invisible character inside words", "invisible characters inside words"))
    n = len(findings.get("homoglyph_runs") or [])
    if n:
        alarms.append(_plural(n, "mixed-script word", "mixed-script words"))

    context = []
    n = len(findings.get("hidden_blocks") or [])
    if n:
        context.append(_plural(n, "hidden block", "hidden blocks"))
    n = len(findings.get("hidden_urls") or [])
    if n:
        context.append(_plural(n, "hidden URL", "hidden URLs"))
    removed = " and ".join(context)

    if alarms:
        line = "posting_guard: ⚠ " + ", ".join(alarms) + " - review before continuing"
        return f"{line} ({removed} removed)" if removed else line
    if removed:
        return f"posting_guard: clean ({removed} removed, none instruction-like)"
    return "posting_guard: clean"


def format_security_flags(findings: Dict[str, Any]) -> List[str]:
    """Convert suspicious findings into human-readable Red Flag strings for Skippy's UI."""
    flags: List[str] = []
    if not findings:
        return flags

    instr = findings.get("instruction_like") or []
    if instr:
        sample = instr[0][:100]
        flags.append(
            f"🛡️ Security Alert (Prompt Injection): Detected {_plural(len(instr), 'instruction-shaped line', 'instruction-shaped lines')} "
            f"in posting (e.g., \"{sample}\"). Hidden/malicious instructions were neutralized."
        )

    inv_flagged = int(findings.get("invisible_flagged") or 0)
    if inv_flagged:
        flags.append(
            f"🛡️ Security Alert (Unicode Tampering): Stripped {_plural(inv_flagged, 'invisible character', 'invisible characters')} "
            f"embedded inside words or bidirectional text overrides."
        )

    homoglyphs = findings.get("homoglyph_runs") or []
    if homoglyphs:
        sample_words = ", ".join(homoglyphs[:3])
        flags.append(
            f"🛡️ Security Alert (Homoglyph Spoofing): Detected {_plural(len(homoglyphs), 'mixed-script word', 'mixed-script words')} "
            f"combining Latin and Cyrillic/Greek characters ({sample_words})."
        )

    return flags


def guard(raw: str, mode: str = "auto") -> Tuple[str, Dict[str, Any]]:
    """Run the full integrity gate on HTML or plain text.

    Args:
        raw: Raw HTML markup or plain text.
        mode: "html", "text", or "auto".

    Returns:
        (cleaned_text, findings_dict)
    """
    if not raw or not isinstance(raw, str):
        empty_findings = {
            "hidden_blocks": [],
            "invisible_chars": {},
            "invisible_flagged": 0,
            "instruction_like": [],
            "hidden_urls": [],
            "visible_url_count": 0,
            "homoglyph_runs": [],
            "verdict": "posting_guard: clean",
            "security_flags": [],
        }
        return "", empty_findings

    if mode == "auto":
        mode = "html" if HTML_HINT.search(raw) else "text"

    if mode == "html":
        text, hf = clean_html(raw)
        hidden_text, hidden_blocks = hf["hidden_text"], hf["hidden_blocks"]
    else:
        text, hidden_text, hidden_blocks = raw, "", []

    text, tf = clean_text(text)
    hidden_text, _ = clean_text(hidden_text)
    findings = {"hidden_blocks": hidden_blocks, **tf, **scan(text, hidden_text)}
    findings["verdict"] = verdict(findings)
    findings["security_flags"] = format_security_flags(findings)
    return text, findings
