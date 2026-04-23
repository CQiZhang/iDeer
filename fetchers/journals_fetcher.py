import re
import time
import requests
from datetime import datetime, timedelta


# 期刊配置：key -> (展示名, ISSN)
# ISSN 已逐一核实，可直接用于 CrossRef API
JOURNAL_ISSN = {
    "nature":         ("Nature",                     "0028-0836"),
    "science":        ("Science",                    "0036-8075"),
    "nature_food":    ("Nature Food",                "2662-1355"),
    "nature_water":   ("Nature Water",               "2731-6084"),
    "nature_climate": ("Nature Climate Change",      "1758-6798"),
    "nature_cities":  ("Nature Cities",              "2731-9997"),
    "science_adv":    ("Science Advances",           "2375-2548"),
    "one_earth":      ("One Earth",                  "2590-3322"),
    "earths_future":  ("Earth's Future",             "2328-4277"),
    "cell_rep_sus":   ("Cell Reports Sustainability", "2949-7906"),
}

CROSSREF_BASE = "https://api.crossref.org"


def _clean_jats(text: str) -> str:
    """清洗 CrossRef abstract 中的 JATS XML 标签。"""
    if not text:
        return ""
    text = re.sub(r"</?jats:[^>]+>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^\s*Abstract[:\s]+", "", text, flags=re.IGNORECASE)
    return text


def _extract_year(msg: dict) -> int | str:
    """从 CrossRef 返回中取发表年份。"""
    for key in ("published", "issued", "created"):
        date_info = msg.get(key, {})
        parts = date_info.get("date-parts", [[]])
        if parts and parts[0]:
            return parts[0][0]
    return ""


def _extract_pub_date(msg: dict) -> datetime | None:
    """取一个可比较的发表日期（用于过滤最近 N 天）。"""
    for key in ("published", "issued", "created"):
        date_info = msg.get(key, {})
        parts = date_info.get("date-parts", [[]])
        if parts and parts[0]:
            dp = parts[0]
            try:
                y = dp[0] if len(dp) >= 1 else 1970
                m = dp[1] if len(dp) >= 2 else 1
                d = dp[2] if len(dp) >= 3 else 1
                return datetime(y, m, d)
            except Exception:
                continue
    return None


def _format_authors(author_list: list) -> str:
    """[{given, family}, ...] -> 'A. Smith, B. Lee'"""
    if not author_list:
        return ""
    parts = []
    for a in author_list:
        given = a.get("given", "")
        family = a.get("family", "")
        name = f"{given} {family}".strip()
        if name:
            parts.append(name)
    return ", ".join(parts)


def _fetch_journal_works(
    issn: str,
    journal_name: str,
    days: int,
    rows: int,
    mailto: str,
) -> list[dict]:
    """
    按 ISSN + 日期范围从 CrossRef 查询一本期刊的近期论文。
    """
    from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    url = f"{CROSSREF_BASE}/journals/{issn}/works"
    params = {
    "filter": f"from-pub-date:{from_date}",
    "rows": rows,
    "sort": "published",
    "order": "desc",
}
    ua = f"DailyPaperBot/1.0 (mailto:{mailto})" if mailto else "DailyPaperBot/1.0"
    headers = {"User-Agent": ua}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
    except Exception as e:
        print(f"[journals_fetcher] {journal_name} 查询失败: {e}")
        return []

    # 想要的类型：研究论文、综述、Perspective/Analysis 等
    WANTED_TYPES = {"journal-article"}
    # 想要剔除的 subtype（Springer Nature 用 subtype 区分 editorial / news / correction 等）
    DROP_SUBTYPES = {
        "editorial", "news", "correction", "erratum", "retraction",
        "book-review", "obituary", "letter", "comment",
    }

    papers = []
    for msg in items:
        if msg.get("type") not in WANTED_TYPES:
            continue
        if msg.get("subtype", "").lower() in DROP_SUBTYPES:
            continue

        doi = msg.get("DOI", "")
        if not doi:
            continue

        title_list = msg.get("title", [])
        title = title_list[0] if title_list else ""
        if not title:
            continue

        abstract = _clean_jats(msg.get("abstract", ""))

        papers.append({
            "paper_id": doi,
            "doi": doi,
            "title": title,
            "authors": _format_authors(msg.get("author", [])),
            "journal": journal_name,
            "year": _extract_year(msg),
            "pub_date": _extract_pub_date(msg),
            "abstract": abstract,
            "url": msg.get("URL", f"https://doi.org/{doi}"),
        })

    return papers


def fetch_papers_for_journals(
    journal_keys: list[str],
    days: int = 7,
    max_results_per_journal: int = 30,
    mailto: str = "",
) -> list[dict]:
    """
    从多本期刊的 CrossRef 接口抓取近 N 天的论文，返回统一格式的 dict 列表。
    """
    all_papers = []
    seen_dois = set()

    for key in journal_keys:
        if key not in JOURNAL_ISSN:
            print(f"[journals_fetcher] 未知期刊 key: {key}")
            continue

        journal_name, issn = JOURNAL_ISSN[key]
        print(f"[journals_fetcher] 抓取 {journal_name} (ISSN: {issn}) ...")

        papers = _fetch_journal_works(
            issn=issn,
            journal_name=journal_name,
            days=days,
            rows=max_results_per_journal,
            mailto=mailto,
        )

        for p in papers:
            if p["doi"] in seen_dois:
                continue
            seen_dois.add(p["doi"])
            all_papers.append(p)

        print(f"  └─ 获得 {len(papers)} 篇")
        time.sleep(0.5)  # 对 CrossRef 礼貌限速

    # 按发表日期倒序
    all_papers.sort(
        key=lambda p: p.get("pub_date") or datetime(1970, 1, 1),
        reverse=True,
    )

    # pub_date 是 datetime，不能进缓存 JSON；剥离后返回
    for p in all_papers:
        p.pop("pub_date", None)

    print(f"[journals_fetcher] 共抓取 {len(all_papers)} 篇论文")
    return all_papers
