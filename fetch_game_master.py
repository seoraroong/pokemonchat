"""
fetch_game_master.py
PVPoke gamemaster JSON(GitHub) 에서 포켓몬 GO 전체 포켓몬 데이터 파싱.
PVPoke 는 Niantic GAME_MASTER 를 직접 파싱해 정제한 공개 데이터.
출력: .raw/game_master_pokemon.json
"""
import sys, json, os, re, math

sys.stdout.reconfigure(encoding="utf-8")

import requests

RAW_DIR = ".raw"
OUTPUT  = os.path.join(RAW_DIR, "game_master_pokemon.json")

# PVPoke 가 GitHub 에 공개한 Pokémon GO 게임마스터 파싱 데이터
PVPOKE_URL = (
    "https://raw.githubusercontent.com/pvpoke/pvpoke/master/"
    "src/data/gamemaster/pokemon.json"
)

CPM_40 = 0.79030001
CPM_50 = 0.84029999

# 변형 폼 식별 키워드 (speciesId 에 포함되면 변형)
VARIANT_KEYWORDS = {
    "alola", "alolan", "galar", "galarian", "hisui", "hisuian", "paldea", "paldean",
    "mega", "shadow", "purified", "origin", "therian", "black", "white",
    "resolute", "ordinary", "pirouette", "aria", "sunshine", "rainy", "snowy",
    "libre", "phd", "belle", "cosplay", "pop", "star", "rock",
    "school", "complete", "dusk", "dawn", "wings", "mane", "ultra",
    "midnight", "midday",
    "xl", "xs",
}

# 키워드 매칭이 안 되지만 명시적으로 variant로 처리할 species IDs
VARIANT_SPECIFIC_IDS = {
    "deoxys_attack", "deoxys_defense", "deoxys_speed",
    "hoopa_unbound", "hoopa_confined",
    "calyrex_ice_rider", "calyrex_shadow_rider",
}

# speciesId 에 언더스코어가 있지만 기본 폼인 특수 케이스
BASE_FORM_OVERRIDES = {
    "nidoran_female", "nidoran_male", "mr_mime", "farfetch_d",
    "ho_oh", "mime_jr", "porygon_z", "type_null",
    "jangmo_o", "hakamo_o", "kommo_o", "tapu_koko", "tapu_lele",
    "tapu_bulu", "tapu_fini", "mr_rime", "sirfetchd",
    "great_tusk", "scream_tail", "brute_bonnet", "flutter_mane",
    "slither_wing", "sandy_shocks", "iron_treads", "iron_bundle",
    "iron_hands", "iron_jugulis", "iron_moth", "iron_thorns",
    "roaring_moon", "iron_valiant",
}


def calc_cp(atk, def_, sta, cpm):
    return max(10, math.floor(
        (atk + 15) * math.sqrt(def_ + 15) * math.sqrt(sta + 15) * cpm * cpm / 10
    ))


def is_variant(species_id: str) -> bool:
    if species_id in BASE_FORM_OVERRIDES:
        return False
    if species_id in VARIANT_SPECIFIC_IDS:
        return True
    parts = set(species_id.lower().split("_"))
    return bool(parts & VARIANT_KEYWORDS)


def fmt_move(m: str) -> str:
    """THUNDER_SHOCK_FAST → Thunder Shock  (또는 THUNDER_SHOCK → Thunder Shock)"""
    return m.replace("_FAST", "").replace("_", " ").title()


# ── 1. 다운로드 ────────────────────────────────────────────────────
print("PVPoke gamemaster pokemon.json 다운로드 중...")
r = requests.get(
    PVPOKE_URL, timeout=60,
    headers={"User-Agent": "pogo-wiki-builder/1.0"},
)
r.raise_for_status()
pvpoke_list: list[dict] = r.json()
print(f"  → {len(pvpoke_list)}개 엔트리 로드")


# ── 2. 파싱 ───────────────────────────────────────────────────────
base_map: dict[int, dict]     = {}   # dex → base form data
variant_map: dict[int, dict]  = {}   # dex → {form_name: stats}

for entry in pvpoke_list:
    sid  = entry.get("speciesId", "")
    dex  = entry.get("dex")

    # dex 없으면 speciesName 등으로 추정 불가 → 건너뜀
    if not dex:
        continue

    bs   = entry.get("baseStats", {})
    atk  = bs.get("atk", 0)
    def_ = bs.get("def", 0)
    sta  = bs.get("hp", bs.get("sta", 0))   # PVPoke 는 'hp' 키 사용

    if not (atk and def_ and sta):          # 스탯 없으면 미출시
        continue

    types = entry.get("types", [])
    t1    = types[0] if len(types) > 0 else ""
    t2    = types[1] if len(types) > 1 else None

    fast    = [fmt_move(m) for m in entry.get("fastMoves",    [])]
    charged = [fmt_move(m) for m in entry.get("chargedMoves", [])]

    # eliteMoves 처리 (리스트 or dict)
    elite_raw = entry.get("eliteMoves", [])
    if isinstance(elite_raw, dict):
        elite_fast    = [fmt_move(m) for m in elite_raw.get("fast", [])]
        elite_charged = [fmt_move(m) for m in elite_raw.get("charged", [])]
    else:
        # 예전 PVPoke 형식: 단일 리스트
        elite_fast    = []
        elite_charged = [fmt_move(m) for m in elite_raw]

    buddy  = entry.get("buddyDistance", 3.0)

    record = {
        "dex":           dex,
        "species_id":    sid,
        "type1":         t1,
        "type2":         t2,
        "atk":           atk,
        "def":           def_,
        "sta":           sta,
        "cp_40":         calc_cp(atk, def_, sta, CPM_40),
        "cp_50":         calc_cp(atk, def_, sta, CPM_50),
        "buddy_km":      buddy,
        "fast_moves":    fast,
        "charged_moves": charged,
        "elite_fast":    elite_fast,
        "elite_charged": elite_charged,
        "variant_forms": {},
    }

    if is_variant(sid):
        # 변형 폼 → 해당 dex 의 variant_forms 에 추가
        form_name = sid  # e.g. "rattata_alola"
        variant_map.setdefault(dex, {})[form_name] = {
            "atk": atk, "def": def_, "sta": sta,
            "cp_40": record["cp_40"], "cp_50": record["cp_50"],
            "type1": t1, "type2": t2,
            "fast_moves":    fast,
            "charged_moves": charged,
            "elite_fast":    elite_fast,
            "elite_charged": elite_charged,
        }
    else:
        # 기본 폼
        if dex not in base_map:
            base_map[dex] = record

# 변형 폼 병합
for dex, variants in variant_map.items():
    if dex in base_map:
        base_map[dex]["variant_forms"] = variants

result = {str(k): v for k, v in sorted(base_map.items())}


# ── 3. 통계 출력 ───────────────────────────────────────────────────
print(f"  → 기본 폼 포켓몬 {len(result)}개")
gen_ranges = [(1,151,1),(152,251,2),(252,386,3),(387,493,4),
              (494,649,5),(650,721,6),(722,809,7),(810,905,8),(906,1025,9)]
for lo, hi, g in gen_ranges:
    cnt = sum(1 for k in result if lo <= int(k) <= hi)
    if cnt:
        print(f"  Gen{g}: {cnt}마리")

variant_cnt = sum(len(v) for v in variant_map.values())
print(f"  변형 폼: {variant_cnt}개 (알로라/가라르/메가 등)")


# ── 4. 저장 ───────────────────────────────────────────────────────
os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n[완료] {OUTPUT} 저장")
print("다음: python fetch_go_names.py")
