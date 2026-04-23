import time
import feedparser
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


# 期刊 RSS 配置：key 是内部标识，value 是展示名和 RSS URL
JOURNAL_FEEDS = {
    "nature":          ("Nature",                   "https://www.nature.com/nature.rss"),
    "nature_food":     ("Nature Food",              "https://www.nature.com/natfood.rss"),
    "nature_water":    ("Nature Water",             "https://www.nature.com/natwater.rss"),
    "nature_climate":  ("Nature Climate Change",    "https://www.nature.com/nclimate.rss"),
    "nature_cities":   ("Nature Cities",            "https://www.nature.com/natcities.rss"),
    "science":         ("Science",                  "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science"),
    "science_adv":     ("Science Advances",         "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv"),
    "one_earth":       ("One Earth",                "https://www.cell.com/one-earth/current.rss"),
    "earths_future":   ("Earth's Future",           "https://agupubs.onlinelibrary.wiley.com/feed/23284277/most-recent"),
    "cell_rep_sus":    ("Cell Reports Sustainability", "https://www.cell.com/cell-reports-sustainability/current.rss"),
}


def _parse_date(entry) -> datetime | None:
    """从 feed entry 中提取发布日期，统一为带时区的 datetime。"""
    for key in ("published", "updated", "pubDate"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    # 回退到 struct_time 字段
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return None


def _extract_doi(entry) -> str:
    """尝试从 entry 中提取 DOI。"""
    # Nature / Cell / AGU 通常把 DOI 放在 link 或 id 里
    for field in ("prism_doi", "dc_identifier", "id"):
        val = entry.get(field, "")
        if isinstance(val, str) and "10." in val:
            idx = val.find("10.")
            return val[idx:].strip()
    link = entry.get("link", "")
    if "doi.org/" in link:
        return link.split("doi.org/")[-1].strip()
    return ""


def _clean_html(text: str) -> str:
    """简单去掉 summary 里的 HTML 标签。"""
    import re
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_papers_for_journals(
    journal_keys: list[str],
    days: int = 7,
    max_results_per_journal: int = 30,
) -> list[dict]:
    """
    从指定期刊 RSS 抓取近 N 天的论文。
    返回统一格式的 dict 列表，字段对齐 PubMedSource 的使用习惯。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    seen_ids = set()

    for key in journal_keys:
        if key not in JOURNAL_FEEDS:
            print(f"[journals_fetcher] 未知期刊: {key}")
            continue

        journal_name, url = JOURNAL_FEEDS[key]
        print(f"[journals_fetcher] 抓取 {journal_name} ...")

        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[journals_fetcher] {journal_name} 抓取失败: {e}")
            continue

        count = 0
        for entry in feed.entries:
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            doi = _extract_doi(entry)
            link = entry.get("link", "")
            paper_id = doi or link
            if not paper_id or paper_id in seen_ids:
                continue
            seen_ids.add(paper_id)

            authors = ""
            if "authors" in entry:
                authors = ", ".join(a.get("name", "") for a in entry.authors if a.get("name"))
            elif "author" in entry:
                authors = entry.author

            abstract = _clean_html(entry.get("summary", "") or entry.get("description", ""))

            results.append({
                "paper_id": paper_id,
                "title": _clean_html(entry.get("title", "")),
                "authors": authors,
                "journal": journal_name,
                "year": pub_date.year if pub_date else "",
                "abstract": abstract,
                "url": link,
                "doi": doi,
            })

            count += 1
            if count >= max_results_per_journal:
                break

        time.sleep(1)  # 对服务器友好一点

    # 按日期倒序（如果拿不到日期就保持原序）
    results.sort(key=lambda x: x.get("year", 0), reverse=True)
    print(f"[journals_fetcher] 共抓取 {len(results)} 篇论文")
    return results
