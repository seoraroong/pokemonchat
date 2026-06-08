"""
fetch_current_raids.py
ScrapedDuck 레이드 보스 데이터 수집 + wiki/current-raids.md 생성.
"""
import sys, json, os, re
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR    = ".raw"
WIKI_DIR   = "wiki"
GM_PATH    = os.path.join(RAW_DIR, "game_master_pokemon.json")
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
OUTPUT_RAW = os.path.join(RAW_DIR, "current_raids.json")
OUTPUT_MD  = os.path.join(WIKI_DIR, "current-raids.md")
TODAY      = "2026-06-05"
HEADERS    = {"User-Agent": "pogo-wiki-builder/1.0"}

RAIDS_URL = (
    "https://raw.githubusercontent.com/bigfoott/ScrapedDuck"
    "/data/raids.json"
)

TYPE_KO = {
    "Normal":"노말","Fire":"불꽃","Water":"물","Electric":"전기",
    "Grass":"풀","Ice":"얼음","Fighting":"격투","Poison":"독",
    "Ground":"땅","Flying":"비행","Psychic":"에스퍼","Bug":"벌레",
    "Rock":"바위","Ghost":"고스트","Dragon":"드래곤","Dark":"악",
    "Steel":"강철","Fairy":"페어리",
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}

TIER_KO = {
    "1": "1성", "3": "3성", "5": "5성", "mega": "메가",
    "mega_legendary": "메가 레전더리",
}

def pokemon_slug(en_name: str) -> str:
    s = en_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9-]", "", s)

# ── 보조 데이터 ────────────────────────────────────────────────────
with open(NAMES_PATH, encoding="utf-8") as f:
    names_data: dict[str, dict] = json.load(f)
with open(GM_PATH, encoding="utf-8") as f:
    gm_data: dict[str, dict] = json.load(f)

# dex → ko_name, en_name
dex_to_names: dict[int, dict] = {}
for dex_str, nd in names_data.items():
    dex_to_names[int(dex_str)] = nd

# 영문 이름 → dex (대소문자 불문)
en_lower_to_dex: dict[str, int] = {
    nd["en_name"].lower(): int(dex_str)
    for dex_str, nd in names_data.items()
}

# ── 접두사 처리 (Mega, Shadow, Alolan, Galarian 등) ──────────────
PREFIXES_KO: list[tuple[str, str]] = [
    ("mega ",      "메가 "),
    ("shadow ",    "다크 "),
    ("alolan ",    "알로라 "),
    ("galarian ",  "가라르 "),
    ("hisuian ",   "히스이 "),
    ("paldean ",   "팔데아 "),
    ("kantonian ", "관동 "),
    ("johtonian ", "성도 "),
]

def parse_prefixes(en_name: str) -> tuple[str, str]:
    """여러 접두사를 순서대로 제거해 (ko_prefix, base_en_name) 반환."""
    remaining  = en_name
    prefix_ko  = ""
    changed    = True
    while changed:
        changed = False
        low = remaining.lower()
        for en_pfx, ko_pfx in PREFIXES_KO:
            if low.startswith(en_pfx):
                prefix_ko += ko_pfx
                remaining  = remaining[len(en_pfx):]
                changed    = True
                break
    return prefix_ko, remaining

def find_dex(en_name: str) -> int | None:
    dex = en_lower_to_dex.get(en_name.lower())
    if dex:
        return dex
    # 접두사 제거 후 재시도
    _, base = parse_prefixes(en_name)
    return en_lower_to_dex.get(base.lower())

def ko_name_for(en_name: str, dex: int | None) -> str:
    prefix_ko, base_en = parse_prefixes(en_name)
    if dex:
        base_ko = dex_to_names.get(dex, {}).get("ko_name", base_en)
        return prefix_ko + base_ko
    # dex 없는 경우에도 접두사 한국어 + 영문 base 반환
    return prefix_ko + base_en if prefix_ko else en_name

# ── ScrapedDuck 다운로드 ──────────────────────────────────────────
print("ScrapedDuck 레이드 보스 다운로드...")
try:
    r = requests.get(RAIDS_URL, timeout=30, headers=HEADERS)
    r.raise_for_status()
    raw_data = r.json()
    print(f"  → 데이터 로드 성공")
except Exception as e:
    print(f"  [실패] {e}")
    print("  ScrapedDuck URL이 변경됐을 수 있습니다.")
    print("  https://github.com/bigfoott/ScrapedDuck 에서 확인하세요.")
    print("  빈 데이터로 계속합니다.")
    raw_data = []

# ── ScrapedDuck 포맷 파싱 ─────────────────────────────────────────
# 실제 포맷: flat list of {name, tier, canBeShiny, types:[{name,image}], ...}
# tier 예시: "1-Star Raids", "3-Star Raids", "5-Star Raids", "Mega Raids", etc.
bosses_by_tier: dict[str, list] = {}

TIER_NORMALIZE = {
    "1-star raids": "1", "1-star": "1",
    "3-star raids": "3", "3-star": "3",
    "5-star raids": "5", "5-star": "5",
    "mega raids": "mega", "mega": "mega",
    "mega legendary raids": "mega_legendary",
    "elite raids": "elite",
}

def normalize_tier(raw_tier: str) -> str:
    k = raw_tier.lower().strip()
    return TIER_NORMALIZE.get(k, raw_tier)

if isinstance(raw_data, list):
    # flat list: 각 항목이 개별 보스
    if raw_data and "tier" in raw_data[0]:
        for boss_entry in raw_data:
            raw_tier = boss_entry.get("tier", "?")
            tier = normalize_tier(raw_tier)
            bosses_by_tier.setdefault(tier, []).append(boss_entry)
    else:
        # 구 포맷: [{tier, bosses: [...]}]
        for tier_obj in raw_data:
            tier = normalize_tier(str(tier_obj.get("tier", tier_obj.get("name", "?"))))
            bosses_raw = tier_obj.get("bosses", tier_obj.get("pokemon", []))
            bosses_by_tier[tier] = bosses_raw
elif isinstance(raw_data, dict):
    for tier, bosses_raw in raw_data.items():
        bosses_by_tier[normalize_tier(str(tier))] = bosses_raw if isinstance(bosses_raw, list) else []

# ── 포켓몬별 처리 ────────────────────────────────────────────────
processed: dict[str, list] = {}

for tier, bosses_raw in bosses_by_tier.items():
    tier_list = []
    for boss in bosses_raw:
        if isinstance(boss, str):
            en_name = boss
            types   = []
            is_shiny = False
        else:
            en_name  = boss.get("name", boss.get("speciesName", ""))
            raw_types = boss.get("types", [])
            # types가 [{name, image}] 형태 또는 단순 string list 형태 모두 처리
            types = []
            for t in raw_types:
                if isinstance(t, dict):
                    types.append(t.get("name", ""))
                elif isinstance(t, str):
                    types.append(t)
            is_shiny = bool(boss.get("shiny", boss.get("canBeShiny", False)))

        if not en_name:
            continue

        dex = find_dex(en_name)
        ko  = ko_name_for(en_name, dex)
        slug = pokemon_slug(en_name)

        # 타입 한국어 변환
        types_ko = " / ".join(TYPE_KO.get(t, t) for t in types) if types else ""

        tier_list.append({
            "en_name":  en_name,
            "ko_name":  ko,
            "slug":     slug,
            "dex":      dex,
            "types_ko": types_ko,
            "is_shiny": is_shiny,
        })

    processed[tier] = tier_list

# ── RAW 저장 ─────────────────────────────────────────────────────
os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT_RAW, "w", encoding="utf-8") as f:
    json.dump(processed, f, ensure_ascii=False, indent=2)
print(f"  RAW 저장: {OUTPUT_RAW}")

# ── 위키 페이지 생성 ──────────────────────────────────────────────
TIER_ORDER = ["mega", "mega_legendary", "5", "3", "1"]
all_tiers  = list(bosses_by_tier.keys())
# 정렬: 지정 순서 우선, 나머지는 뒤에
ordered = [t for t in TIER_ORDER if t in all_tiers] + \
          [t for t in all_tiers if t not in TIER_ORDER]

sections = []
total_count = 0
for tier in ordered:
    bosses = processed.get(tier, [])
    if not bosses:
        continue

    tier_label = TIER_KO.get(tier, f"{tier}성")
    rows = [
        f"### {tier_label} 레이드",
        "",
        "| 포켓몬 | 타입 | 색변 |",
        "|--------|------|------|",
    ]
    for b in bosses:
        link  = f"[[pokemon-{b['slug']}|{b['ko_name']}]]"
        shiny = "O" if b["is_shiny"] else "—"
        rows.append(f"| {link} | {b['types_ko']} | {shiny} |")

    sections.append("\n".join(rows))
    total_count += len(bosses)
    print(f"  {tier_label}: {len(bosses)}마리")

body = "\n\n".join(sections) if sections else "현재 레이드 보스 데이터를 불러오지 못했습니다."

counter_note = """## 레이드 카운터 찾기

각 레이드 보스 이름을 클릭하면 개별 포켓몬 페이지로 이동합니다.
카운터 정보는 `raid-counters-{slug}` 페이지에서 확인할 수 있습니다.
예) 뮤츠 레이드 카운터 → [[raid-counters-mewtwo|뮤츠 레이드 카운터]]"""

content = f"""---
title: "Current Raids / 현재 레이드 보스"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["raid", "current", "boss", "event"]
aliases: ["현재 레이드", "레이드 보스", "레이드 보스 목록", "raid boss", "current raids"]
summary: "현재 포켓몬 GO 레이드 보스 목록 — {TODAY} 기준, 총 {total_count}마리"
---

# 현재 레이드 보스

> 데이터 출처: [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) (LeekDuck 기반)
> 기준일: {TODAY}
> ⚠️ 레이드 보스는 자주 변경됩니다. 최신 정보는 [LeekDuck](https://leekduck.com/boss/) 에서 확인하세요.

{body}

{counter_note}

## Related Concepts
- [[type-chart]] — 타입 상성표
- [[moves-fast]] — 빠른 기술 목록
- [[moves-charged]] — 스페셜 기술 목록
"""

os.makedirs(WIKI_DIR, exist_ok=True)
with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n[완료] {OUTPUT_MD} 저장 (총 {total_count}마리)")
print("다음: python build_wiki_index.py  (인덱스 재빌드)")
