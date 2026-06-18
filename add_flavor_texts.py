"""
add_flavor_texts.py
.raw/flavor_texts.json 의 도감 설명문을 wiki/pokemon-*.md 에 추가.
이미 "도감 설명" 섹션이 있는 페이지는 건너뜀.
"""
import json, re
from pathlib import Path
from datetime import date

WIKI_DIR  = Path("wiki")
TODAY     = date.today().isoformat()
flavors   = json.loads(Path(".raw/flavor_texts.json").read_text(encoding="utf-8"))
names     = json.loads(Path(".raw/go_all_names.json").read_text(encoding="utf-8"))

en2dex = {v["en_name"].lower(): int(k) for k, v in names.items()}

def slug_to_en(slug: str) -> str:
    return slug.replace("pokemon-", "").replace("-", " ")

added = skipped_no_data = skipped_exists = skipped_no_match = 0

for page_path in sorted(WIKI_DIR.glob("pokemon-*.md")):
    content = page_path.read_text(encoding="utf-8")

    if "## 도감 설명" in content:
        skipped_exists += 1
        continue

    en_raw = slug_to_en(page_path.stem)
    dex = en2dex.get(en_raw)
    if not dex:
        skipped_no_match += 1
        continue

    entry = flavors.get(str(dex), {})
    text  = entry.get("ko") or entry.get("en", "")
    if not text:
        skipped_no_data += 1
        continue

    flavor_section = f'\n## 도감 설명\n\n> {text}\n'

    # "## 기본 스탯" 앞에 삽입, 없으면 "## 포켓몬 GO 스탯" 앞에
    if "## 기본 스탯" in content:
        content = content.replace("## 기본 스탯", flavor_section + "## 기본 스탯", 1)
    elif "## 포켓몬 GO 스탯" in content:
        content = content.replace("## 포켓몬 GO 스탯", flavor_section + "## 포켓몬 GO 스탯", 1)
    else:
        content = content.rstrip() + "\n" + flavor_section

    content = re.sub(r'(modified: )\d{4}-\d{2}-\d{2}', f'\\g<1>{TODAY}', content)
    page_path.write_text(content, encoding="utf-8")
    added += 1

print(f"추가: {added}개 / 이미 있음: {skipped_exists}개 / 데이터 없음: {skipped_no_data}개 / 매핑 실패: {skipped_no_match}개")
