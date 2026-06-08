"""
generate_move_wiki.py
go_moves.json → wiki/move-{slug}.md 개별 페이지 + 허브 페이지 생성.
"""
import sys, json, os

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR  = ".raw"
WIKI_DIR = "wiki"
MOVES_PATH = os.path.join(RAW_DIR, "go_moves.json")
TODAY = "2026-06-05"

# ── 데이터 로드 ────────────────────────────────────────────────────
with open(MOVES_PATH, encoding="utf-8") as f:
    moves: dict[str, dict] = json.load(f)

os.makedirs(WIKI_DIR, exist_ok=True)

# ── 개별 기술 페이지 생성 ──────────────────────────────────────────
created = updated = 0

for move_id, m in moves.items():
    slug      = m["slug"]
    en_name   = m["en_name"]
    ko_name   = m["ko_name"]
    type_     = m["type"]
    type_ko   = m["type_ko"]
    category  = m["category"]
    cat_ko    = "빠른 기술" if category == "fast" else "스페셜 기술"
    power     = m["power"]
    e_gain    = m["energy_gain"]
    e_cost    = m["energy_cost"]
    turns     = m["turns"]
    cooldown  = m["cooldown_ms"]
    dpt       = m["dpt"]
    ept       = m["ept"]
    dpe       = m["dpe"]
    dps_pve   = m["dps_pve"]
    eps_pve   = m["eps_pve"]
    archetype = m["archetype"]
    buff_desc = m["buff_desc"]

    tags = json.dumps(
        ["move", category, f"type-{type_}", "move-data"],
        ensure_ascii=False
    )

    if category == "fast":
        summary = (
            f"{type_ko} 타입 빠른 기술 — "
            f"위력: {power}, DPT: {dpt}, EPT: {ept}"
        )
    else:
        summary = (
            f"{type_ko} 타입 스페셜 기술 — "
            f"위력: {power}, 에너지 소모: {e_cost}, DPE: {dpe}"
        )

    # PvP 스탯 테이블
    if category == "fast":
        pvp_table = (
            "| 항목 | 수치 |\n"
            "|------|------|\n"
            f"| 타입 | {type_ko} |\n"
            f"| 분류 | {cat_ko} |\n"
            f"| 위력 (PvP) | {power} |\n"
            f"| 에너지 획득 | {e_gain} |\n"
            f"| 턴 수 | {turns} |\n"
            f"| DPT (턴당 데미지) | {dpt} |\n"
            f"| EPT (턴당 에너지) | {ept} |\n"
            f"| 애니메이션 쿨다운 | {cooldown}ms |\n"
        )
        pve_section = ""  # PvE 전용 섹션 없음 (PvP 위력값 기반이라 참고만)
    else:
        pvp_table = (
            "| 항목 | 수치 |\n"
            "|------|------|\n"
            f"| 타입 | {type_ko} |\n"
            f"| 분류 | {cat_ko} |\n"
            f"| 위력 (PvP) | {power} |\n"
            f"| 에너지 소모 | {e_cost} |\n"
            f"| DPE (에너지당 데미지) | {dpe} |\n"
        )
        pve_section = ""

    archetype_line = f"\n**유형(Archetype):** {archetype}\n" if archetype else ""
    buff_line = f"\n**효과:** {buff_desc}\n" if buff_desc else ""

    content = f"""---
title: "{en_name} / {ko_name}"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: {tags}
aliases: ["{ko_name}", "{en_name.lower()}"]
summary: "{summary}"
---

# {en_name} / {ko_name}

## PvP 스탯 (리그 배틀)

{pvp_table}
{archetype_line}{buff_line}
> 위 수치는 PVPoke 게임마스터 기준 PvP 수치입니다.

## Related Concepts / 관련 개념
- [[moves-fast]] — 전체 빠른 기술 목록
- [[moves-charged]] — 전체 스페셜 기술 목록
- [[type-{type_}]] — {type_ko} 타입 상세
"""

    path = os.path.join(WIKI_DIR, f"move-{slug}.md")
    exists = os.path.exists(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if exists:
        updated += 1
    else:
        created += 1

print(f"개별 기술 페이지: 신규 {created}개, 업데이트 {updated}개")

# ── 빠른 기술 허브 ────────────────────────────────────────────────
fast_moves = sorted(
    [m for m in moves.values() if m["category"] == "fast"],
    key=lambda x: (x["type"], x["ko_name"])
)

rows = [
    "| 기술 이름 | 타입 | 위력 | 에너지 | 턴 | DPT | EPT |",
    "|----------|------|------|--------|-----|-----|-----|",
]
for m in fast_moves:
    link = f"[[move-{m['slug']}\\|{m['ko_name']}]]"
    rows.append(
        f"| {link} | {m['type_ko']} | {m['power']} "
        f"| +{m['energy_gain']} | {m['turns']} "
        f"| {m['dpt']} | {m['ept']} |"
    )

fast_hub = f"""---
title: "Fast Moves / 빠른 기술 목록"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["move", "fast", "hub", "move-data"]
aliases: ["빠른기술목록", "빠른 기술 전체"]
summary: "포켓몬 GO 빠른 기술 전체 목록 — {len(fast_moves)}개"
---

# 빠른 기술 목록 (Fast Moves)

포켓몬 GO PvP 기준 빠른 기술 {len(fast_moves)}개.

- **DPT**: 턴당 데미지 (Damage Per Turn)
- **EPT**: 턴당 에너지 획득 (Energy Per Turn)

{chr(10).join(rows)}

## Related Concepts
- [[moves-charged]] — 스페셜 기술 목록
- [[type-chart]] — 타입 상성표
"""

path = os.path.join(WIKI_DIR, "moves-fast.md")
with open(path, "w", encoding="utf-8") as f:
    f.write(fast_hub)
print(f"빠른 기술 허브: {path}")

# ── 스페셜 기술 허브 ──────────────────────────────────────────────
charged_moves = sorted(
    [m for m in moves.values() if m["category"] == "charged"],
    key=lambda x: (x["type"], x["ko_name"])
)

rows2 = [
    "| 기술 이름 | 타입 | 위력 | 에너지 | DPE | 효과 |",
    "|----------|------|------|--------|-----|------|",
]
for m in charged_moves:
    link = f"[[move-{m['slug']}\\|{m['ko_name']}]]"
    rows2.append(
        f"| {link} | {m['type_ko']} | {m['power']} "
        f"| -{m['energy_cost']} | {m['dpe']} "
        f"| {m['buff_desc'] or '—'} |"
    )

charged_hub = f"""---
title: "Charged Moves / 스페셜 기술 목록"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: ["move", "charged", "hub", "move-data"]
aliases: ["스페셜기술목록", "스페셜 기술 전체", "차지기술목록"]
summary: "포켓몬 GO 스페셜 기술 전체 목록 — {len(charged_moves)}개"
---

# 스페셜 기술 목록 (Charged Moves)

포켓몬 GO PvP 기준 스페셜 기술 {len(charged_moves)}개.

- **DPE**: 에너지당 데미지 (Damage Per Energy)
- 에너지 수치: 사용에 필요한 에너지 (마이너스 = 소모량)

{chr(10).join(rows2)}

## Related Concepts
- [[moves-fast]] — 빠른 기술 목록
- [[type-chart]] — 타입 상성표
"""

path = os.path.join(WIKI_DIR, "moves-charged.md")
with open(path, "w", encoding="utf-8") as f:
    f.write(charged_hub)
print(f"스페셜 기술 허브: {path}")

# ── 타입별 기술 허브 (선택: 상위 타입만) ──────────────────────────
type_groups: dict[str, list] = {}
for m in moves.values():
    type_groups.setdefault(m["type"], []).append(m)

print(f"\n[완료] 총 {len(moves)}개 기술 위키 생성")
print(f"  빠른 기술: {len(fast_moves)}개")
print(f"  스페셜 기술: {len(charged_moves)}개")
print("다음: python build_wiki_index.py")
