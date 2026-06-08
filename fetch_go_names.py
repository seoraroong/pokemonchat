"""
fetch_go_names.py
game_master_pokemon.json 의 모든 포켓몬 도감 번호에 대해
PokéAPI 에서 한국어 이름 + 영문 이름 + 세대 정보 수집.
출력: .raw/go_all_names.json
기존 Gen1 데이터가 있으면 재활용해 API 요청 최소화.
"""
import sys, json, os, time

sys.stdout.reconfigure(encoding="utf-8")

import requests

RAW_DIR  = ".raw"
GM_PATH  = os.path.join(RAW_DIR, "game_master_pokemon.json")
OUT_PATH = os.path.join(RAW_DIR, "go_all_names.json")
API_BASE = "https://pokeapi.co/api/v2"
HEADERS  = {"User-Agent": "pogo-wiki-builder/1.0"}
DELAY    = 0.15   # 요청 간격 (초)

# 세대 범위
GEN_RANGES = {1:(1,151), 2:(152,251), 3:(252,386), 4:(387,493),
              5:(494,649), 6:(650,721), 7:(722,809), 8:(810,905), 9:(906,1025)}

def get_gen(dex: int) -> int:
    for g, (lo, hi) in GEN_RANGES.items():
        if lo <= dex <= hi:
            return g
    return 9

def fetch_species(dex_id: int, retry: int = 3) -> dict | None:
    url = f"{API_BASE}/pokemon-species/{dex_id}"
    for attempt in range(retry):
        try:
            r = requests.get(url, timeout=20, headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [실패] #{dex_id}: {e}")
                return None


# ── 기존 데이터 로드 ───────────────────────────────────────────────
existing: dict[str, dict] = {}
if os.path.exists(OUT_PATH):
    with open(OUT_PATH, encoding="utf-8") as f:
        existing = json.load(f)
    print(f"기존 캐시 {len(existing)}개 로드")

# ── 대상 도감 번호 목록 ────────────────────────────────────────────
with open(GM_PATH, encoding="utf-8") as f:
    gm: dict = json.load(f)

dex_ids = sorted(int(k) for k in gm.keys())
print(f"처리 대상: {len(dex_ids)}마리")
todo = [d for d in dex_ids if str(d) not in existing]
print(f"신규 수집 필요: {len(todo)}마리")

# ── PokéAPI 수집 ──────────────────────────────────────────────────
results = dict(existing)

for i, dex_id in enumerate(todo):
    data = fetch_species(dex_id)
    if not data:
        continue

    # 한국어 이름
    ko_name = ""
    en_name = ""
    for n in data.get("names", []):
        lang = n["language"]["name"]
        if lang == "ko":
            ko_name = n["name"]
        elif lang == "en":
            en_name = n["name"]

    # 영문 이름 fallback
    if not en_name:
        en_name = data.get("name", "").replace("-", " ").title()
    if not ko_name:
        ko_name = en_name  # 한국어 없으면 영어로

    results[str(dex_id)] = {
        "dex":     dex_id,
        "en_name": en_name,
        "ko_name": ko_name,
        "gen":     get_gen(dex_id),
    }

    print(f"  [{i+1}/{len(todo)}] #{dex_id:04d} {en_name:20s} → {ko_name}")

    # 매 50개마다 중간 저장
    if (i + 1) % 50 == 0:
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  [중간 저장] {len(results)}개")

    time.sleep(DELAY)

# ── 최종 저장 ─────────────────────────────────────────────────────
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n[완료] {OUT_PATH} 저장 ({len(results)}마리)")
print("다음: python generate_go_wiki_full.py")
