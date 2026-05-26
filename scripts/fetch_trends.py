from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


BANGKOK = timezone(timedelta(hours=7))
GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo=TH"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


CATEGORY_RULES = {
    "food": ["อาหาร", "คาเฟ่", "ร้าน", "กิน", "เมนู", "food", "cafe", "restaurant", "coffee"],
    "beauty": ["แฟชั่น", "สวย", "beauty", "fashion", "makeup", "skincare"],
    "entertainment": ["เพลง", "หนัง", "ดารา", "ซีรีส์", "concert", "movie", "music", "series"],
    "relationship": ["รัก", "แฟน", "แต่งงาน", "relationship", "dating", "marriage"],
    "lifestyle": ["เที่ยว", "บ้าน", "ทำงาน", "สุขภาพ", "travel", "lifestyle", "work"],
    "social_topic": ["สังคม", "ไวรัล", "viral", "community", "online"],
}

TOPIC_CLUSTERS = [
    {
        "key": "thai-help-thai-plus",
        "title": "ไทยช่วยไทยพลัส / คนละครึ่งพลัส",
        "terms": ["ไทยช่วยไทย", "คนละครึ่งพลัส", "เป๋าตัง", "เช็กสิทธิ", "เช็คสิทธิ"],
        "category": "social_topic",
        "riskLevel": "medium",
        "contentPotential": "medium",
        "summary": "ประเด็นลงทะเบียนและตรวจสิทธิโครงการไทยช่วยไทยพลัส/คนละครึ่งพลัสมีหลายข่าวในช่วงนี้ เหมาะใช้เป็นหัวข้อให้ข้อมูลและชวนแชร์ประสบการณ์แบบระวังความถูกต้อง",
        "whyItMatters": "เป็นเรื่องที่คนจำนวนมากค้นหาเพราะเกี่ยวกับสิทธิและการลงทะเบียน จึงมีโอกาสเกิดคำถามและ discussion สูง",
        "creatorAngle": "เล่าประสบการณ์การเช็กสิทธิหรือถามว่าคนอื่นเจอขั้นตอนไหนติดขัด โดยไม่ยืนยันข้อมูลแทนแหล่งทางการ",
        "promptIdea": "มีใครลองเช็กสิทธิแล้วเจอข้อความแบบไหนบ้าง?",
        "hashtags": ["#ไทยช่วยไทยพลัส", "#คนละครึ่งพลัส", "#เช็กสิทธิ", "#เป๋าตัง"],
        "riskNote": "Medium risk ควรอ้างอิงแหล่งทางการและเตือนให้ระวังลิงก์ปลอมหรือข้อมูลผิด",
    },
    {
        "key": "ferrari-luce",
        "title": "Ferrari / Ferrari Luce",
        "terms": ["ferrari luce", "ferrari"],
        "category": "lifestyle",
        "riskLevel": "low",
        "contentPotential": "medium",
        "summary": "หัวข้อ Ferrari/Ferrari Luce ถูกค้นหาในช่วงล่าสุด เหมาะเป็น topic สาย lifestyle, luxury หรือ design",
        "whyItMatters": "เป็น trend ที่หยิบไปคุยเรื่องภาพลักษณ์ แบรนด์ หรือความเห็นต่อสินค้า/ดีไซน์ได้",
        "creatorAngle": "ชวนคุยว่าคนมองแบรนด์ luxury แบบนี้ยังไง หรือดีไซน์ไหนที่จำง่ายที่สุด",
        "promptIdea": "ถ้าพูดถึงแบรนด์นี้ ทุกคนนึกถึงอะไรเป็นอย่างแรก?",
        "hashtags": ["#LifestyleTH", "#LuxuryTalk", "#DesignTrend"],
        "riskNote": "Low risk แต่ควรเลี่ยงใช้รูป/โลโก้โดยไม่มีสิทธิ์",
    },
]

HIGH_RISK_TERMS = [
    "การเมือง",
    "เลือกตั้ง",
    "อาชญากรรม",
    "ฆ่า",
    "เสียชีวิต",
    "อุบัติเหตุ",
    "สงคราม",
    "โรค",
    "วัคซีน",
    "ศาสนา",
    "politic",
    "election",
    "crime",
    "murder",
    "death",
    "war",
    "disease",
    "vaccine",
    "religion",
]

MEDIUM_RISK_TERMS = [
    "ดราม่า",
    "ร้องเรียน",
    "แบน",
    "ประท้วง",
    "มิจฉาชีพ",
    "ลิงก์ปลอม",
    "debate",
    "complaint",
    "boycott",
    "protest",
    "scandal",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Thailand trend/news feed for Creator Trend Hub.")
    parser.add_argument("--out", default="creator-trend-hub/data/trends.json", help="Output JSON path.")
    parser.add_argument("--keep-existing", action="store_true", help="Keep existing data if all feeds fail.")
    args = parser.parse_args()

    out_path = Path(args.out)
    now = datetime.now(BANGKOK)
    existing_topics = load_existing_topics(out_path)
    topics = []
    errors = []
    failed_sources = set()

    try:
        topics.extend(fetch_google_trends(now))
    except Exception as exc:  # noqa: BLE001 - CLI should keep going on feed failure.
        errors.append(f"google_trends: {exc}")
        failed_sources.add("trends")

    try:
        topics.extend(fetch_gdelt_news(now))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"gdelt: {exc}")
        failed_sources.add("news")

    if existing_topics and failed_sources:
        topics.extend(topic for topic in existing_topics if topic.get("sourceType") in failed_sources)

    topics = dedupe_topics(topics)

    if not topics and args.keep_existing and out_path.exists():
        print("No fresh topics fetched; keeping existing data.", file=sys.stderr)
        if errors:
            print("; ".join(errors), file=sys.stderr)
        return 0

    payload = {
        "generatedAt": now.isoformat(),
        "dateRange": f"{(now - timedelta(days=7)).date().isoformat()} to {now.date().isoformat()}",
        "sourceErrors": errors,
        "topics": topics,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(topics)} topics to {out_path}")
    if errors:
        print("Feed warnings: " + "; ".join(errors), file=sys.stderr)
    return 0


def load_existing_topics(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload.get("topics", []) if isinstance(payload.get("topics"), list) else []


def fetch_google_trends(now: datetime) -> list[dict]:
    root = parse_xml(fetch_url(GOOGLE_TRENDS_RSS, timeout=30))
    ns = {"ht": "https://trends.google.com/trending/rss"}
    items = []
    for item in root.findall("./channel/item")[:30]:
        title = text(item, "title")
        traffic = text(item, "ht:approx_traffic", ns)
        description = strip_html(text(item, "description"))
        link = text(item, "link") or "https://trends.google.com/trending?geo=TH"
        pub_date = parse_rss_date(text(item, "pubDate")) or now
        news_items = item.findall("ht:news_item", ns)
        sources = [{"title": "Google Trends", "url": link}]
        for news in news_items[:3]:
            news_title = text(news, "ht:news_item_title", ns)
            news_url = text(news, "ht:news_item_url", ns)
            if news_url:
                sources.append({"title": news_title or "Related news", "url": news_url})

        items.append(make_topic(
            title=title,
            source_type="trends",
            summary=description or f"กำลังถูกค้นหาใน Google Trends Thailand ประมาณ {traffic or 'หลาย'} searches",
            sources=sources,
            updated_at=pub_date,
            traffic=traffic,
        ))
    return items


def fetch_gdelt_news(now: datetime) -> list[dict]:
    params = {
        "query": "Thailand",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": "20",
        "sort": "HybridRel",
        "timespan": "2d",
    }
    url = f"{GDELT_DOC_API}?{urllib.parse.urlencode(params)}"
    payload = json.loads(fetch_url(url, timeout=35).decode("utf-8"))
    articles = payload.get("articles", [])
    topics = []
    for article in articles:
        title = article.get("title") or article.get("seendate") or "Thailand news"
        domain = article.get("domain") or "News source"
        url = article.get("url")
        seen = parse_gdelt_date(article.get("seendate")) or now
        topics.append(make_topic(
            title=title,
            source_type="news",
            summary=f"ข่าวจาก {domain} ที่เกี่ยวข้องกับ Thailand ในช่วง 48 ชั่วโมงล่าสุด",
            sources=[{"title": domain, "url": url}] if url else [],
            updated_at=seen,
        ))
    return topics


def make_topic(title: str, source_type: str, summary: str, sources: list[dict], updated_at: datetime, traffic: str | None = None) -> dict:
    cluster = topic_cluster(title + " " + summary)
    if cluster:
        category = cluster["category"]
        risk = cluster["riskLevel"]
        potential = cluster["contentPotential"]
        hashtags = cluster["hashtags"]
        summary = cluster["summary"]
    else:
        category = classify_category(title + " " + summary)
        risk = classify_risk(title + " " + summary)
        potential = classify_potential(category, risk, source_type, traffic)
        hashtags = hashtags_for(category, title)
    return {
        "id": stable_id(title),
        "title": title,
        "sourceType": source_type,
        "category": category,
        "contentPotential": potential,
        "riskLevel": risk,
        "summary": summary,
        "whyItMatters": cluster["whyItMatters"] if cluster else why_it_matters(category, source_type),
        "creatorAngle": cluster["creatorAngle"] if cluster else creator_angle(category, risk),
        "promptIdea": cluster["promptIdea"] if cluster else prompt_idea(category, risk),
        "hashtags": hashtags,
        "riskNote": cluster["riskNote"] if cluster else risk_note(risk),
        "sources": clean_sources(sources),
        "updatedAt": updated_at.astimezone(BANGKOK).isoformat(),
    }


def classify_category(text_value: str) -> str:
    lowered = text_value.lower()
    for category, terms in CATEGORY_RULES.items():
        if any(term.lower() in lowered for term in terms):
            return category
    return "social_topic"


def classify_risk(text_value: str) -> str:
    lowered = text_value.lower()
    if any(term.lower() in lowered for term in HIGH_RISK_TERMS):
        return "high"
    if any(term.lower() in lowered for term in MEDIUM_RISK_TERMS):
        return "medium"
    return "low"


def classify_potential(category: str, risk: str, source_type: str, traffic: str | None) -> str:
    if risk == "high":
        return "low"
    if category in {"food", "entertainment", "relationship", "lifestyle", "beauty"}:
        return "high"
    if source_type == "trends" and traffic:
        return "medium"
    return "medium"


def hashtags_for(category: str, title: str) -> list[str]:
    base = {
        "food": ["#FoodTrend", "#CafeTH", "#รีวิวของกิน"],
        "beauty": ["#BeautyTalk", "#FashionTH", "#ไอเดียแต่งตัว"],
        "entertainment": ["#EntertainmentTH", "#คุยเรื่องบันเทิง", "#กระแสวันนี้"],
        "relationship": ["#RelationshipTalk", "#คุยกันหน่อย", "#SocialTopic"],
        "lifestyle": ["#LifestyleTH", "#ชีวิตประจำวัน", "#แชร์ประสบการณ์"],
        "social_topic": ["#SocialTopic", "#คุยกันวันนี้", "#TrendTH"],
    }.get(category, ["#TrendTH"])
    keyword = re.sub(r"\s+", "", title.strip())[:24]
    if keyword and not keyword.startswith("#"):
        base.append(f"#{keyword}")
    return base[:4]


def why_it_matters(category: str, source_type: str) -> str:
    if source_type == "trends":
        return "เป็นสัญญาณว่าคนกำลังค้นหาและสนใจเรื่องนี้ในช่วงล่าสุด"
    if category in {"food", "beauty", "lifestyle"}:
        return "เป็นข่าวหรือหัวข้อที่ต่อยอดเป็นประสบการณ์ส่วนตัวและโพสต์ชวนคุยได้"
    return "ช่วยให้ทีมรู้ว่าประเด็นไหนกำลังถูกพูดถึงก่อนเลือก brief Creator"


def creator_angle(category: str, risk: str) -> str:
    if risk == "high":
        return "ใช้เป็นข้อมูลเฝ้าระวังมากกว่าบรีฟโพสต์ หากต้องใช้ควรให้ทีม review ก่อน"
    return {
        "food": "ให้ Creator เล่าประสบการณ์ร้าน/เมนูที่อยากลอง แล้วถามคนอื่นว่าคิดเหมือนกันไหม",
        "beauty": "ชวนแชร์สไตล์ ไอเท็ม หรือเทคนิคที่ใช้จริงโดยไม่ขายของแข็งเกินไป",
        "entertainment": "เล่า reaction ส่วนตัวต่อกระแส แล้วเปิดคำถามให้คนคุยต่อ",
        "relationship": "ตั้งเป็นสถานการณ์สมมติหรือมุมมองทั่วไปเพื่อชวนแลกเปลี่ยน",
        "lifestyle": "โยงกับชีวิตประจำวันของ Creator และถามประสบการณ์คนในคอมมูนิตี้",
    }.get(category, "เล่าแบบ personal take และชวนคอมเมนต์ด้วยคำถามปลายเปิด")


def prompt_idea(category: str, risk: str) -> str:
    if risk == "high":
        return "เรื่องนี้ควรเช็กข้อมูลก่อนแชร์ ทุกคนคิดว่าเราควรระวังอะไรบ้าง?"
    return {
        "food": "เห็นคนพูดถึงเมนูนี้เยอะมาก มีใครลองแล้วบ้าง?",
        "beauty": "สไตล์นี้ถ้าแต่งในชีวิตจริงจะรอดไหม?",
        "entertainment": "กระแสนี้ทุกคนอยู่ทีมไหน?",
        "relationship": "ถ้าเป็นคุณ จะรับมือกับสถานการณ์แบบนี้ยังไง?",
        "lifestyle": "ช่วงนี้มีใครเจอเรื่องแบบนี้เหมือนกันไหม?",
    }.get(category, "ทุกคนคิดยังไงกับเรื่องนี้?")


def risk_note(risk: str) -> str:
    return {
        "low": "Low risk ใช้เป็นไอเดียโพสต์ได้ แต่ยังควรตรวจรูปและที่มา",
        "medium": "Medium risk ควรเลี่ยงการพาดพิงบุคคลจริงและใช้คำถามเชิงสร้างสรรค์",
        "high": "High risk ควรให้ทีม review ก่อนนำไป brief Creator และไม่ควรชวนดราม่า",
    }.get(risk, "ตรวจ context ก่อนใช้งาน")


def dedupe_topics(topics: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for topic in topics:
        if should_skip_topic(topic["title"]):
            continue
        cluster = topic_cluster(topic["title"] + " " + topic.get("summary", ""))
        key = cluster["key"] if cluster else normalize_title(topic["title"])
        if key in merged:
            existing = merged[key]
            existing["sources"] = clean_sources(existing.get("sources", []) + topic.get("sources", []))
            existing["hashtags"] = merge_list(existing.get("hashtags", []), topic.get("hashtags", []), limit=6)
            if existing["sourceType"] != topic["sourceType"]:
                existing["sourceType"] = "news" if "news" in {existing["sourceType"], topic["sourceType"]} else existing["sourceType"]
            if cluster:
                apply_cluster(existing, cluster)
            continue
        if cluster:
            topic = {**topic}
            apply_cluster(topic, cluster)
        merged[key] = topic
    return sorted(merged.values(), key=lambda item: (risk_rank(item["riskLevel"]), potential_rank(item["contentPotential"]), item["title"]))


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", "", title.lower())


def topic_cluster(text_value: str) -> dict | None:
    lowered = text_value.lower()
    for cluster in TOPIC_CLUSTERS:
        if any(term.lower() in lowered for term in cluster["terms"]):
            return cluster
    return None


def apply_cluster(topic: dict, cluster: dict) -> None:
    topic["id"] = cluster["key"]
    topic["title"] = cluster["title"]
    topic["category"] = cluster["category"]
    topic["riskLevel"] = cluster["riskLevel"]
    topic["contentPotential"] = cluster["contentPotential"]
    topic["summary"] = cluster["summary"]
    topic["whyItMatters"] = cluster["whyItMatters"]
    topic["creatorAngle"] = cluster["creatorAngle"]
    topic["promptIdea"] = cluster["promptIdea"]
    topic["hashtags"] = cluster["hashtags"]
    topic["riskNote"] = cluster["riskNote"]


def should_skip_topic(title: str) -> bool:
    # CJK-only foreign headlines are usually not usable for Thai creator briefs in v1.
    has_cjk = re.search(r"[\u3400-\u9fff]", title) is not None
    has_thai = re.search(r"[\u0e00-\u0e7f]", title) is not None
    return has_cjk and not has_thai


def merge_list(left: list, right: list, limit: int) -> list:
    output = []
    for item in left + right:
        if item and item not in output:
            output.append(item)
        if len(output) >= limit:
            break
    return output


def risk_rank(risk: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(risk, 1)


def potential_rank(potential: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(potential, 1)


def clean_sources(sources: list[dict]) -> list[dict]:
    seen = set()
    clean = []
    for source in sources:
        url = source.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        clean.append({"title": source.get("title") or "Source", "url": url})
    return clean[:5]


def stable_id(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())[:40].strip("-")
    return f"{slug or 'topic'}-{digest}"


def fetch_url(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CreatorTrendHub/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_xml(value: bytes) -> ET.Element:
    return ET.fromstring(value)


def text(node: ET.Element, path: str, ns: dict | None = None) -> str:
    found = node.find(path, ns or {})
    return (found.text or "").strip() if found is not None else ""


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()


def parse_rss_date(value: str) -> datetime | None:
    if not value:
        return None
    parsed = email.utils.parsedate_to_datetime(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_gdelt_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


if __name__ == "__main__":
    raise SystemExit(main())
