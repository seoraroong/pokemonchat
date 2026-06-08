"""
fetch_pvp_rankings.py
PVPoke GL/UL/ML PvP 랭킹 다운로드.
출력: .raw/pvp_rankings.json
"""
import sys, json, os, re
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR    = ".raw"
OUTPUT     = os.path.join(RAW_DIR, "pvp_rankings.json")
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
MOVES_PATH = os.path.join(RAW_DIR, "go_moves.json")
GM_PATH    = os.path.join(RAW_DIR, "game_master_pokemon.json")
HEADERS    = {"User-Agent": "pogo-wiki-builder/1.0"}

LEAGUES = {
    "gl": {"name": "슈퍼리그",   "cp": 1500,  "slug": "1500"},
    "ul": {"name": "하이퍼리그", "cp": 2500,  "slug": "2500"},
    "ml": {"name": "마스터리그", "cp": 10000, "slug": "10000"},
}
BASE_URL = (
    "https://raw.githubusercontent.com/pvpoke/pvpoke/master"
    "/src/data/rankings/all/overall/rankings-{slug}.json"
)

TYPE_KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}

# ── 보조 데이터 ────────────────────────────────────────────────────
with open(NAMES_PATH, encoding="utf-8") as f:
    names_data = json.load(f)
with open(MOVES_PATH, encoding="utf-8") as f:
    moves_raw = json.load(f)
with open(GM_PATH, encoding="utf-8") as f:
    gm_data = json.load(f)

# speciesId → dex (game_master_pokemon.json 기준)
sid_to_dex: dict[str, int] = {
    v["species_id"]: int(k)
    for k, v in gm_data.items()
    if v.get("species_id")
}

dex_to_names: dict[int, dict] = {v["dex"]: v for v in names_data.values()}
dex_to_types: dict[int, dict] = {
    int(k): {"type1": v.get("type1",""), "type2": v.get("type2")}
    for k, v in gm_data.items()
}

move_id_to_ko:   dict[str, str] = {m["move_id"]: m["ko_name"] for m in moves_raw.values()}
move_id_to_slug: dict[str, str] = {m["move_id"]: m["slug"]    for m in moves_raw.values()}
move_id_cat:     dict[str, str] = {m["move_id"]: m["category"] for m in moves_raw.values()}

def move_link(move_id: str) -> str:
    ko   = move_id_to_ko.get(move_id)
    slug = move_id_to_slug.get(move_id)
    if ko and slug:
        return f"[[move-{slug}|{ko}]]"
    return move_id.replace("_FAST", "").replace("_", " ").title()

def pokemon_slug_from_en(en: str) -> str:
    s = en.lower().replace(" ", "-").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9-]", "", s)

# ── 다운로드 & 처리 ────────────────────────────────────────────────
results: dict = {}

for league_key, info in LEAGUES.items():
    url = BASE_URL.format(slug=info["slug"])
    print(f"[{info['name']}] 다운로드...")
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    raw: list[dict] = r.json()
    print(f"  → {len(raw)}개 포켓몬")

    entries = []
    for rank, entry in enumerate(raw, 1):
        species_id = entry.get("speciesId", "")
        en_name    = entry.get("speciesName", "")
        score      = round(entry.get("score", 0), 1)

        # dex 조회
        dex = sid_to_dex.get(species_id, 0)
        ko_name = dex_to_names.get(dex, {}).get("ko_name", en_name) if dex else en_name

        # 타입
        t_data  = dex_to_types.get(dex, {})
        t1      = t_data.get("type1", "")
        t2      = t_data.get("type2")
        types_ko = TYPE_KO.get(t1, t1)
        if t2 and t2 != "none":
            types_ko += " / " + TYPE_KO.get(t2, t2)

        # 추천 기술: moveset = [fast, charged1, charged2]
        moveset = entry.get("moveset", [])
        fast_ko    = move_link(moveset[0]) if moveset else "—"
        charged_ko = " / ".join(move_link(m) for m in moveset[1:]) if len(moveset) > 1 else "—"

        entries.append({
            "rank":         rank,
            "dex":          dex,
            "species_id":   species_id,
            "en_name":      en_name,
            "ko_name":      ko_name,
            "pokemon_slug": pokemon_slug_from_en(en_name),
            "score":        score,
            "types_ko":     types_ko,
            "fast_ko":      fast_ko,
            "charged_ko":   charged_ko,
        })

    results[league_key] = {
        "name":    info["name"],
        "cp":      info["cp"],
        "entries": entries,
    }
    top5 = [(e["rank"], e["ko_name"], e["score"]) for e in entries[:5]]
    print(f"  상위 5: {top5}")

os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n[완료] {OUTPUT} 저장")
print("다음: python generate_pvp_wiki.py")
