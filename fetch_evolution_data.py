"""
fetch_evolution_data.py
PVPoke pokemon.json에서 GO 진화 체인 + 사탕 비용 추출.
출력: .raw/go_evolution.json
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR    = ".raw"
OUTPUT     = os.path.join(RAW_DIR, "go_evolution.json")
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
HEADERS    = {"User-Agent": "pogo-wiki-builder/1.0"}

PVPOKE_URL = (
    "https://raw.githubusercontent.com/pvpoke/pvpoke/master"
    "/src/data/gamemaster/pokemon.json"
)

ITEM_KO = {
    "KINGS_ROCK":       "왕의 징표석",
    "SUN_STONE":        "태양의 돌",
    "METAL_COAT":       "금속코트",
    "DRAGON_SCALE":     "용의비늘",
    "UP_GRADE":         "업그레이드",
    "UPGRADE":          "업그레이드",
    "SINNOH_STONE":     "신오의 돌",
    "UNOVA_STONE":      "유나이트의 돌",
    "BLACK_AUGURITE":   "흑요석",
    "PEAT_BLOCK":       "이탄 덩어리",
    "LINKING_CORD":     "이어지는실",
    "AUSPICIOUS_ARMOR": "상서로운 갑옷",
    "MALICIOUS_ARMOR":  "악의의 갑옷",
}

VARIANT_KW = {
    "alola","alolan","galar","galarian","hisui","hisuian","paldea","paldean",
    "mega","shadow","purified","origin","therian","black","white",
    "xl","xs","libre","phd","belle","cosplay","pop","star",
    "school","complete","dusk","midnight","midday",
}
BASE_OVERRIDES = {
    "nidoran_female","nidoran_male","mr_mime","farfetch_d","ho_oh","mime_jr",
    "porygon_z","type_null","jangmo_o","hakamo_o","kommo_o",
    "tapu_koko","tapu_lele","tapu_bulu","tapu_fini","mr_rime","sirfetchd",
    "great_tusk","scream_tail","brute_bonnet","flutter_mane",
    "slither_wing","sandy_shocks","iron_treads","iron_bundle",
    "iron_hands","iron_jugulis","iron_moth","iron_thorns",
    "roaring_moon","iron_valiant",
}

def is_variant(sid: str) -> bool:
    if sid in BASE_OVERRIDES:
        return False
    return bool(set(sid.lower().split("_")) & VARIANT_KW)

# ── 다운로드 ─────────────────────────────────────────────────────
print("PVPoke pokemon.json 다운로드 중...")
r = requests.get(PVPOKE_URL, timeout=60, headers=HEADERS)
r.raise_for_status()
pvpoke_list: list[dict] = r.json()
print(f"  → {len(pvpoke_list)}개 엔트리")

# speciesId → dex (변형 포함 전체 매핑, 진화 타깃 dex 탐색용)
sid_to_dex: dict[str, int] = {
    e["speciesId"]: e["dex"]
    for e in pvpoke_list if e.get("dex") and e.get("speciesId")
}

# ── 진화 파싱 ─────────────────────────────────────────────────────
# PVPoke 포맷: entry.family.evolutions = ["ivysaur", "venusaur"] (다음 진화 목록)
evo_map: dict[str, dict] = {}   # str(dex) → {dex, evolves_to: [...]}

for entry in pvpoke_list:
    sid = entry.get("speciesId", "")
    dex = entry.get("dex")
    if not dex or is_variant(sid):
        continue

    family = entry.get("family", {})
    evolutions = family.get("evolutions", [])
    if not evolutions:
        continue

    evo_to = []
    for target_sid in evolutions:
        if not target_sid or is_variant(target_sid):
            continue
        target_dex = sid_to_dex.get(target_sid)
        if not target_dex:
            continue

        evo_to.append({
            "dex": target_dex,
            "sid": target_sid,
            "candy": 0,     # PVPoke에 사탕 수 없음
            "item": "",
            "item_ko": "",
        })

    if evo_to:
        evo_map[str(dex)] = {
            "dex":        dex,
            "sid":        sid,
            "evolves_to": evo_to,
        }

# 역방향: target_dex → from_dex
evolves_from: dict[int, int] = {}
for data in evo_map.values():
    for evo in data["evolves_to"]:
        evolves_from[evo["dex"]] = data["dex"]

# evolves_from 병합
for dex_str, data in evo_map.items():
    data["evolves_from_dex"] = evolves_from.get(data["dex"])

# evolves_from만 있고 evo_map에 없는 dex도 추가 (최종 진화형 등)
for to_dex, from_dex in evolves_from.items():
    dex_str = str(to_dex)
    if dex_str not in evo_map:
        evo_map[dex_str] = {
            "dex":             to_dex,
            "sid":             "",
            "evolves_from_dex": from_dex,
            "evolves_to":      [],
        }

# ── 저장 ─────────────────────────────────────────────────────────
os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(evo_map, f, ensure_ascii=False, indent=2)

# 통계
has_from = sum(1 for v in evo_map.values() if v.get("evolves_from_dex"))
has_to   = sum(1 for v in evo_map.values() if v.get("evolves_to"))
print(f"\n[완료] {OUTPUT} 저장")
print(f"  진화 관계 포켓몬: {len(evo_map)}개")
print(f"  진화 전 있음: {has_from}개 / 진화 후 있음: {has_to}개")

# 샘플 확인 (이상해씨 #1)
sample = evo_map.get("1")
if sample:
    print(f"\n샘플 #1: {sample}")
print("다음: python generate_pvp_wiki.py")
