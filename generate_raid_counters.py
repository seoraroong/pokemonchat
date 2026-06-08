"""
generate_raid_counters.py
PvE 기술 DPS + 타입 상성 기반 레이드 카운터 계산.
각 포켓몬(레이드 보스 후보)에 대한 wiki/raid-counters-{slug}.md 생성.
"""
import sys, json, os, re, math
sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR    = ".raw"
WIKI_DIR   = "wiki"
GM_PATH    = os.path.join(RAW_DIR, "game_master_pokemon.json")
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
MOVES_PATH = os.path.join(RAW_DIR, "pve_moves.json")
TODAY      = "2026-06-05"
TOP_N      = 15   # 카운터 상위 N마리

# ── 타입 상성 (GO 기준, 디폴트=1.0) ──────────────────────────────
# GO: SE=1.6, NVE=0.625, 무효(원작)→0.390625
SE  = 1.6
NVE = 0.625
IMM = 0.390625   # '무효' → GO에서는 이중 저항 수치

TYPE_CHART: dict[str, dict[str, float]] = {
    "normal":   {"rock": NVE, "steel": NVE, "ghost": IMM},
    "fire":     {"fire": NVE, "water": NVE, "rock": NVE, "dragon": NVE,
                 "bug": SE, "grass": SE, "ice": SE, "steel": SE},
    "water":    {"water": NVE, "grass": NVE, "dragon": NVE,
                 "fire": SE, "ground": SE, "rock": SE},
    "electric": {"electric": NVE, "grass": NVE, "dragon": NVE, "ground": IMM,
                 "water": SE, "flying": SE},
    "grass":    {"fire": NVE, "grass": NVE, "poison": NVE, "flying": NVE,
                 "bug": NVE, "dragon": NVE, "steel": NVE,
                 "water": SE, "ground": SE, "rock": SE},
    "ice":      {"water": NVE, "ice": NVE, "steel": NVE,
                 "grass": SE, "ground": SE, "flying": SE, "dragon": SE},
    "fighting": {"poison": NVE, "psychic": NVE, "flying": NVE,
                 "bug": NVE, "fairy": NVE, "ghost": IMM,
                 "normal": SE, "rock": SE, "steel": SE, "ice": SE, "dark": SE},
    "poison":   {"poison": NVE, "ground": NVE, "rock": NVE, "ghost": NVE, "steel": IMM,
                 "grass": SE, "fairy": SE},
    "ground":   {"grass": NVE, "bug": NVE, "flying": IMM,
                 "fire": SE, "electric": SE, "poison": SE, "rock": SE, "steel": SE},
    "flying":   {"electric": NVE, "rock": NVE, "steel": NVE,
                 "fighting": SE, "bug": SE, "grass": SE},
    "psychic":  {"psychic": NVE, "steel": NVE, "dark": IMM,
                 "fighting": SE, "poison": SE},
    "bug":      {"fire": NVE, "fighting": NVE, "flying": NVE, "ghost": NVE,
                 "steel": NVE, "fairy": NVE,
                 "grass": SE, "psychic": SE, "dark": SE},
    "rock":     {"fighting": NVE, "ground": NVE, "steel": NVE,
                 "fire": SE, "ice": SE, "flying": SE, "bug": SE},
    "ghost":    {"normal": IMM, "dark": NVE,
                 "psychic": SE, "ghost": SE},
    "dragon":   {"steel": NVE, "fairy": IMM,
                 "dragon": SE},
    "dark":     {"fighting": NVE, "dark": NVE, "fairy": NVE,
                 "psychic": SE, "ghost": SE},
    "steel":    {"fire": NVE, "water": NVE, "electric": NVE, "steel": NVE,
                 "ice": SE, "rock": SE, "fairy": SE},
    "fairy":    {"fire": NVE, "poison": NVE, "steel": NVE,
                 "fighting": SE, "dragon": SE, "dark": SE},
}

TYPE_KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}

def type_eff(atk_type: str, def_types: list[str]) -> float:
    """공격 타입이 수비 타입(들)에 대한 총 배율."""
    mult = 1.0
    chart = TYPE_CHART.get(atk_type, {})
    for def_type in def_types:
        if def_type and def_type != "none":
            mult *= chart.get(def_type, 1.0)
    return mult

def get_weaknesses(def_types: list[str]) -> list[tuple[float, str]]:
    """보스 타입에 약한 공격 타입 목록 (배율 내림차순)."""
    results = []
    for atk_type in TYPE_CHART:
        m = type_eff(atk_type, def_types)
        if m > 1.0:
            results.append((m, atk_type))
    return sorted(results, reverse=True)

def pokemon_slug(en_name: str) -> str:
    s = en_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9-]", "", s)

# ── 포켓몬 이름에서 기술 이름으로 매핑 ──────────────────────────────
# game_master: 기술명은 "Thunder Shock" 형태 → move_id로 변환
def name_to_move_id(name: str) -> str:
    return name.upper().replace(" ", "_")

# ── 데이터 로드 ────────────────────────────────────────────────────
with open(GM_PATH, encoding="utf-8") as f:
    gm: dict[str, dict] = json.load(f)
with open(NAMES_PATH, encoding="utf-8") as f:
    names: dict[str, dict] = json.load(f)
with open(MOVES_PATH, encoding="utf-8") as f:
    pve_moves: dict[str, dict] = json.load(f)

# 기술 한국어 이름 (위키 링크용)
def move_ko_link(move_id: str) -> str:
    m = pve_moves.get(move_id, {})
    ko = m.get("ko_name", "")
    slug = m.get("slug", move_id.lower().replace("_", "-"))
    if ko and slug:
        return f"[[move-{slug}|{ko}]]"
    return move_id.replace("_", " ").title()

# ── 카운터 스코어 계산 ────────────────────────────────────────────
def best_effective_dps(attacker: dict, boss_types: list[str]) -> tuple[float, str]:
    """공격자가 보스에 대한 최고 유효 DPS와 기술명 반환."""
    atk_stat = attacker["atk"]
    all_moves = (
        [name_to_move_id(m) for m in attacker.get("fast_moves", [])]
        + [name_to_move_id(m) for m in attacker.get("charged_moves", [])]
    )
    boss_types_clean = [t for t in boss_types if t and t != "none"]

    best_dps  = 0.0
    best_move = ""

    attacker_types = [attacker.get("type1", ""), attacker.get("type2") or ""]

    for mid in all_moves:
        move = pve_moves.get(mid)
        if not move:
            continue
        mtype = move.get("type", "")
        dps   = move.get("dps_pve", 0)
        if not dps:
            continue

        mult = type_eff(mtype, boss_types_clean)
        stab = 1.2 if mtype in attacker_types else 1.0
        eff_dps = dps * mult * stab

        if eff_dps > best_dps:
            best_dps  = eff_dps
            best_move = mid

    # ATK 스탯 가중치 (제곱근으로 스케일)
    score = math.sqrt(atk_stat) * best_dps
    return score, best_move


# ── 레이드 보스 선별: CP_40 > 1800 또는 레전더리 세대 범위 ─────────
LEGENDARY_DEX = set(range(144, 152)) | set(range(243, 252)) | set(range(377, 386)) | \
    set(range(480, 494)) | set(range(638, 650)) | set(range(716, 722)) | \
    set(range(785, 810)) | set(range(888, 899)) | {905} | set(range(1001, 1026))

MYTHICAL_DEX  = {151, 251, 385, 386, 490, 491, 492, 493, 494,
                 647, 648, 649, 719, 720, 721, 801, 802, 807, 808, 809, 893, 900}

os.makedirs(WIKI_DIR, exist_ok=True)
created = 0

# 전체 공격자 풀 (스탯 있는 모든 포켓몬)
all_attackers = [
    {"dex": int(k), **v}
    for k, v in gm.items()
    if v.get("atk") and v.get("fast_moves")
]

for dex_str, boss_data in sorted(gm.items(), key=lambda x: int(x[0])):
    dex = int(dex_str)
    nr  = names.get(dex_str)
    if not nr:
        continue

    en  = nr["en_name"]
    ko  = nr["ko_name"]
    gen = nr["gen"]
    t1  = boss_data.get("type1", "")
    t2  = boss_data.get("type2") or ""
    if t2 == "none":
        t2 = ""

    boss_types_clean = [t for t in [t1, t2] if t and t != "none"]

    cp40 = boss_data.get("cp_40", 0)
    is_legendary = dex in LEGENDARY_DEX or dex in MYTHICAL_DEX

    # 레이드 보스 필터: CP_40 > 1800 OR 레전더리/미식컬
    if cp40 < 1800 and not is_legendary:
        continue

    # 약점 정보
    weaknesses = get_weaknesses(boss_types_clean)
    weak_str   = ", ".join(
        f"{TYPE_KO.get(t, t)} ({'%.2f' % m}×)" for m, t in weaknesses
    )

    # 카운터 계산
    scored = []
    for attacker in all_attackers:
        if attacker["dex"] == dex:
            continue
        score, best_move = best_effective_dps(attacker, boss_types_clean)
        if score > 0:
            scored.append((score, attacker, best_move))
    scored.sort(key=lambda x: x[0], reverse=True)
    top_counters = scored[:TOP_N]

    # 타입 표시
    type_ko_str = TYPE_KO.get(t1, t1)
    if t2:
        type_ko_str += f" / {TYPE_KO.get(t2, t2)}"

    # 카운터 테이블
    rows = [
        "| 순위 | 포켓몬 | 추천 기술 | DPS 배율 |",
        "|------|--------|----------|---------|",
    ]
    for rank, (score, att, best_mid) in enumerate(top_counters, 1):
        att_dex = att["dex"]
        att_nr  = names.get(str(att_dex), {})
        att_ko  = att_nr.get("ko_name", att.get("species_id", ""))
        att_en  = att_nr.get("en_name", "")
        att_slug = pokemon_slug(att_en) if att_en else att.get("species_id", "")
        move_link = move_ko_link(best_mid)
        score_str = f"{score:.1f}"
        rows.append(f"| {rank} | [[pokemon-{att_slug}|{att_ko}]] | {move_link} | {score_str} |")

    table = "\n".join(rows)

    # 다른 관련 링크
    boss_slug = f"pokemon-{pokemon_slug(en)}"
    tags = json.dumps(["raid", "counter", f"type-{t1}"] + ([f"type-{t2}"] if t2 else []), ensure_ascii=False)

    content = f"""---
title: "Raid Counters / {ko} 레이드 카운터"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: {tags}
aliases: ["{ko} 레이드", "{ko} 카운터", "{en.lower()} raid counter"]
summary: "{ko} ({type_ko_str}) 레이드 카운터 상위 {TOP_N}위 — PvE DPS 기반"
---

# {ko} 레이드 카운터

**타입:** {type_ko_str} | **약점:** {weak_str or "없음"}

## 추천 카운터 상위 {TOP_N}위

{table}

> 점수 = √(공격스탯) × PvE DPS × 타입 배율 × STAB
> 메가 진화 미포함. 실제 전투에서는 레벨, 개체값, 날씨 보너스에 따라 달라집니다.

## Related Concepts
- [[{boss_slug}|{ko}]] — 포켓몬 상세 정보
- [[type-chart]] — 타입 상성표
- [[current-raids]] — 현재 레이드 보스
"""

    slug = f"raid-counters-{pokemon_slug(en)}"
    path = os.path.join(WIKI_DIR, f"{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    created += 1
    print(f"  [{created:4d}] #{dex:04d} {ko:16s} ({type_ko_str}) — {len(top_counters)}개 카운터")

print(f"\n[완료] 레이드 카운터 페이지 {created}개 생성")
print("다음: python fetch_current_raids.py && python build_wiki_index.py")
