import re
import time
import requests
from datetime import datetime, timedelta


# 期刊配置：key -> (展示名, ISSN)
# 注：CrossRef 的 /journals/{issn}/works endpoint 对 Elsevier 老刊和部分老牌
# 学会刊通常只认 pISSN（印刷 ISSN），不认 eISSN。下面已根据实际抓取结果做了修正。
# 经济学顶刊（AEA / Wiley / Elsevier）一律使用 pISSN。
JOURNAL_ISSN = {
    # ========== 原有 10 本（保留不动）==========
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

    # ========== 第一批新增 26 本 ==========
    # ---------- 环境科学与可持续性 ----------
    "est":              ("Environmental Science & Technology",        "1520-5851"),
    "erl":              ("Environmental Research Letters",            "1748-9326"),
    "rcr":              ("Resources, Conservation and Recycling",     "0921-3449"),  # pISSN
    "nat_sustain":      ("Nature Sustainability",                     "2398-9629"),
    "comm_earth_env":   ("Communications Earth & Environment",        "2662-4435"),
    "ambio":            ("Ambio",                                     "1654-7209"),
    "nrev_earth_env":   ("Nature Reviews Earth & Environment",        "2662-138X"),

    # ---------- 全球变化与气候 ----------
    "gec":              ("Global Environmental Change",               "0959-3780"),  # pISSN
    "gcb":              ("Global Change Biology",                     "1365-2486"),

    # ---------- 水资源 ----------
    "water_res":        ("Water Research",                            "0043-1354"),  # pISSN
    "agr_water_mgmt":   ("Agricultural Water Management",             "0378-3774"),  # pISSN

    # ---------- 食物 / 粮食安全 / 农业经济（IAAE）----------
    "food_security":    ("Food Security",                             "1876-4525"),
    "global_food_sec":  ("Global Food Security",                      "2211-9124"),
    "food_policy":      ("Food Policy",                               "0306-9192"),  # pISSN
    "ag_econ":          ("Agricultural Economics",                    "1574-0862"),  # IAAE/Wiley

    # ---------- 综合 / 顶刊 ----------
    "pnas":             ("Proceedings of the National Academy of Sciences", "1091-6490"),
    "pnas_nexus":       ("PNAS Nexus",                                "2752-6542"),
    "nat_commun":       ("Nature Communications",                     "2041-1723"),
    "sci_rep":          ("Scientific Reports",                        "2045-2322"),
    "sci_data":         ("Scientific Data",                           "2052-4463"),
    "nat_hum_behav":    ("Nature Human Behaviour",                    "2397-3374"),

    # ---------- 健康 / Lancet 系列 ----------
    "lancet":           ("The Lancet",                                "0140-6736"),  # pISSN
    "lancet_glob_h":    ("The Lancet Global Health",                  "2214-109X"),
    "lancet_planet_h":  ("The Lancet Planetary Health",               "2542-5196"),

    # ---------- 城市可持续 / 能源 ----------
    "npj_urban_sus":    ("npj Urban Sustainability",                  "2661-8001"),
    "applied_energy":   ("Applied Energy",                            "0306-2619"),  # pISSN

    # ---------- 迁移 ----------
    "jems":             ("Journal of Ethnic and Migration Studies",   "1469-9451"),

    # ========== 第二批新增 10 本：经济学顶刊 ==========
    # ---------- AEA 旗舰刊 ----------
    "aer":              ("American Economic Review",                  "0002-8282"),  # AEA
    "jel":              ("Journal of Economic Literature",            "0022-0515"),  # AEA
    "jep":              ("Journal of Economic Perspectives",          "0895-3309"),  # AEA

    # ---------- AEJ 系列 4 本 ----------
    "aej_app":          ("American Economic Journal: Applied Economics",   "1945-7782"),
    "aej_pol":          ("American Economic Journal: Economic Policy",     "1945-7731"),
    "aej_macro":        ("American Economic Journal: Macroeconomics",      "1945-7707"),
    "aej_micro":        ("American Economic Journal: Microeconomics",      "1945-7669"),

    # ---------- 农业 / 环境 / 发展经济学 ----------
    "ajae":             ("American Journal of Agricultural Economics",     "0002-9092"),  # AAEA/Wiley
    "jeem":             ("Journal of Environmental Economics and Management", "0095-0696"),  # Elsevier
    "jde":              ("Journal of Development Economics",               "0304-3878"),  # Elsevier
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
