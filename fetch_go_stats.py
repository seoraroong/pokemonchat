"""
fetch_go_stats.py
PVPoke gamemaster JSON에서 포켓몬 GO 전용 스탯을 가져와 .raw/go_pokemon_stats.json 저장.
데이터: GO 공격/방어/체력, 최대 CP(Lv.40/50), 버디 거리, 기술 풀
"""
import sys, json, math, os, re, time
import requests

sys.stdout.reconfigure(encoding="utf-8")

PVPOKE_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster/pokemon.json"
RAW_DIR    = ".raw"
GEN1_PATH  = os.path.join(RAW_DIR, "gen1_pokemon.json")
OUTPUT     = os.path.join(RAW_DIR, "go_pokemon_stats.json")

CPM_40 = 0.79030001
CPM_50 = 0.84029999

# PokéAPI slug → PVPoke speciesId 예외 매핑
OVERRIDE = {
    "nidoran-f":  "nidoran_female",
    "nidoran-m":  "nidoran_male",
    "mr-mime":    "mr_mime",
    "farfetchd":  "farfetchd",
    "ho-oh":      "ho_oh",        # gen1 외지만 혹시 모르니
}


def calc_cp(atk: int, def_: int, sta: int, cpm: float) -> int:
    return max(10, math.floor(
        (atk + 15) * math.sqrt(def_ + 15) * math.sqrt(sta + 15) * cpm * cpm / 10
    ))


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", s.lower()).strip("_")


def slug_to_pvpoke_id(slug: str) -> str:
    """PokéAPI slug를 PVPoke speciesId 후보로 변환."""
    if slug in OVERRIDE:
        return OVERRIDE[slug]
    return normalize(slug)


def fmt_move(move_id: str) -> str:
    """THUNDER_SHOCK_FAST → Thunder Shock"""
    return move_id.replace("_FAST", "").replace("_", " ").title()


# ── 1. PVPoke 데이터 다운로드 ────────────────────────────────────────
print("PVPoke gamemaster 다운로드 중...")
resp = requests.get(PVPOKE_URL, timeout=60, headers={"User-Agent": "pogo-wiki-builder/1.0"})
resp.raise_for_status()
pvpoke_list: list[dict] = resp.json()
print(f"  → {len(pvpoke_list)}개 엔트리 로드")

# speciesId 기준 인덱스 생성 (정규화 key → 원본 dict)
pvpoke_index: dict[str, dict] = {}
for entry in pvpoke_list:
    sid = entry.get("speciesId", "")
    pvpoke_index[normalize(sid)] = entry

# ── 2. Gen 1 목록 로드 ───────────────────────────────────────────────
with open(GEN1_PATH, encoding="utf-8") as f:
    gen1_list: list[dict] = json.load(f)

print(f"Gen1 포켓몬 {len(gen1_list)}개 처리 중...")

results: dict[str, dict] = {}
missing: list[str] = []

for pkmn in gen1_list:
    slug      = pkmn["name"]       # e.g. "pikachu"
    pkmn_id   = pkmn["id"]         # e.g. 25
    pvpoke_key = slug_to_pvpoke_id(slug)
    entry      = pvpoke_index.get(pvpoke_key)

    if entry is None:
        missing.append(slug)
        continue

    bs  = entry.get("baseStats", {})
    atk = bs.get("atk", 0)
    def_ = bs.get("def", 0)
    sta  = bs.get("hp", bs.get("sta", 0))  # PVPoke uses 'hp' for stamina

    fast    = [fmt_move(m) for m in entry.get("fastMoves", [])]
    charged = [fmt_move(m) for m in entry.get("chargedMoves", [])]
    buddy   = entry.get("buddyDistance", 0)

    results[slug] = {
        "id":           pkmn_id,
        "slug":         slug,
        "atk":          atk,
        "def":          def_,
        "sta":          sta,
        "cp_40":        calc_cp(atk, def_, sta, CPM_40),
        "cp_50":        calc_cp(atk, def_, sta, CPM_50),
        "buddy_km":     buddy,
        "fast_moves":   fast,
        "charged_moves": charged,
    }
    print(f"  OK #{pkmn_id:03d} {slug:20s}  atk={atk} def={def_} sta={sta}  CP40={results[slug]['cp_40']:,}")

# ── 3. 저장 ─────────────────────────────────────────────────────────
os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n[완료] {len(results)}개 저장 → {OUTPUT}")
if missing:
    print(f"[주의] PVPoke 매칭 실패 ({len(missing)}개): {missing}")
