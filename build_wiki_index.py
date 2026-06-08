# Wiki index builder
import sys
import os
import re
import json
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

WIKI_DIR = "wiki"
INDEX_PATH = os.path.join(WIKI_DIR, ".llm-wiki", "index.md")
MANIFEST_PATH = os.path.join(WIKI_DIR, ".llm-wiki", "cache", "source-manifest.json")
SENTINEL_DIR = os.path.join(WIKI_DIR, ".llm-wiki", "cache", "ingests")
os.makedirs(SENTINEL_DIR, exist_ok=True)

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TODAY = "2026-06-05"

HASHES = [
    "2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5",
    "bb8096ad5a0b2c74200879a8a90f450de39cf76898c0fd158d85011302b5f3d5",
]

# ── Parse all wiki pages ────────────────────────────────────────
def parse_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"')
    return fm

pages = []
md_files = sorted(f for f in os.listdir(WIKI_DIR) if f.endswith(".md"))
for fname in md_files:
    path = os.path.join(WIKI_DIR, fname)
    slug = fname[:-3]
    fm = parse_frontmatter(path)
    if not fm:
        continue
    pages.append({
        "slug": slug,
        "title": fm.get("title", slug),
        "type": fm.get("type", "concept"),
        "language": fm.get("language", "ko"),
        "tags": fm.get("tags", ""),
        "summary": fm.get("summary", ""),
        "modified": fm.get("modified", TODAY),
    })

print(f"Parsed {len(pages)} pages")

# ── Build index ─────────────────────────────────────────────────
type_counts = {}
for p in pages:
    t = p["type"]
    type_counts[t] = type_counts.get(t, 0) + 1

# Tag index
tag_map = {}
for p in pages:
    raw = p["tags"]
    # handle JSON array or comma separated
    if raw.startswith("["):
        try:
            tags = json.loads(raw)
        except:
            tags = []
    else:
        tags = [t.strip().strip('"') for t in raw.split(",") if t.strip()]
    for tag in tags:
        if tag not in tag_map:
            tag_map[tag] = []
        tag_map[tag].append(p)

all_pages_table = "\n".join(
    f"| {p['slug']} | {p['title']} | {p['type']} | {p['language']} | {p['summary'][:60]} | {p['modified']} |"
    for p in pages
)

type_counts_str = "\n".join(f"| {t} | {c} |" for t, c in sorted(type_counts.items()))

# Top tags (most pages)
top_tags = sorted(tag_map.items(), key=lambda x: -len(x[1]))[:15]
tag_sections = []
for tag, tag_pages in top_tags:
    lines = [f"### {tag} ({len(tag_pages)} pages)"]
    for tp in tag_pages[:10]:
        lines.append(f"- [[{tp['slug']}]] — {tp['summary'][:50]}")
    if len(tag_pages) > 10:
        lines.append(f"- ... 외 {len(tag_pages)-10}개")
    tag_sections.append("\n".join(lines))

tag_sections_str = "\n\n".join(tag_sections)

index_content = f"""# Wiki Index
<!-- AUTO-GENERATED — DO NOT EDIT BY HAND -->
**Last generated:** {NOW}
**Total pages:** {len(pages)}

## Page Type Summary / 페이지 유형
| Type | Count |
|------|-------|
{type_counts_str}

## All Pages / 전체 페이지
| Slug | Title | Type | Lang | Summary | Modified |
|------|-------|------|------|---------|----------|
{all_pages_table}

## By Tag / 태그별
{tag_sections_str}

## Orphan Pages / 고립 페이지
(run /wiki-lint to check)

## Review Queue / 검토 대기
(none)
"""

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(index_content)
print(f"Index written -> {INDEX_PATH}")

# ── Sentinel files ──────────────────────────────────────────────
for h in HASHES:
    sentinel = os.path.join(SENTINEL_DIR, f"{h}.done")
    with open(sentinel, "w") as f:
        f.write(NOW)
    print(f"Sentinel -> {sentinel}")

# ── Source manifest ─────────────────────────────────────────────
with open(MANIFEST_PATH, encoding="utf-8") as f:
    manifest = json.load(f)

manifest[HASHES[0]] = {
    "name": "type_effectiveness.json",
    "date": NOW,
    "language": "en",
    "pages_created": ["type-chart"] + [f"type-{t}" for t in [
        "normal","fighting","flying","poison","ground","rock","bug","ghost",
        "steel","fire","water","grass","electric","psychic","ice","dragon","dark","fairy"
    ]],
    "pages_updated": [],
}
manifest[HASHES[1]] = {
    "name": "gen1_pokemon.json",
    "date": NOW,
    "language": "ko",
    "pages_created": ["pokedex-gen1", "2026-06-05-pokeapi-gen1-import"] + [f"pokemon-{i}" for i in range(1, 152)],
    "pages_updated": [],
}

with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(f"Manifest updated -> {MANIFEST_PATH}")

print(f"\n[done] Wiki 구축 완료! 총 {len(pages)}개 페이지")
