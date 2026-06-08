"""
generate_pvp_wiki.py
pvp_rankings.json → wiki/pvp-gl.md, pvp-ul.md, pvp-ml.md
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR   = ".raw"
WIKI_DIR  = "wiki"
RANKINGS  = os.path.join(RAW_DIR, "pvp_rankings.json")
TODAY     = "2026-06-05"
TOP_N     = 50

with open(RANKINGS, encoding="utf-8") as f:
    data: dict = json.load(f)

LEAGUE_WIKI = {
    "gl": "pvp-gl",
    "ul": "pvp-ul",
    "ml": "pvp-ml",
}

os.makedirs(WIKI_DIR, exist_ok=True)

for league_key, league_data in data.items():
    name_ko  = league_data["name"]
    cp_limit = league_data["cp"]
    entries  = league_data["entries"][:TOP_N]
    wiki_slug = LEAGUE_WIKI[league_key]

    rows = [
        "| 순위 | 포켓몬 | 타입 | 점수 | 빠른 기술 | 스페셜 기술 |",
        "|------|--------|------|------|----------|------------|",
    ]
    for e in entries:
        ko_name   = e["ko_name"]
        pslug     = e["pokemon_slug"]
        score     = e["score"]
        types_ko  = e["types_ko"]
        fast_ko   = e["fast_ko"]
        charged_ko = e["charged_ko"]
        link = f"[[pokemon-{pslug}|{ko_name}]]"
        rows.append(
            f"| {e['rank']} | {link} | {types_ko} | {score} "
            f"| {fast_ko} | {charged_ko} |"
        )

    table = "\n".join(rows)

    other_links = "\n".join(
        f"- [[{slug}|{data[k]['name']} 랭킹]]"
        for k, slug in LEAGUE_WIKI.items()
        if k != league_key
    )

    tags = json.dumps(
        ["pvp", "rankings", league_key, "battle-league"],
        ensure_ascii=False
    )

    content = f"""---
title: "PvP Rankings / {name_ko} 랭킹"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: {tags}
aliases: ["{name_ko}랭킹", "{name_ko} 최강", "{league_key.upper()} 랭킹", "pvp {league_key}"]
summary: "포켓몬 GO {name_ko} (CP {cp_limit:,} 이하) PvP 랭킹 상위 {TOP_N}위 — PVPoke 기준"
---

# {name_ko} PvP 랭킹

**CP 제한:** {cp_limit:,} 이하 | **출처:** PVPoke 시뮬레이션 | **상위 {TOP_N}위**

{table}

> 점수는 PVPoke 메타 시뮬레이션 기준 상대 점수 (1위 = 100점).
> 추천 기술은 PVPoke 최적 기술 세트 기준입니다. 실제 메타는 달라질 수 있습니다.

## 다른 리그

{other_links}

## Related Concepts
- [[type-chart]] — 타입 상성표
"""

    path = os.path.join(WIKI_DIR, f"{wiki_slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[{name_ko}] {path} 생성 (상위 {len(entries)}위)")

print("\n다음: python generate_go_wiki_full.py  (포켓몬 페이지에 랭킹+진화 추가)")
