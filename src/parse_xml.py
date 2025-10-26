import pathlib, re, html, hashlib, xml.etree.ElementTree as ET
from utils import write_jsonl, DATA_STAGE

RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"

def extract_event(elem):
    # 便捷读取：尝试多个 XPath（直系与下钻）
    def ftext(paths):
        for p in paths:
            t = elem.findtext(p)
            if t and t.strip():
                return t.strip()
        return ""

    # 常见字段：更丰富的标签与下钻（Event 必含 Description）
    doc_id = elem.attrib.get("id") or ftext(["id", ".//id", ".//event/id", ".//group/id"]) or ""
    title = ftext(["title", "name", ".//name", ".//event/name"])  # 许多数据用 <name> 作为标题
    description_raw = ftext(["description", ".//description"])  # Event 类文件关键字段

    # Group 信息下钻
    group_name = ftext(["group", ".//group/name", ".//group/who"])  # who/name 二选一
    group_urlname = ftext([".//group/urlname"]) or ""

    # Venue 信息下钻
    venue_name = ftext([".//venue/name"]) or ""
    venue_addr = ftext([".//venue/address_1"]) or ""
    venue_city = ftext([".//venue/city"]) or ""
    venue_state = ftext([".//venue/state"]) or ""
    venue_country = ftext([".//venue/country"]) or ""
    venue_lat = ftext([".//venue/lat"]) or ""
    venue_lon = ftext([".//venue/lon"]) or ""

    # Hosts 下钻（可能有多个 host）
    host_names = [
        (x.text or "").strip()
        for x in elem.findall(".//event_hosts_item/member_name")
        if x is not None and (x.text or "").strip()
    ]

    # 其他常用元数据
    time_val = ftext(["time", ".//time"]) or ""
    created = ftext(["created", ".//created"]) or ""
    updated = ftext(["updated", ".//updated"]) or ""
    status = ftext(["status", ".//status"]) or ""
    yes_rsvp = ftext(["yes_rsvp_count", ".//yes_rsvp_count"]) or ""
    maybe_rsvp = ftext(["maybe_rsvp_count", ".//maybe_rsvp_count"]) or ""
    waitlist = ftext(["waitlist_count", ".//waitlist_count"]) or ""
    headcount = ftext(["headcount", ".//headcount"]) or ""
    event_url = ftext(["event_url", ".//event_url"]) or ""

    # HTML 清洗与实体反转义（只用于 text 聚合，不覆盖原 description_raw）
    desc_clean = description_raw
    if desc_clean:
        desc_clean = re.sub(r"<[^>]+>", " ", desc_clean)
        desc_clean = html.unescape(desc_clean)

    # 组装统一可检索文本：标题 + 描述 + 群组 + 场地 + 主持人 + 城市州国家
    text_parts = [
        title,
        desc_clean,
        group_name,
        group_urlname,
        venue_name,
        venue_addr,
        venue_city,
        venue_state,
        venue_country,
        ", ".join(host_names) if host_names else "",
    ]
    text = " ".join([p for p in text_parts if p]).strip()

    doc = {
        "doc_id": doc_id,
        "title": title,
        "description": description_raw,  # 保留原始 HTML
        "group": group_name,
        "group_urlname": group_urlname,
        "venue": {
            "name": venue_name,
            "address_1": venue_addr,
            "city": venue_city,
            "state": venue_state,
            "country": venue_country,
            "lat": venue_lat,
            "lon": venue_lon,
        },
        "hosts": host_names,
        "status": status,
        "time": time_val,
        "created": created,
        "updated": updated,
        "yes_rsvp_count": yes_rsvp,
        "maybe_rsvp_count": maybe_rsvp,
        "waitlist_count": waitlist,
        "headcount": headcount,
        "event_url": event_url,
        "text": text,
    }
    return doc

def main():
    docs = []
    for xml_path in RAW_DIR.rglob("*.xml"):
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # 兼容 <events><event/></events> 或直接 <event/>（或 <item/>）
        if root.tag.lower() == "events":
            events = root.findall(".//event")
        else:
            events = [root]
        for e in events:
            d = extract_event(e)
            if not d.get("doc_id"):
                # 基于 title/time/group 生成稳定 doc_id（避免冲突）
                key = (d.get("title", "") + "|" + d.get("time", "") + "|" + d.get("group", "")).encode("utf-8", errors="ignore")
                d["doc_id"] = hashlib.md5(key).hexdigest()[:12]
            if d["text"]:
                docs.append(d)
    out = DATA_STAGE / "events.jsonl"
    write_jsonl(out, docs)
    print(f"Parsed {len(docs)} docs -> {out}")

if __name__ == "__main__":
    main()

