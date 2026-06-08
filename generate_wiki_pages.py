# Wiki page generator for PokéAPI Gen 1 data
import sys
import json
import os

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = ".raw"
WIKI_DIR = "wiki"
os.makedirs(WIKI_DIR, exist_ok=True)

TODAY = "2026-06-05"

TYPE_KO = {
    "normal": "노말", "fighting": "격투", "flying": "비행", "poison": "독",
    "ground": "땅", "rock": "바위", "bug": "벌레", "ghost": "고스트",
    "steel": "강철", "fire": "불꽃", "water": "물", "grass": "풀",
    "electric": "전기", "psychic": "에스퍼", "ice": "얼음", "dragon": "드래곤",
    "dark": "악", "fairy": "페어리",
}

with open(os.path.join(RAW_DIR, "type_effectiveness.json"), encoding="utf-8") as f:
    type_data = json.load(f)

with open(os.path.join(RAW_DIR, "gen1_pokemon.json"), encoding="utf-8") as f:
    pokemons = json.load(f)

# ── evolution line mapping ──────────────────────────────────────
# Find the root of each evolution line
name_to_pokemon = {p["name"]: p for p in pokemons}

def find_evo_root(name, visited=None):
    if visited is None:
        visited = set()
    if name in visited:
        return name
    visited.add(name)
    p = name_to_pokemon.get(name)
    if p and p.get("evolves_from") and p["evolves_from"] in name_to_pokemon:
        return find_evo_root(p["evolves_from"], visited)
    return name

for p in pokemons:
    p["evo_root"] = find_evo_root(p["name"])

# Find evolutions (who evolves into what)
evolves_to = {p["name"]: [] for p in pokemons}
for p in pokemons:
    if p.get("evolves_from") and p["evolves_from"] in evolves_to:
        evolves_to[p["evolves_from"]].append(p["name"])

count = 0

# ── 1. Type pages ───────────────────────────────────────────────
print("[type] generating 18 type pages...")
for tname, tdata in type_data.items():
    tko = TYPE_KO.get(tname, tname)
    slug = f"type-{tname}"
    fname = os.path.join(WIKI_DIR, f"{slug}.md")

    def fmt_types(lst):
        if not lst:
            return "없음"
        return ", ".join(f"[[type-{t}|{TYPE_KO.get(t, t)}]]" for t in lst)

    content = f"""---
title: "{tname.capitalize()} 타입 / {tko} 타입"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: [pokemon, type, type-chart, gen1]
aliases: ["{tko}", "{tname}"]
summary: "포켓몬 {tko} 타입의 공격/방어 상성 관계"
---

# {tname.capitalize()} 타입 / {tko} 타입

## Definition / 정의
포켓몬의 18개 타입 중 하나인 **{tko} 타입**의 공격 및 방어 상성 정보입니다.
포켓몬 GO 레이드/배틀에서 타입 상성은 데미지 배율에 직접 영향을 줍니다.

## 공격 상성 (이 타입 기술 사용 시)

| 효과 | 배율 | 대상 타입 |
|------|------|----------|
| 효과 굉장 | ×2 | {fmt_types(tdata['double_damage_to'])} |
| 효과 별로 | ×0.5 | {fmt_types(tdata['half_damage_to'])} |
| 효과 없음 | ×0 | {fmt_types(tdata['no_damage_to'])} |

## 방어 상성 (이 타입 포켓몬이 받는 데미지)

| 효과 | 배율 | 공격 타입 |
|------|------|----------|
| 약점 (2배 피해) | ×2 | {fmt_types(tdata['double_damage_from'])} |
| 저항 (0.5배 피해) | ×0.5 | {fmt_types(tdata['half_damage_from'])} |
| 무효 (0배 피해) | ×0 | {fmt_types(tdata['no_damage_from'])} |

## Related Concepts / 관련 개념
- [[type-chart]] — 전체 18타입 상성표
- [[pokedex-gen1]] — 1세대 포켓몬 목록

## References / 참고
- Source: PokéAPI v2 type endpoint
- Hash: `2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5`
"""
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    count += 1
    print(f"  OK {fname}")

# ── 2. Type chart hub ───────────────────────────────────────────
print("[hub] generating type-chart.md...")

rows = []
for tname, tko in TYPE_KO.items():
    td = type_data.get(tname, {})
    weak_to = ", ".join(TYPE_KO.get(t, t) for t in td.get("double_damage_from", []))
    resist   = ", ".join(TYPE_KO.get(t, t) for t in td.get("half_damage_from", []))
    immune   = ", ".join(TYPE_KO.get(t, t) for t in td.get("no_damage_from", []))
    strong   = ", ".join(TYPE_KO.get(t, t) for t in td.get("double_damage_to", []))
    rows.append(f"| [[type-{tname}\\|{tko}]] | {strong or '—'} | {weak_to or '—'} | {resist or '—'} | {immune or '—'} |")

type_table = "\n".join(rows)

with open(os.path.join(WIKI_DIR, "type-chart.md"), "w", encoding="utf-8") as f:
    f.write(f"""---
title: "포켓몬 타입 상성표 / Type Chart"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: [pokemon, type, type-chart, reference]
aliases: ["타입 상성", "type chart", "상성표"]
summary: "포켓몬 18개 타입의 공격/방어 상성을 한눈에 볼 수 있는 허브 페이지"
---

# 포켓몬 타입 상성표

포켓몬 GO 레이드/배틀 시 데미지 배율 기준:
- **효과 굉장**: ×1.6 (GO 기준, 메인 시리즈 ×2)
- **효과 별로**: ×0.625 (GO 기준, 메인 시리즈 ×0.5)
- **효과 없음**: ×0.390625 (GO 이중 저항)

> 포켓몬 GO는 메인 시리즈와 배율이 다릅니다. 아래 표는 **유효/무효 관계**를 기준으로 합니다.

## 전체 타입 상성표

| 타입 | 효과 굉장 (공격) | 약점 (방어) | 저항 (방어) | 무효 (방어) |
|------|----------------|------------|------------|------------|
{type_table}

## 각 타입 상세 페이지
{chr(10).join(f"- [[type-{t}|{ko}]] 타입" for t, ko in TYPE_KO.items())}

## References
- Source: PokéAPI v2
""")
count += 1
print("  OK wiki/type-chart.md")

# ── 3. Individual Pokémon pages ─────────────────────────────────
print("[pokemon] generating 151 individual pages...")

for p in pokemons:
    slug = f"pokemon-{p['name']}"
    fname = os.path.join(WIKI_DIR, f"{slug}.md")

    name_ko = p.get("name_ko") or p["name"]
    types_en = p.get("types", [])
    types_ko = "/".join(TYPE_KO.get(t, t) for t in types_en)
    type_links = ", ".join(f"[[type-{t}|{TYPE_KO.get(t, t)}]]" for t in types_en)

    stats = p.get("stats", {})
    total = sum(stats.values())

    evo_from = p.get("evolves_from")
    evo_to   = evolves_to.get(p["name"], [])
    evo_root = p.get("evo_root", p["name"])

    evo_from_str = f"[[pokemon-{evo_from}|{name_to_pokemon[evo_from].get('name_ko', evo_from)}]]" if evo_from and evo_from in name_to_pokemon else "없음"
    evo_to_str   = ", ".join(f"[[pokemon-{e}|{name_to_pokemon[e].get('name_ko', e)}]]" for e in evo_to) if evo_to else "없음"

    legendary_str = "전설 포켓몬" if p.get("is_legendary") else ("신화 포켓몬" if p.get("is_mythical") else "일반 포켓몬")
    tags = ["pokemon", "gen1"] + [f"type-{t}" for t in types_en] + [f"evo-line-{evo_root}"]
    if p.get("is_legendary"): tags.append("legendary")
    if p.get("is_mythical"):  tags.append("mythical")

    flavor = p.get("flavor_text", "")
    flavor_ko = p.get("flavor_text_ko", "")
    height_m = p.get("height_dm", 0) / 10
    weight_kg = p.get("weight_hg", 0) / 10

    content = f"""---
title: "{p['name'].capitalize()} / {name_ko}"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: {json.dumps(tags, ensure_ascii=False)}
aliases: ["{name_ko}", "{p['name']}"]
summary: "#{p['id']:03d} {name_ko} ({types_ko} 타입) — 기본 스탯 합계 {total}"
evolution_line: "{evo_root}"
---

# {p['name'].capitalize()} / {name_ko}

## Definition / 정의
**{name_ko}** (#{p['id']:03d})는 {legendary_str}로, {type_links} 타입입니다.
{f'"{flavor_ko}"' if flavor_ko else (f'"{flavor}"' if flavor else '')}

## 기본 정보

| 항목 | 값 |
|------|-----|
| 도감 번호 | #{p['id']:03d} |
| 영문 이름 | {p['name'].capitalize()} |
| 타입 | {type_links} |
| 키 | {height_m:.1f}m |
| 몸무게 | {weight_kg:.1f}kg |
| 분류 | {legendary_str} |
| 포획률 | {p.get('capture_rate', '?')} |

## 기본 스탯 (Base Stats)

| 스탯 | 수치 |
|------|------|
| HP | {stats.get('hp', '?')} |
| 공격 | {stats.get('attack', '?')} |
| 방어 | {stats.get('defense', '?')} |
| 특수공격 | {stats.get('special-attack', '?')} |
| 특수방어 | {stats.get('special-defense', '?')} |
| 스피드 | {stats.get('speed', '?')} |
| **합계** | **{total}** |

## 진화 정보

| 항목 | 포켓몬 |
|------|--------|
| 진화 전 | {evo_from_str} |
| 진화 후 | {evo_to_str} |
| 계열 루트 | [[pokemon-{evo_root}]] |

## 특성 (Abilities)
{chr(10).join(f'- {a}' for a in p.get('abilities', []))}

## Related Concepts / 관련 개념
{chr(10).join(f'- [[type-{t}|{TYPE_KO.get(t, t)} 타입]] — {name_ko}의 타입' for t in types_en)}
- [[pokedex-gen1]] — 1세대 포켓몬 목록
- [[type-chart]] — 타입 상성표

## References
- Source: PokéAPI v2 pokemon/{p['id']}
- Hash: `bb8096ad5a0b2c74200879a8a90f450de39cf76898c0fd158d85011302b5f3d5`
"""
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    count += 1
    print(f"  OK #{p['id']:03d} {p['name']} / {name_ko}")

# ── 4. Pokedex Gen1 hub ─────────────────────────────────────────
print("[hub] generating pokedex-gen1.md...")
poke_rows = "\n".join(
    f"| #{p['id']:03d} | [[pokemon-{p['name']}\\|{p.get('name_ko', p['name'])}]] | {p['name'].capitalize()} | "
    f"{'/'.join(TYPE_KO.get(t, t) for t in p.get('types', []))} | "
    f"{'전설' if p.get('is_legendary') else ('신화' if p.get('is_mythical') else '')} |"
    for p in pokemons
)

with open(os.path.join(WIKI_DIR, "pokedex-gen1.md"), "w", encoding="utf-8") as f:
    f.write(f"""---
title: "1세대 포켓덱스 / Gen 1 Pokédex"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: [pokemon, gen1, reference, pokedex]
aliases: ["1세대", "Gen 1", "관동지방"]
summary: "1세대 포켓몬 151마리의 인덱스 — 각 포켓몬 개별 페이지로 연결"
---

# 1세대 포켓덱스 / Gen 1 Pokédex

관동지방(Kanto) 1세대 포켓몬 151마리 목록입니다.

## 포켓몬 목록

| # | 한국어 | 영어 | 타입 | 비고 |
|---|--------|------|------|------|
{poke_rows}

## 관련
- [[type-chart]] — 타입 상성표
- Source: PokéAPI v2
""")
count += 1
print("  OK wiki/pokedex-gen1.md")

# ── 5. Article overview page ────────────────────────────────────
print("[article] generating import article...")
with open(os.path.join(WIKI_DIR, f"2026-06-05-pokeapi-gen1-import.md"), "w", encoding="utf-8") as f:
    f.write(f"""---
title: "PokéAPI Gen 1 데이터 임포트"
type: article
language: ko
created: {TODAY}
modified: {TODAY}
tags: [pokemon, gen1, pokeapi, import, data-source]
summary: "PokéAPI에서 1세대 포켓몬 151마리 스탯 및 18개 타입 상성 데이터를 가져와 위키에 구축한 기록"
source_hashes:
  - "2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5"
  - "bb8096ad5a0b2c74200879a8a90f450de39cf76898c0fd158d85011302b5f3d5"
status: published
---

# PokéAPI Gen 1 데이터 임포트

## Summary / 요약
PokéAPI(https://pokeapi.co)의 공개 REST API를 통해 1세대 포켓몬 151마리의 기본 스탯, 타입, 진화 정보와 18개 타입의 공격/방어 상성 데이터를 수집해 위키에 구축했습니다.

## Content / 내용

### 수집 데이터
- **type_effectiveness.json** — 18개 타입 × 6개 관계 (공격/방어 × 2배/0.5배/무효)
- **gen1_pokemon.json** — 151마리 × 스탯(HP/공/방/특공/특방/스피드) + 타입 + 진화 + 한국어/영어 이름

### 생성된 위키 페이지
- 타입 개념 페이지 18개: `type-fire.md`, `type-water.md` 등
- 타입 상성 허브: `type-chart.md`
- 포켓몬 개념 페이지 151개: `pokemon-pikachu.md` 등
- 포켓덱스 허브: `pokedex-gen1.md`

### 한계
- 포켓몬 GO 전용 스탯(CP 계수, IV 등)은 포함되지 않음 → LeekDuck 등 후속 ingestion 필요
- 2세대 이후 포켓몬 미포함 → 추가 ingestion 계획

## Key Takeaways / 핵심
- 타입 상성은 [[type-chart]]에서 한눈에 확인 가능
- 각 포켓몬은 `evolution_line` 태그로 계열 그룹화 가능
- 포켓몬 GO에서 배틀/레이드 시 타입 배율은 메인 시리즈와 다름 (×1.6 / ×0.625)

## 출처
| 소스 | 섹션/페이지 | URL |
|------|------------|-----|
| PokéAPI | /api/v2/type | https://pokeapi.co/api/v2/type |
| PokéAPI | /api/v2/pokemon | https://pokeapi.co/api/v2/pokemon |
| PokéAPI | /api/v2/pokemon-species | https://pokeapi.co/api/v2/pokemon-species |

## Related / 관련
- [[type-chart]] — 타입 상성 허브
- [[pokedex-gen1]] — 포켓몬 목록
""")
count += 1
print("  OK wiki/2026-06-05-pokeapi-gen1-import.md")

print(f"\n[done] 총 {count}개 페이지 생성 완료 -> {WIKI_DIR}/")
