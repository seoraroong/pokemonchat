"""
fetch_go_moves.py
PVPoke moves.json 파싱 + PokéAPI 한국어 이름 수집.
출력: .raw/go_moves.json
"""
import sys, json, os, re, time

sys.stdout.reconfigure(encoding="utf-8")

import requests

RAW_DIR    = ".raw"
OUTPUT     = os.path.join(RAW_DIR, "go_moves.json")
PVPOKE_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster/moves.json"
POKEAPI    = "https://pokeapi.co/api/v2"
HEADERS    = {"User-Agent": "pogo-wiki-builder/1.0"}

# ── 타입 한국어 ───────────────────────────────────────────────────
TYPE_KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}

# ── 1. PVPoke moves.json 다운로드 ─────────────────────────────────
print("PVPoke moves.json 다운로드...")
r = requests.get(PVPOKE_URL, timeout=30, headers=HEADERS)
r.raise_for_status()
pvpoke_moves: list[dict] = r.json()
print(f"  → {len(pvpoke_moves)}개 기술 로드")

# ── 2. PokéAPI 전체 기술 목록 (이름→슬러그 인덱스) ────────────────
print("PokéAPI 기술 목록 수집...")
r2 = requests.get(f"{POKEAPI}/move?limit=2000", timeout=30, headers=HEADERS)
r2.raise_for_status()
pokeapi_moves = r2.json()["results"]

# "thunder-shock" 형태의 슬러그 → url 매핑
name_to_url: dict[str, str] = {}
for m in pokeapi_moves:
    name_to_url[m["name"]] = m["url"]      # e.g. "thunder-shock" → url

def pvpoke_name_to_slug(name: str) -> str:
    """'Thunder Shock' → 'thunder-shock'"""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def fetch_ko_name(url: str, retry: int = 3) -> str:
    for attempt in range(retry):
        try:
            r = requests.get(url, timeout=20, headers=HEADERS)
            r.raise_for_status()
            for n in r.json().get("names", []):
                if n["language"]["name"] == "ko":
                    return n["name"]
        except Exception:
            if attempt < retry - 1:
                time.sleep(1.5 ** attempt)
    return ""

# ── 3. 파싱 + 한국어 이름 수집 ────────────────────────────────────
results: dict[str, dict] = {}

# 기존 캐시 로드 (중단 후 재실행 대비)
if os.path.exists(OUTPUT):
    with open(OUTPUT, encoding="utf-8") as f:
        results = json.load(f)
    print(f"  기존 캐시 {len(results)}개 로드")

todo = [m for m in pvpoke_moves if m["moveId"] not in results]
print(f"  신규 처리: {len(todo)}개\n")

for i, move in enumerate(todo):
    move_id      = move["moveId"]
    en_name      = move["name"]
    type_        = move.get("type", "")
    power        = move.get("power", 0)
    energy_gain  = move.get("energyGain", 0)
    energy_cost  = move.get("energy", 0)
    cooldown_ms  = move.get("cooldown", 0)
    turns        = move.get("turns", 1)
    archetype    = move.get("archetype", "")
    buffs        = move.get("buffs", [])
    buff_target  = move.get("buffTarget", "")
    buff_chance  = move.get("buffApplyChance", "")

    is_fast = energy_gain > 0 and energy_cost == 0

    # PvP 지표
    if is_fast and turns > 0:
        dpt = round(power / turns, 2)    # 턴당 데미지
        ept = round(energy_gain / turns, 2)  # 턴당 에너지
    else:
        dpt = ept = 0

    dpe = round(power / energy_cost, 2) if energy_cost > 0 else 0  # 에너지당 데미지

    # PvE 지표 (쿨다운 기반)
    if cooldown_ms > 0:
        dps_pve = round(power / (cooldown_ms / 1000), 2)
        eps_pve = round(energy_gain / (cooldown_ms / 1000), 2) if is_fast else 0
    else:
        dps_pve = eps_pve = 0

    # 슬러그
    slug = pvpoke_name_to_slug(en_name)

    # 한국어 이름 — PokéAPI
    ko_name = ""
    api_url = name_to_url.get(slug)
    if api_url:
        ko_name = fetch_ko_name(api_url)
        time.sleep(0.15)

    if not ko_name:
        ko_name = en_name  # fallback

    # 버프/디버프 설명
    buff_desc = ""
    if buffs:
        stat_map = {0: "공격", 1: "방어", 2: "특공", 3: "특방"}
        parts = []
        for idx, val in enumerate(buffs):
            if val != 0 and idx < len(stat_map):
                target = "상대" if buff_target == "opponent" else "자신"
                sign   = "+" if val > 0 else ""
                parts.append(f"{target} {stat_map[idx]} {sign}{val}")
        if parts and buff_chance:
            chance = float(buff_chance) * 100
            buff_desc = f"{' / '.join(parts)} ({chance:.0f}% 확률)"

    results[move_id] = {
        "move_id":      move_id,
        "slug":         slug,
        "en_name":      en_name,
        "ko_name":      ko_name,
        "type":         type_,
        "type_ko":      TYPE_KO.get(type_, type_),
        "category":     "fast" if is_fast else "charged",
        "power":        power,
        "energy_gain":  energy_gain,
        "energy_cost":  energy_cost,
        "turns":        turns,
        "cooldown_ms":  cooldown_ms,
        "dpt":          dpt,
        "ept":          ept,
        "dpe":          dpe,
        "dps_pve":      dps_pve,
        "eps_pve":      eps_pve,
        "archetype":    archetype,
        "buff_desc":    buff_desc,
    }

    cat = "빠른기술" if is_fast else "스페셜"
    print(f"  [{i+1}/{len(todo)}] {cat:6s} {en_name:28s} → {ko_name}")

    if (i + 1) % 50 == 0:
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  [중간 저장] {len(results)}개")

# ── 4. 저장 ───────────────────────────────────────────────────────
os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

fast_cnt    = sum(1 for v in results.values() if v["category"] == "fast")
charged_cnt = sum(1 for v in results.values() if v["category"] == "charged")
print(f"\n[완료] {OUTPUT} 저장")
print(f"  빠른 기술: {fast_cnt}개 / 스페셜 기술: {charged_cnt}개")
print("다음: python generate_move_wiki.py")
