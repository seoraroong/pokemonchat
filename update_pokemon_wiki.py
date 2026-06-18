"""
update_pokemon_wiki.py
포켓몬 GO 데이터로 위키 페이지 업데이트:
  1. 약점/저항 섹션 추가 (아직 없는 모든 페이지)
  2. 구형 summary("기본 스탯 합계") → GO 스탯 기준으로 교체
"""
import json, re
from pathlib import Path
from datetime import date

WIKI_DIR = Path("wiki")
TODAY = date.today().isoformat()

# ── 데이터 로드 ────────────────────────────────────────────────────
gm    = json.loads(Path(".raw/game_master_pokemon.json").read_text(encoding="utf-8"))
names = json.loads(Path(".raw/go_all_names.json").read_text(encoding="utf-8"))
te    = json.loads(Path(".raw/type_effectiveness.json").read_text(encoding="utf-8"))

# en_name(소문자) → (dex, ko_name)
en2info: dict[str, tuple[int, str]] = {
    v["en_name"].lower(): (int(k), v["ko_name"])
    for k, v in names.items()
}

TYPE_KO = {
    "normal": "노말", "fire": "불꽃", "water": "물", "electric": "전기",
    "grass": "풀", "ice": "얼음", "fighting": "격투", "poison": "독",
    "ground": "땅", "flying": "비행", "psychic": "에스퍼", "bug": "벌레",
    "rock": "바위", "ghost": "고스트", "dragon": "드래곤", "dark": "악",
    "steel": "강철", "fairy": "페어리",
}

def calc_weaknesses(t1: str, t2: str | None) -> dict[str, list]:
    result: dict[str, list] = {"weak": [], "resist": [], "immune": []}
    for atk_t in te:
        def eff(dt: str) -> float:
            d = te.get(dt, {})
            if atk_t in d.get("double_damage_from", []): return 2.0
            if atk_t in d.get("no_damage_from",     []): return 0.0
            if atk_t in d.get("half_damage_from",   []): return 0.5
            return 1.0
        combined = eff(t1) * (eff(t2) if t2 else 1.0)
        label = TYPE_KO.get(atk_t, atk_t)
        if combined >= 4:
            result["weak"].append(f"{label}(×4)")
        elif combined >= 2:
            result["weak"].append(label)
        elif combined == 0:
            result["immune"].append(label)
        elif combined <= 0.25:
            result["resist"].append(f"{label}(×¼)")
        elif combined < 1:
            result["resist"].append(label)
    return result

def make_weakness_section(t1: str, t2: str | None) -> str:
    w = calc_weaknesses(t1, t2)
    rows = f"| 약점 | {', '.join(w['weak']) or '없음'} |\n"
    rows += f"| 저항 | {', '.join(w['resist']) or '없음'} |"
    if w["immune"]:
        rows += f"\n| 무효 | {', '.join(w['immune'])} |"
    return f"""\n### 타입 상성 (GO 기준)\n\n| 구분 | 타입 |\n|------|------|\n{rows}\n"""

def slug_to_en(slug: str) -> str:
    """pokemon-mr-mime → mr mime, pokemon-ho-oh → ho oh"""
    return slug.replace("pokemon-", "").replace("-", " ")

# ── 처리 ──────────────────────────────────────────────────────────
pages = sorted(WIKI_DIR.glob("pokemon-*.md"))
updated_weakness = 0
updated_summary  = 0
skipped          = 0

for page_path in pages:
    slug   = page_path.stem
    en_raw = slug_to_en(slug)

    # dex 조회 (하이픈→공백 변환 후 시도, 실패하면 다양한 변형 시도)
    info = en2info.get(en_raw)
    if not info:
        # mr-mime → mr. mime 등 특수 케이스
        for variant in [en_raw.replace(" ", ". "), en_raw.replace(" ", "'")]:
            info = en2info.get(variant)
            if info:
                break
    if not info:
        skipped += 1
        continue

    dex, ko_name = info
    gm_entry = gm.get(str(dex))
    if not gm_entry:
        skipped += 1
        continue

    content = page_path.read_text(encoding="utf-8")

    # ── 1. 약점 섹션 없으면 추가 ───────────────────────────────────
    if "타입 상성 (GO 기준)" not in content and "포켓몬 GO 스탯" in content:
        t1     = gm_entry.get("type1", "")
        t2_raw = gm_entry.get("type2")
        t2     = t2_raw if (t2_raw and t2_raw != "none") else None
        weakness_md = make_weakness_section(t1, t2)

        # "### 기술 풀 (GO)" 앞에 삽입, 없으면 GO 스탯 섹션 끝에 추가
        if "### 기술 풀 (GO)" in content:
            content = content.replace(
                "### 기술 풀 (GO)",
                weakness_md + "### 기술 풀 (GO)",
                1,
            )
        else:
            # ## References 앞에 삽입
            if "## References" in content:
                content = content.replace("## References", weakness_md + "## References", 1)
            else:
                content = content.rstrip() + "\n" + weakness_md
        updated_weakness += 1

    # ── 2. summary가 구형이면 GO 기준으로 교체 ────────────────────
    if re.search(r'summary:.*(?:기본 스탯 합계|/ none)', content):
        cp40 = gm_entry.get("cp_40", 0)
        t1   = gm_entry.get("type1", "")
        t2_raw = gm_entry.get("type2")
        t2     = t2_raw if (t2_raw and t2_raw != "none") else None
        type_ko = TYPE_KO.get(t1, t1)
        if t2:
            type_ko += " / " + TYPE_KO.get(t2, t2)
        dex_str = str(dex).zfill(3)
        new_summary = f'summary: "#{dex_str} {ko_name} ({type_ko}) — GO 최대 CP: {cp40:,}"'
        content = re.sub(r'summary: ".*(?:기본 스탯 합계|/ none).*"', new_summary, content)
        updated_summary += 1

    # ── 3. modified 날짜 갱신 (변경된 경우만) ──────────────────────
    if updated_weakness or updated_summary:
        content = re.sub(r'(modified: )\d{4}-\d{2}-\d{2}', f'\\g<1>{TODAY}', content)
        page_path.write_text(content, encoding="utf-8")

total = updated_weakness + updated_summary
print(f"완료: 약점 섹션 추가 {updated_weakness}개 / summary 교체 {updated_summary}개 / 건너뜀 {skipped}개")
print(f"총 {total}개 페이지 업데이트")
