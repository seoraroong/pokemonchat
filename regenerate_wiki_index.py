"""
regenerate_wiki_index.py
wiki/.llm-wiki/index.md 를 전체 페이지 frontmatter 기준으로 재생성.
"""
import re
from pathlib import Path
from datetime import datetime, timezone

WIKI_DIR   = Path("wiki")
INDEX_PATH = WIKI_DIR / ".llm-wiki" / "index.md"

FM_PAT = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)

def parse_frontmatter(text: str) -> dict:
    m = FM_PAT.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        fm[key.strip()] = val.strip().strip('"')
    return fm

pages = []
for md in sorted(WIKI_DIR.glob("*.md")):
    if md.parent != WIKI_DIR:
        continue
    text = md.read_text(encoding="utf-8")
    fm   = parse_frontmatter(text)
    if not fm:
        continue
    pages.append({
        "slug":     md.stem,
        "title":    fm.get("title", md.stem),
        "type":     fm.get("type", "concept"),
        "lang":     fm.get("language", "ko"),
        "summary":  fm.get("summary", ""),
        "modified": fm.get("modified", ""),
    })

# 타입별 집계
type_counts: dict[str, int] = {}
for p in pages:
    type_counts[p["type"]] = type_counts.get(p["type"], 0) + 1

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

rows = "\n".join(
    f"| {p['slug']} | {p['title']} | {p['type']} | {p['lang']} | {p['summary']} | {p['modified']} |"
    for p in pages
)
type_rows = "\n".join(f"| {t} | {c} |" for t, c in sorted(type_counts.items()))

index_md = f"""# Wiki Index
<!-- AUTO-GENERATED — DO NOT EDIT BY HAND -->
**Last generated:** {now}
**Total pages:** {len(pages)}

## Page Type Summary / 페이지 유형
| Type | Count |
|------|-------|
{type_rows}

## All Pages / 전체 페이지
| Slug | Title | Type | Lang | Summary | Modified |
|------|-------|------|------|---------|----------|
{rows}
"""

INDEX_PATH.write_text(index_md, encoding="utf-8")
print(f"완료: {len(pages)}개 페이지 → {INDEX_PATH}")
