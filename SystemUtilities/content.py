"""Smart document classification: decide from the file name whenever possible, ask AI about names the rules
don't know, and read a short text excerpt only from files whose names say nothing.

Only document files stored on this PC are considered - images, videos, installers, archives and code are ignored,
and online-only (cloud) files are never opened because that would download them.
"""

import html
import json
import os
import re
import zipfile

import quickclean

DOC_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx", ".ppt", ".txt", ".md", ".rtf", ".odt"}
LEGACY = {".doc", ".xls", ".ppt"}            # binary formats we can't read without extra software
CLOUD_ONLY = 0x00400000 | 0x00001000
SNIPPET_CHARS = 1500
CACHE_PATH = os.path.join(quickclean.LOCAL, "StorageAnalyzer", "content_cache.json")

CATEGORIES = {   # key: (label, folder it would move to)
    "bills": ("Bills & invoices", "Bills & Invoices"),
    "kyc": ("KYC & identity", "KYC & Identity"),
    "bank": ("Bank & tax", "Bank & Tax"),
    "insurance": ("Insurance & medical", "Insurance & Medical"),
    "work": ("Work & career", "Work"),
    "education": ("Education & certificates", "Education"),
    "property": ("Property & legal", "Property & Legal"),
    "travel": ("Travel & tickets", "Travel"),
    "manuals": ("Manuals & guides", "Manuals & Guides"),
    "personal": ("Personal", "Personal"),
    "other": ("Other documents", "Other Documents"),
}
CATEGORY_HELP = ", ".join(f"{k} = {v[0]}" for k, v in CATEGORIES.items())

# First match wins, so the order matters (e.g. "birth certificate" must hit KYC before Education).
NAME_RULES = [
    ("kyc", r"aadh?aar|pan[\s_-]?card|\bpan\b|passport|voter|driving[\s_-]?licen[cs]e|birth|kyc|national[\s_-]?id|"
            r"ration[\s_-]?card|death[\s_-]?certificate|marriage[\s_-]?certificate|\be-?kyc\b"),
    ("bills", r"\bbills?\b|invoice|receipt|airtel|\bjio\b|vodafone|\bbsnl\b|electricity|bescom|tneb|msedcl|\bgas\b|"
              r"water[\s_-]?bill|broadband|recharge|postpaid|prepaid|order[\s_-]?(summary|details)|payment[\s_-]?confirm"),
    ("bank", r"statement|salary[\s_-]?slip|pay[\s_-]?slip|payslip|form[\s_-]?16|\bitr\b|income[\s_-]?tax|\btax\b|\bgst\b|"
             r"\btds\b|26as|\bepf\b|\bpf\b|mutual[\s_-]?fund|demat|cheque|\bloan\b|\bemi\b|credit[\s_-]?card|bank"),
    ("insurance", r"insurance|policy|premium|claim|prescription|lab[\s_-]?report|medical|hospital|discharge|"
                  r"diagnos|vaccin|covid|health"),
    ("work", r"resume|\bcv\b|curriculum|offer[\s_-]?letter|appointment[\s_-]?letter|relieving|experience[\s_-]?letter|"
             r"appraisal|timesheet|cover[\s_-]?letter|joining|employment|\bnda\b"),
    ("education", r"marksheet|mark[\s_-]?sheet|degree|transcript|certificate|diploma|admit[\s_-]?card|hall[\s_-]?ticket|"
                  r"syllabus|assignment|semester|\bexam|university|college|school"),
    ("property", r"rent(al)?[\s_-]?agreement|lease|agreement|deed|property|khata|encumbrance|affidavit|"
                 r"power[\s_-]?of[\s_-]?attorney|legal[\s_-]?notice"),
    ("travel", r"ticket|boarding[\s_-]?pass|itinerary|flight|\bpnr\b|irctc|hotel|booking|\bvisa\b"),
    ("manuals", r"manual|user[\s_-]?guide|\bguide\b|datasheet|handbook|instructions|cheat[\s_-]?sheet|tutorial"),
]
NAME_RULES = [(k, re.compile(p, re.I)) for k, p in NAME_RULES]

# Words that carry no meaning in a file name.
GENERIC = {"download", "downloads", "document", "documents", "doc", "docx", "file", "files", "scan", "scanned",
           "untitled", "new", "copy", "print", "output", "export", "report", "attachment", "image", "img", "pdf",
           "final", "draft", "temp", "tmp", "test", "sample", "data", "sheet", "book", "form", "letter", "page",
           "pg", "microsoft", "word", "excel", "powerpoint", "presentation", "text", "notes", "note", "misc",
           "signed", "version", "ver", "rev", "full", "part", "edited"}
MACHINE_WORD = re.compile(r"(img|dsc|scan|doc|pxl|wa|vid|cam|pic|file)\d*$")


def words_of(stem):
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)          # AirtelBill -> Airtel Bill
    return re.findall(r"[a-z]+", stem.lower())


def rule_classify(name):
    stem = os.path.splitext(name)[0]
    text = " ".join(words_of(stem))
    for key, rx in NAME_RULES:
        if rx.search(text) or rx.search(stem):
            return key
    return None


def is_opaque(name):
    """True when the name tells us nothing about the content (download.pdf, Doc1.docx, img2025..., PG 7.pdf)."""
    stem = os.path.splitext(name)[0]
    if re.fullmatch(r"[0-9a-fA-F-]{12,}", stem):            # hashes / GUIDs
        return True
    meaningful = [w for w in words_of(stem) if len(w) >= 3 and w not in GENERIC and not MACHINE_WORD.match(w)]
    return sum(len(w) for w in meaningful) < 4


# ---------------------------------------------------------------- reading a short excerpt (local files only)

def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _zip_text(path, members, limit=400_000):
    parts = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for pattern in members:
            for m in sorted(n for n in names if re.fullmatch(pattern, n)):
                with z.open(m) as f:
                    parts.append(re.sub(r"<[^>]+>", " ", f.read(limit).decode("utf-8", "replace")))
                if sum(len(p) for p in parts) > SNIPPET_CHARS * 4:
                    return " ".join(parts)
    return " ".join(parts)


def extract_snippet(path):
    """First ~1500 characters of readable text, or '' if the file has none (e.g. a scanned PDF)."""
    st = os.stat(path, follow_symlinks=False)
    if st.st_file_attributes & CLOUD_ONLY:
        raise PermissionError("online-only file - not opened")   # opening it would download it
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md", ".csv"):
            with open(path, "rb") as f:
                raw = f.read(SNIPPET_CHARS * 4)
            enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
            text = raw.decode(enc, "replace")
        elif ext == ".rtf":
            with open(path, "rb") as f:
                raw = f.read(40_000).decode("latin-1", "replace")
            text = re.sub(r"\\[a-z]+-?\d* ?|\\'[0-9a-f]{2}|[{}]", " ", raw)
        elif ext == ".docx":
            text = _zip_text(path, [r"word/document\.xml"])
        elif ext == ".xlsx":
            text = _zip_text(path, [r"xl/sharedStrings\.xml", r"xl/worksheets/sheet1\.xml"])
        elif ext == ".pptx":
            text = _zip_text(path, [r"ppt/slides/slide[1-3]\.xml"])
        elif ext == ".odt":
            text = _zip_text(path, [r"content\.xml"])
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            if reader.is_encrypted and not reader.decrypt(""):
                return ""
            text = " ".join((page.extract_text() or "") for page in reader.pages[:2])
        else:
            return ""
    except (OSError, zipfile.BadZipFile, ValueError, KeyError) as e:
        raise ValueError(f"couldn't read it ({e.__class__.__name__})") from e
    except Exception as e:                       # malformed PDFs raise many different errors
        raise ValueError(f"couldn't read it ({e.__class__.__name__})") from e
    return _clean(text)[:SNIPPET_CHARS]


# ---------------------------------------------------------------- AI prompts

NAMES_SYSTEM = f"""You sort a person's documents into categories using ONLY their file names.
Categories: {CATEGORY_HELP}.
For each file give the best category key and a short description of what it probably is (max 8 words).
If the name really gives no clue, use "other". Describe only what the name shows - don't invent details.
Respond with JSON only: {{"items":[{{"id":1,"category":"<key>","summary":"<what it probably is>"}}]}}"""

CONTENT_SYSTEM = f"""You sort a person's documents into categories. For each file you get its name and the first
part of its text. Categories: {CATEGORY_HELP}.
For each file give the best category key and a short description of what it is (max 10 words).
Use only facts present in the text - no invented dates or names - and leave out account, order or ID numbers.
Respond with JSON only: {{"items":[{{"id":1,"category":"<key>","summary":"<what the document is>"}}]}}"""

NAMES_BATCH, CONTENT_BATCH = 40, 6
NAMES_MAX_TOKENS, CONTENT_MAX_TOKENS = 2000, 1200


def names_prompts(names):
    return [(NAMES_SYSTEM, "\n".join(f"{i + 1}. {n}" for i, n in enumerate(names[s:s + NAMES_BATCH])))
            for s in range(0, len(names), NAMES_BATCH)]


def content_prompts(items):
    """items: [(name, snippet)]"""
    return [(CONTENT_SYSTEM, "\n\n".join(f"File {i + 1}: {n}\nText: {t}" for i, (n, t) in enumerate(items[s:s + CONTENT_BATCH])))
            for s in range(0, len(items), CONTENT_BATCH)]


def _answers(data, count):
    out = {}
    for item in data.get("items", []) if isinstance(data, dict) else []:
        try:
            i = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if 1 <= i <= count:
            cat = str(item.get("category", "other")).lower().strip()
            out[i] = (cat if cat in CATEGORIES else "other", str(item.get("summary", ""))[:120])
    return out


def ask(llm, prompts, sizes, max_tokens, progress=None, stage=""):
    """Run prompt batches; returns a flat list of (category, summary) in input order."""
    results = []
    for b, ((system, user), size) in enumerate(zip(prompts, sizes)):
        if progress:
            progress(stage, b, len(prompts))
        got = _answers(llm.chat_json(system, user, max_tokens=max_tokens), size)
        results += [got.get(i + 1, ("other", "")) for i in range(size)]
    return results


# ---------------------------------------------------------------- cache (AI results only)

def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def cache_key(path, size, mtime):
    return f"{os.path.normcase(path)}|{size}|{int(mtime)}"
