"""
fetch_pve_moves.py
PokeMiners GAME_MASTER에서 PvE 기술 데이터 수집.
PvP 위력값과 다른 실제 레이드/체육관 수치.
출력: .raw/pve_moves.json
"""
import sys, json, os, re
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR    = ".raw"
OUTPUT     = os.path.join(RAW_DIR, "pve_moves.json")
MOVES_PATH = os.path.join(RAW_DIR, "go_moves.json")
HEADERS    = {"User-Agent": "pogo-wiki-builder/1.0"}

GM_URL = (
    "https://raw.githubusercontent.com/PokeMiners/game_masters/master"
    "/latest/latest.json"
)

TYPE_PREFIX = "POKEMON_TYPE_"

# PvP 기술 데이터 (이름/타입 보완용)
with open(MOVES_PATH, encoding="utf-8") as f:
    pvp_raw = json.load(f)
pvp_by_id: dict[str, dict] = {m["move_id"]: m for m in pvp_raw.values()}

# ── GAME_MASTER 다운로드 ──────────────────────────────────────────
print(f"PokeMiners GAME_MASTER 다운로드 중... (파일이 클 수 있음)")
try:
    r = requests.get(GM_URL, timeout=120, headers=HEADERS)
    r.raise_for_status()
    gm: list = r.json()
    print(f"  → {len(gm)}개 템플릿 로드")
except Exception as e:
    print(f"  [실패] {e}")
    sys.exit(1)

# ── PvE 기술 파싱 ────────────────────────────────────────────────
pve_moves: dict[str, dict] = {}

for template in gm:
    tid = template.get("templateId", "")
    if not re.match(r"V\d+_MOVE_", tid):
        continue
    data = template.get("data", {})
    move = data.get("moveSettings", {})
    if not move:
        continue

    move_id = move.get("movementId", "")
    if not move_id or not isinstance(move_id, str):
        continue

    type_raw = move.get("pokemonType", "")
    type_en  = type_raw.replace(TYPE_PREFIX, "").lower() if type_raw else ""
    power        = float(move.get("power", 0))
    duration_ms  = int(move.get("durationMs", 0))
    energy_delta = int(move.get("energyDelta", 0))

    dps = round(power / (duration_ms / 1000), 2) if duration_ms > 0 else 0
    eps = round(abs(energy_delta) / (duration_ms / 1000), 2) if duration_ms > 0 else 0

    is_fast = energy_delta > 0

    # PvP 데이터 보완 (한국어 이름, 슬러그)
    pvp = pvp_by_id.get(move_id, {})
    ko_name = pvp.get("ko_name", "")
    slug    = pvp.get("slug", move_id.lower().replace("_", "-"))
    if not ko_name:
        ko_name = pvp.get("en_name", move_id.replace("_", " ").title())

    pve_moves[move_id] = {
        "move_id":      move_id,
        "ko_name":      ko_name,
        "slug":         slug,
        "type":         type_en,
        "power":        power,
        "duration_ms":  duration_ms,
        "energy_delta": energy_delta,
        "dps_pve":      dps,
        "eps_pve":      eps,
        "is_fast":      is_fast,
    }

os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(pve_moves, f, ensure_ascii=False, indent=2)

fast_cnt    = sum(1 for v in pve_moves.values() if v["is_fast"])
charged_cnt = sum(1 for v in pve_moves.values() if not v["is_fast"])
print(f"\n[완료] {OUTPUT} 저장")
print(f"  PvE 기술: 빠른 기술 {fast_cnt}개, 스페셜 기술 {charged_cnt}개")

# PvP vs PvE 위력 차이 샘플 비교
print("\n[PvP vs PvE 위력 비교 샘플]")
compare_ids = ["THUNDER_SHOCK", "VINE_WHIP", "WATER_GUN", "RAZOR_LEAF", "ACID"]
for mid in compare_ids:
    pve = pve_moves.get(mid, {})
    pvp = pvp_by_id.get(mid, {})
    if pve and pvp:
        print(f"  {mid:20s}: PvP={pvp.get('power',0):4.0f}, PvE={pve.get('power',0):4.0f}, PvE DPS={pve.get('dps_pve',0):.2f}")

print("\n다음: python generate_raid_counters.py")
