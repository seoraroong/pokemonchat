"""
fetch_eggs_and_rockets.py
ScrapedDuck eggs.json + rocketLineups.json 수집 후 위키 페이지 생성.

생성 페이지:
  wiki/eggs-1km.md, eggs-2km.md, eggs-5km.md,
  eggs-7km.md, eggs-10km.md, eggs-12km.md
  wiki/eggs-hub.md         (전체 알 요약)
  wiki/rocket-grunt-{type}.md  (타입별 그런트)
  wiki/rocket-leaders.md   (Giovanni / Cliff / Arlo / Sierra)
"""
import sys, json, os, re
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR   = ".raw"
WIKI_DIR  = "wiki"
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
TODAY     = "2026-06-08"
HEADERS   = {"User-Agent": "pogo-wiki-builder/1.0"}

EGGS_URL    = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.json"
ROCKETS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/rocketLineups.json"

TYPE_KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}
RARITY_STR = {1: "★ 흔함", 3: "★★★ 드묾", 4: "★★★★ 레어"}

# ── 보조 데이터 ────────────────────────────────────────────────────
GM_PATH = os.path.join(RAW_DIR, "game_master_pokemon.json")

with open(NAMES_PATH, encoding="utf-8") as f:
    names_data: dict[str, dict] = json.load(f)
with open(GM_PATH, encoding="utf-8") as f:
    gm_data: dict[str, dict] = json.load(f)

# dex → 타입
dex_to_types: dict[int, tuple] = {
    int(k): (v.get("type1",""), v.get("type2",""))
    for k, v in gm_data.items()
}

en_lower_to_info: dict[str, dict] = {}
for dex_str, nd in names_data.items():
    dex = int(dex_str)
    t1, t2 = dex_to_types.get(dex, ("",""))
    t2_clean = t2 if t2 and t2 != "none" else ""
    t_str = TYPE_KO.get(t1, t1)
    if t2_clean:
        t_str += " / " + TYPE_KO.get(t2_clean, t2_clean)
    en_lower_to_info[nd["en_name"].lower()] = {
        "ko": nd["ko_name"], "dex": dex, "type_str": t_str
    }

def poke_link(en_name: str) -> str:
    """영문 이름 → [[pokemon-slug|한국어]] 위키링크"""
    info = en_lower_to_info.get(en_name.lower())
    slug = en_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    ko = info["ko"] if info else en_name
    return f"[[pokemon-{slug}|{ko}]]"

def poke_type_str(en_name: str) -> str:
    """영문 이름 → 한국어 타입 문자열"""
    info = en_lower_to_info.get(en_name.lower())
    return info["type_str"] if info else "—"

def types_ko(types_list: list) -> str:
    out = []
    for t in types_list:
        if isinstance(t, dict):
            out.append(TYPE_KO.get(t.get("name",""), t.get("name","")))
        elif isinstance(t, str):
            out.append(TYPE_KO.get(t, t))
    return " / ".join(out) if out else "—"

os.makedirs(WIKI_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
# 1. 알 목록
# ══════════════════════════════════════════════════════════════════
print("eggs.json 다운로드...")
r = requests.get(EGGS_URL, timeout=30, headers=HEADERS)
r.raise_for_status()
eggs_raw: list[dict] = r.json()
with open(os.path.join(RAW_DIR, "eggs.json"), "w", encoding="utf-8") as f:
    json.dump(eggs_raw, f, ensure_ascii=False, indent=2)
print(f"  → {len(eggs_raw)}개 포켓몬")

# 알 종류별 분류
KM_ORDER = ["1 km", "2 km", "5 km", "7 km", "10 km", "12 km"]
by_km: dict[str, list] = {km: [] for km in KM_ORDER}
for e in eggs_raw:
    km = e.get("eggType", "")
    if km in by_km:
        by_km[km].append(e)

# 알 종류 → slug 매핑
KM_SLUG = {"1 km": "1km", "2 km": "2km", "5 km": "5km",
           "7 km": "7km", "10 km": "10km", "12 km": "12km"}
KM_LABEL = {"1 km": "1km 알", "2 km": "2km 알", "5 km": "5km 알",
            "7 km": "7km 알 (선물 알)", "10 km": "10km 알", "12 km": "12km 알 (어드벤처 싱크)"}

hub_rows = ["| 알 종류 | 포켓몬 수 | 페이지 |",
            "|--------|---------|-------|"]

for km in KM_ORDER:
    entries = by_km[km]
    if not entries:
        continue
    slug = KM_SLUG[km]
    label = KM_LABEL[km]

    # rarity로 정렬: 레어(4) 먼저 → 드묾(3) → 흔함(1)
    entries.sort(key=lambda x: -x.get("rarity", 0))

    rows = ["| 포켓몬 | 타입 | 희귀도 | AS전용 | 색변 |",
            "|--------|------|--------|--------|------|"]
    for e in entries:
        link    = poke_link(e["name"])
        t       = poke_type_str(e["name"])
        rarity  = RARITY_STR.get(e.get("rarity", 0), "—")
        as_only = "O" if e.get("isAdventureSync") else "—"
        shiny   = "O" if e.get("canBeShiny") else "—"
        rows.append(f"| {link} | {t} | {rarity} | {as_only} | {shiny} |")

    table = "\n".join(rows)
    content = f"""---
title: "Eggs {km} / {label}"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["egg", "hatch", "eggs-{slug}"]
aliases: ["{label}", "{km} 알", "{slug} 알", "알 {km}"]
summary: "{label} 부화 가능 포켓몬 목록 — {TODAY} 기준, {len(entries)}종"
---

# {label} 부화 포켓몬

> 데이터 출처: [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) (LeekDuck 기반)
> 기준일: {TODAY}
> ⚠️ 알 풀은 이벤트에 따라 자주 변경됩니다.
{"> 어드벤처 싱크(AS) 전용 알: 주간 50km 또는 25km 달성 보상" if slug == "12km" else ""}
{"> 선물 알: 친구에게서 받은 선물로 획득" if slug == "7km" else ""}

{table}

> **희귀도:** ★ 흔함 / ★★★ 드묾 / ★★★★ 레어
> **AS전용:** 어드벤처 싱크 달성 보상 알에서만 등장
> **색변:** 색이 다른(Shiny) 포켓몬 포획 가능 여부

## Related Concepts
- [[eggs-hub]] — 전체 알 목록 요약
"""
    path = os.path.join(WIKI_DIR, f"eggs-{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    hub_rows.append(f"| [[eggs-{slug}|{label}]] | {len(entries)}종 | [[eggs-{slug}]] |")
    print(f"  eggs-{slug}.md ({len(entries)}종)")

# 허브 페이지
hub_content = f"""---
title: "Eggs Hub / 알 부화 전체 목록"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["egg", "hatch", "hub"]
aliases: ["알 목록", "알 부화", "egg", "eggs", "부화", "알"]
summary: "포켓몬 GO 전체 알 종류별 부화 목록 요약 — {TODAY} 기준"
---

# 포켓몬 GO 알 부화 목록

> 기준일: {TODAY}

{chr(10).join(hub_rows)}

## 알 종류 안내

| 알 종류 | 획득 방법 |
|--------|---------|
| 1km / 2km / 5km | 포켓스톱·체육관 스핀 |
| 7km | 친구 선물 |
| 10km | 포켓스톱·체육관 스핀 (드묾) |
| 12km | 로켓단 간부(Cliff/Arlo/Sierra/Giovanni) 격파 |
| AS 전용 | 어드벤처 싱크 주간 달성 보상 |

## Related Concepts
- [[rocket-leaders]] — 로켓단 간부 라인업 (12km 알 보상)
- [[current-raids]] — 현재 레이드 보스
"""
with open(os.path.join(WIKI_DIR, "eggs-hub.md"), "w", encoding="utf-8") as f:
    f.write(hub_content)
print("  eggs-hub.md")

# ══════════════════════════════════════════════════════════════════
# 2. 로켓단 라인업
# ══════════════════════════════════════════════════════════════════
print("\nrocketLineups.json 다운로드...")
r2 = requests.get(ROCKETS_URL, timeout=30, headers=HEADERS)
r2.raise_for_status()
rockets_raw: list[dict] = r2.json()
with open(os.path.join(RAW_DIR, "rocket_lineups.json"), "w", encoding="utf-8") as f:
    json.dump(rockets_raw, f, ensure_ascii=False, indent=2)
print(f"  → {len(rockets_raw)}개 라인업")

LEADERS = {"Giovanni", "Cliff", "Arlo", "Sierra"}

def slot_table(slot_list: list) -> str:
    """슬롯 포켓몬 목록 → '| 포켓몬 | 타입 | 포획 | 색변 |' 테이블"""
    rows = ["| 포켓몬 | 타입 | 포획 | 색변 |",
            "|--------|------|------|------|"]
    for p in slot_list:
        link   = poke_link(p["name"])
        t      = types_ko(p.get("types", []))
        enc    = "O" if p.get("isEncounter") else "—"
        shiny  = "O" if p.get("canBeShiny") else "—"
        rows.append(f"| {link} | {t} | {enc} | {shiny} |")
    return "\n".join(rows)

def weakness_hint(types_list: list) -> str:
    """타입 약점 간단 힌트 (1~2줄)"""
    from_types = [t.lower() if isinstance(t, str) else t.get("name","").lower()
                  for t in types_list]
    weak_map = {
        "normal": "격투", "fire": "물/땅/바위", "water": "풀/전기",
        "electric": "땅", "grass": "불꽃/얼음/비행/독/벌레",
        "ice": "불꽃/격투/바위/강철", "fighting": "비행/에스퍼/페어리",
        "poison": "땅/에스퍼", "ground": "물/풀/얼음",
        "flying": "전기/얼음/바위", "psychic": "벌레/고스트/악",
        "bug": "불꽃/비행/바위", "rock": "물/풀/격투/땅/강철",
        "ghost": "고스트/악", "dragon": "얼음/드래곤/페어리",
        "dark": "격투/벌레/페어리", "steel": "불꽃/격투/땅",
        "fairy": "독/강철",
    }
    hints = [f"{TYPE_KO.get(t,t)} 약점: {weak_map.get(t,'—')}" for t in from_types if t in weak_map]
    return "\n".join(f"> {h}" for h in hints) if hints else ""

# ── 리더/보스 페이지 (통합) ──────────────────────────────────────
leader_sections = []
for entry in rockets_raw:
    name = entry["name"]
    if name not in LEADERS:
        continue
    title_ko = {"Giovanni": "조반니 (로켓단 보스)", "Cliff": "클리프",
                 "Arlo": "아를로", "Sierra": "시에라"}.get(name, name)
    s1 = slot_table(entry.get("firstPokemon", []))
    s2 = slot_table(entry.get("secondPokemon", []))
    s3 = slot_table(entry.get("thirdPokemon", []))
    note = ""
    if name == "Giovanni":
        note = "\n> 🎁 격파 시 **12km 슈퍼 로켓 알** 획득 가능 (최초 격파 한정)\n"
    else:
        note = "\n> 🎁 격파 시 **12km 슈퍼 로켓 알** 획득 가능\n"
    leader_sections.append(f"""## {title_ko}
{note}
### 슬롯 1 (고정)
{s1}

### 슬롯 2 (랜덤)
{s2}

### 슬롯 3 (랜덤)
{s3}
""")

leaders_content = f"""---
title: "Rocket Leaders / 로켓단 간부 라인업"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["rocket", "leader", "giovanni", "cliff", "arlo", "sierra"]
aliases: ["로켓단 간부", "Giovanni", "조반니", "클리프", "아를로", "시에라",
          "rocket leader", "로켓단 보스"]
summary: "Team GO Rocket 간부(Cliff/Arlo/Sierra) 및 보스 Giovanni 라인업 — {TODAY} 기준"
---

# 로켓단 간부 라인업

> 데이터 출처: [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) (LeekDuck 기반)
> 기준일: {TODAY}
> **포획(O):** 슬롯 3 포켓몬은 격파 후 포획 가능. 색변(Shiny) 여부도 표시.
> 각 슬롯은 목록 중 **랜덤 1마리** 등장.

{"".join(leader_sections)}
## Related Concepts
- [[eggs-hub]] — 12km 슈퍼 로켓 알 부화 목록
- [[rocket-grunts]] — 타입별 그런트 라인업
"""
with open(os.path.join(WIKI_DIR, "rocket-leaders.md"), "w", encoding="utf-8") as f:
    f.write(leaders_content)
print("  rocket-leaders.md")

# ── 그런트 페이지 (타입별 통합) ──────────────────────────────────
grunt_sections: dict[str, list] = {}  # type → [sections]
no_type_entries = []

for entry in rockets_raw:
    name = entry["name"]
    if name in LEADERS:
        continue
    raw_type = entry.get("type", "").lower().strip()
    if not raw_type:
        no_type_entries.append(entry)
        continue
    grunt_sections.setdefault(raw_type, []).append(entry)

# 타입별로 개별 페이지 생성
grunt_pages_created = []
for gtype, entries in sorted(grunt_sections.items()):
    type_ko = TYPE_KO.get(gtype, gtype)
    sections_md = []
    for entry in entries:
        gender = "여성" if "Female" in entry["name"] else "남성"
        s1 = slot_table(entry.get("firstPokemon", []))
        s2 = slot_table(entry.get("secondPokemon", []))
        s3 = slot_table(entry.get("thirdPokemon", []))
        sections_md.append(f"""### {entry['name']} ({gender})

**슬롯 1:**
{s1}

**슬롯 2:**
{s2}

**슬롯 3:**
{s3}
""")
    first_pokes = entries[0].get("firstPokemon", [])
    weak_hint = weakness_hint([gtype])
    page = f"""---
title: "Rocket Grunt {gtype.title()} / {type_ko}타입 그런트"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["rocket", "grunt", "type-{gtype}"]
aliases: ["{type_ko} 그런트", "{type_ko}타입 그런트", "{gtype} grunt",
          "로켓단 {type_ko}", "{gtype}타입 로켓단"]
summary: "{type_ko}타입 로켓단 그런트 라인업 — {TODAY} 기준"
---

# {type_ko}타입 그런트 라인업

> 기준일: {TODAY}
{weak_hint}

{"".join(sections_md)}
## Related Concepts
- [[type-{gtype}]] — {type_ko} 타입 정보
- [[rocket-leaders]] — 로켓단 간부 라인업
- [[rocket-grunts]] — 전체 그런트 허브
"""
    slug = f"rocket-grunt-{gtype}"
    with open(os.path.join(WIKI_DIR, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(page)
    grunt_pages_created.append((slug, type_ko))
    print(f"  {slug}.md ({len(entries)}종 그런트)")

# 그런트 허브 페이지
grunt_hub_rows = ["| 타입 | 페이지 |", "|------|-------|"]
for slug, type_ko in grunt_pages_created:
    grunt_hub_rows.append(f"| {type_ko} | [[{slug}|{type_ko}타입 그런트]] |")

# 특수 그런트 섹션 (타입 없는 것들)
no_type_md = []
for entry in no_type_entries:
    s1 = slot_table(entry.get("firstPokemon", []))
    s2 = slot_table(entry.get("secondPokemon", []))
    s3 = slot_table(entry.get("thirdPokemon", []))
    no_type_md.append(f"""### {entry['name']}

**슬롯 1:**
{s1}

**슬롯 2:**
{s2}

**슬롯 3:**
{s3}
""")

grunt_hub_content = f"""---
title: "Rocket Grunts / 로켓단 그런트 전체 목록"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["rocket", "grunt", "hub"]
aliases: ["로켓단 그런트", "그런트", "grunt", "rocket grunt", "로켓단"]
summary: "Team GO Rocket 타입별 그런트 라인업 허브 — {TODAY} 기준"
---

# 로켓단 그런트 라인업

> 기준일: {TODAY}
> 각 슬롯에서 목록 중 **랜덤 1마리** 등장. 슬롯 3 포켓몬은 격파 후 포획 가능.

## 타입별 그런트

{chr(10).join(grunt_hub_rows)}

## 특수 그런트

{"".join(no_type_md) if no_type_md else "없음"}

## Related Concepts
- [[rocket-leaders]] — 간부(Cliff / Arlo / Sierra / Giovanni)
- [[eggs-hub]] — 알 부화 목록
"""
with open(os.path.join(WIKI_DIR, "rocket-grunts.md"), "w", encoding="utf-8") as f:
    f.write(grunt_hub_content)
print("  rocket-grunts.md")

print(f"\n[완료] 알 페이지 {len(KM_ORDER)+1}개, 로켓단 페이지 {len(grunt_pages_created)+2}개 생성")
print("다음: python build_wiki_index.py")
