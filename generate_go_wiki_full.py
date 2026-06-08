"""
generate_go_wiki_full.py
game_master_pokemon.json + go_all_names.json 을 합쳐
전체 GO 포켓몬 위키 페이지 생성/업데이트.
- Gen1 기존 페이지: 'GO 스탯' 섹션 추가/교체
- Gen2+: 새 페이지 생성
출력: wiki/pokemon-{slug}.md
"""
import sys, json, os, re

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR     = ".raw"
WIKI_DIR    = "wiki"
GM_PATH     = os.path.join(RAW_DIR, "game_master_pokemon.json")
KR_PATH     = os.path.join(RAW_DIR, "go_all_names.json")
MOVES_PATH   = os.path.join(RAW_DIR, "go_moves.json")
EVO_PATH     = os.path.join(RAW_DIR, "go_evolution.json")
RANKINGS_PATH= os.path.join(RAW_DIR, "pvp_rankings.json")
TODAY        = "2026-06-05"

# ── 데이터 로드 ───────────────────────────────────────────────────
with open(GM_PATH, encoding="utf-8") as f:
    gm: dict[str, dict] = json.load(f)
with open(KR_PATH, encoding="utf-8") as f:
    names: dict[str, dict] = json.load(f)

# ── 진화 체인 ──────────────────────────────────────────────────────
_EVO: dict[str, dict] = {}
if os.path.exists(EVO_PATH):
    with open(EVO_PATH, encoding="utf-8") as f:
        _EVO = json.load(f)

# ── PvP 랭킹: dex → {gl: rank, ul: rank, ml: rank} ───────────────
_PVP_RANK: dict[int, dict[str, int]] = {}
if os.path.exists(RANKINGS_PATH):
    with open(RANKINGS_PATH, encoding="utf-8") as f:
        _pvp_raw = json.load(f)
    for league_key, league_data in _pvp_raw.items():
        for entry in league_data["entries"]:
            dex = entry["dex"]
            if not dex:
                continue  # 매핑 안 된 변형폼 제외
            existing = _PVP_RANK.setdefault(dex, {})
            # 동일 dex 중 최고 순위(낮은 번호)만 저장
            if league_key not in existing or entry["rank"] < existing[league_key]:
                existing[league_key] = entry["rank"]

# ── 기술 한국어 이름 매핑 (en_name → {ko_name, slug}) ─────────────
_MOVE_MAP: dict[str, dict] = {}
if os.path.exists(MOVES_PATH):
    with open(MOVES_PATH, encoding="utf-8") as f:
        _moves_raw = json.load(f)
    for m in _moves_raw.values():
        _MOVE_MAP[m["en_name"]] = {"ko": m["ko_name"], "slug": m["slug"]}

def move_ko(en: str) -> str:
    """'Thunder Shock' → '[[move-thunder-shock|전기쇼크]]'  (매핑 없으면 영어 그대로)"""
    info = _MOVE_MAP.get(en)
    if info:
        return f"[[move-{info['slug']}|{info['ko']}]]"
    return en

# ── 타입 한국어 매핑 ──────────────────────────────────────────────
TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기",
    "grass": "풀", "ice": "얼음", "fighting": "격투", "poison": "독",
    "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악",
    "steel": "강철", "fairy": "페어리",
}

def type_ko(t: str) -> str:
    return TYPE_KO.get(t, t)

def type_str(t1: str, t2: str | None) -> str:
    if t2 and t2 != "none":
        return f"{type_ko(t1)} / {type_ko(t2)}"
    return type_ko(t1)

def type_tags(t1: str, t2: str | None) -> list[str]:
    tags = [f"type-{t1}"]
    if t2:
        tags.append(f"type-{t2}")
    return tags

def pokemon_slug(dex: int, en_name: str) -> str:
    """#025 Pikachu → pokemon-pikachu"""
    slug = en_name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return f"pokemon-{slug}"

def evo_line_key(en_name: str) -> str:
    return en_name.lower().replace(" ", "-").replace("'", "").replace(".", "")


# ── 섹션 빌더 ─────────────────────────────────────────────────────
GO_MARKER = "## 포켓몬 GO 스탯"

def _evo_link(dex: int) -> str:
    """dex → '[[pokemon-slug|한국어이름]]' (이름 없으면 영어명)"""
    nr = names.get(str(dex))
    if nr:
        slug = pokemon_slug(dex, nr["en_name"]).replace("pokemon-", "")
        return f"[[pokemon-{slug}|{nr['ko_name']}]]"
    return f"#{dex}"


def build_go_section(data: dict, names_row: dict) -> str:
    dex   = data["dex"]
    atk   = data["atk"]
    def_  = data["def"]
    sta   = data["sta"]
    cp40  = data["cp_40"]
    cp50  = data["cp_50"]
    buddy = data["buddy_km"]
    t1    = data["type1"]
    t2    = data.get("type2") or None
    if t2 == "none":
        t2 = None
    fast    = data.get("fast_moves",    [])
    charged = data.get("charged_moves", [])
    e_fast    = data.get("elite_fast",    [])
    e_charged = data.get("elite_charged", [])

    fast_str    = ", ".join(move_ko(m) for m in fast)    or "—"
    charged_str = ", ".join(move_ko(m) for m in charged) or "—"
    e_fast_str    = ("  *(커뮤니티 데이/전용: " + ", ".join(move_ko(m) for m in e_fast) + ")*")    if e_fast    else ""
    e_charged_str = ("  *(커뮤니티 데이/전용: " + ", ".join(move_ko(m) for m in e_charged) + ")*") if e_charged else ""

    type_display = type_str(t1, t2)

    # PvP 순위 (상위 500위 이내만 표시)
    ranks = _PVP_RANK.get(dex, {})
    LEAGUE_NAMES = {"gl": "슈퍼리그 (GL 1500)", "ul": "하이퍼리그 (UL 2500)", "ml": "마스터리그 (ML)"}
    LEAGUE_WIKI  = {"gl": "pvp-gl", "ul": "pvp-ul", "ml": "pvp-ml"}
    pvp_rows = []
    for lk, lname in LEAGUE_NAMES.items():
        r = ranks.get(lk)
        if r and r <= 500:
            pvp_rows.append(f"| PvP 순위 ({lname}) | [[{LEAGUE_WIKI[lk]}\\|{r}위]] |")

    lines = [
        GO_MARKER,
        "",
        "| 항목 | 수치 |",
        "|------|------|",
        f"| 공격 (GO) | {atk} |",
        f"| 방어 (GO) | {def_} |",
        f"| 체력 (GO) | {sta} |",
        f"| 최대 CP (Lv.40) | {cp40:,} |",
        f"| 최대 CP (Lv.50) | {cp50:,} |",
        f"| 타입 | {type_display} |",
        f"| 버디 거리 | {buddy}km |",
    ] + pvp_rows + [
        "",
        "### 기술 풀 (GO)",
        f"- **빠른 기술:** {fast_str}{e_fast_str}",
        f"- **스페셜 기술:** {charged_str}{e_charged_str}",
    ]

    # 진화 체인
    evo = _EVO.get(str(dex))
    if evo:
        lines += ["", "### 진화 체인"]
        from_dex = evo.get("evolves_from_dex")
        if from_dex:
            lines.append(f"- **진화 전:** {_evo_link(from_dex)}")
        evo_to = evo.get("evolves_to", [])
        if evo_to:
            parts = []
            for ev in evo_to:
                link = _evo_link(ev["dex"])
                candy = ev.get("candy", 0)
                item_ko = ev.get("item_ko", "")
                req = f"사탕 {candy}개" if candy else ""
                if item_ko:
                    req += (" + " if req else "") + item_ko
                parts.append(f"{link} ({req})" if req else link)
            lines.append(f"- **진화 후:** {', '.join(parts)}")

    # 변형 폼 (알로라/가라르 등) 있으면 추가
    variants = data.get("variant_forms", {})
    if variants:
        lines += ["", "### 변형 폼", "| 폼 | 공격 | 방어 | 체력 | 최대 CP(40) |",
                  "|-----|------|------|------|------------|"]
        for form_name, fv in variants.items():
            lines.append(
                f"| {form_name.upper()} | {fv['atk']} | {fv['def']} | {fv['sta']} | {fv['cp_40']:,} |"
            )

    lines.append("")
    return "\n".join(lines)


def build_new_page(dex: int, data: dict, names_row: dict) -> str:
    en  = names_row["en_name"]
    ko  = names_row["ko_name"]
    gen = names_row["gen"]
    t1  = data["type1"]
    t2  = data.get("type2")
    cp40 = data["cp_40"]

    type_display = type_str(t1, t2)
    type_tag_list = type_tags(t1, t2)
    evo_line = evo_line_key(en)
    slug_plain = evo_line  # e.g. "pikachu"

    tags = ["pokemon", f"gen{gen}"] + type_tag_list + [f"evo-line-{evo_line}"]

    buddy = data["buddy_km"]
    parent = data.get("parent", "")
    evolutions = data.get("evolutions", [])

    # 진화 정보
    if parent:
        parent_display = f"[[pokemon-{parent.lower().replace(' ', '-')}|{parent.title()}]]"
    else:
        parent_display = "없음 (1단계 진화)"

    evo_lines = []
    for ev in evolutions:
        to_slug = ev["to"].lower().replace(" ", "-").replace("'", "")
        candy   = ev["candy"]
        item    = ev["item"]
        req = f"{candy} 사탕"
        if item:
            req += f" + {item.replace('_', ' ').title()}"
        evo_lines.append(f"| 진화 후 | [[pokemon-{to_slug}\\|{ev['to']}]] | {req} |")

    if not evo_lines:
        evo_lines = ["| 진화 후 | 없음 | — |"]

    evo_table = "\n".join(evo_lines)
    go_section = build_go_section(data, names_row)

    return f"""---
title: "{en} / {ko}"
type: concept
language: ko
created: {TODAY}
modified: {TODAY}
tags: {json.dumps(tags, ensure_ascii=False)}
aliases: ["{ko}", "{en.lower()}"]
summary: "#{dex:03d} {ko} ({type_display}) — GO 최대 CP: {cp40:,}"
evolution_line: "{evo_line}"
---

# {en} / {ko}

## 기본 정보

| 항목 | 값 |
|------|-----|
| 도감 번호 | #{dex:03d} |
| 영문 이름 | {en} |
| 타입 | {type_display} |
| 세대 | {gen}세대 |

{go_section}

## 진화 정보

| 항목 | 포켓몬 | 조건 |
|------|--------|------|
| 진화 전 | {parent_display} | — |
{evo_table}

## Related Concepts / 관련 개념
- [[type-chart]] — 타입 상성표
- [[pokedex-gen{gen}]] — {gen}세대 포켓몬 목록

## References
- Source: PokeMiners GAME_MASTER + PokéAPI
"""


def update_existing_page(path: str, data: dict, names_row: dict) -> bool:
    """기존 Gen1 페이지에 GO 스탯 섹션 추가/교체."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    go_section = build_go_section(data, names_row)

    if GO_MARKER in content:
        # 기존 섹션 교체
        pattern = re.compile(
            r"## 포켓몬 GO 스탯\n.*?(?=\n## |\Z)",
            re.DOTALL,
        )
        new_content = pattern.sub(go_section.rstrip("\n"), content, count=1)
    else:
        # ## References 직전 삽입
        if "## References" in content:
            new_content = content.replace("## References", go_section + "## References", 1)
        else:
            new_content = content.rstrip("\n") + "\n\n" + go_section

    if new_content == content:
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


# ── 메인 처리 ─────────────────────────────────────────────────────
os.makedirs(WIKI_DIR, exist_ok=True)

created = updated = skipped = 0
missing_names: list[int] = []

for dex_str, data in sorted(gm.items(), key=lambda x: int(x[0])):
    dex = int(dex_str)
    names_row = names.get(dex_str)
    if not names_row:
        missing_names.append(dex)
        continue

    en  = names_row["en_name"]
    gen = names_row["gen"]
    slug = pokemon_slug(dex, en)
    path = os.path.join(WIKI_DIR, f"{slug}.md")

    if os.path.exists(path):
        # 기존 페이지 업데이트 (GO 스탯 섹션)
        changed = update_existing_page(path, data, names_row)
        status = "UPDATE" if changed else "SKIP"
        if changed:
            updated += 1
        else:
            skipped += 1
    else:
        # 새 페이지 생성
        content = build_new_page(dex, data, names_row)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        status = "NEW"
        created += 1

    ko = names_row["ko_name"]
    print(f"  {status:6s}  #{dex:04d} {en:24s} ({ko}) — {slug}.md")

print(f"""
[완료]
  신규 생성:  {created:4d}개
  GO 스탯 추가: {updated:4d}개
  변경 없음:  {skipped:4d}개
""")

if missing_names:
    print(f"[주의] 이름 데이터 없음 ({len(missing_names)}개): {missing_names[:10]}...")

print("다음: python build_wiki_index.py  (인덱스 재빌드)")
