"""
fetch_field_research.py
ScrapedDuck research.json → .raw/field_research.json
과제 텍스트를 한국어로 변환 후 저장.
"""
import sys, json, os, re
sys.stdout.reconfigure(encoding="utf-8")
import requests

RAW_DIR = ".raw"
OUTPUT  = os.path.join(RAW_DIR, "field_research.json")
URL     = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/research.json"
HEADERS = {"User-Agent": "pogo-wiki-builder/1.0"}

NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")
with open(NAMES_PATH, encoding="utf-8") as f:
    names_data = json.load(f)
en2ko = {v["en_name"].lower(): v["ko_name"] for v in names_data.values()}

TYPE_EN2KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}

# 순서 중요: 더 구체적인 패턴 먼저
_PATTERNS = [
    # Catch
    (r"Catch (\d+) different species of Pokémon",      lambda m: f"서로 다른 포켓몬 {m[1]}종 포획"),
    (r"Catch (\d+) (.+?)-type Pokémon",                lambda m: f"{TYPE_EN2KO.get(m[2].lower(), m[2])} 타입 포켓몬 {m[1]}마리 포획"),
    (r"Catch a (.+?)-type Pokémon",                    lambda m: f"{TYPE_EN2KO.get(m[1].lower(), m[1])} 타입 포켓몬 포획"),
    (r"Catch (\d+) Pokémon with Weather Boost",        lambda m: f"날씨 부스트 포켓몬 {m[1]}마리 포획"),
    (r"Catch (\d+) Pokémon",                           lambda m: f"포켓몬 {m[1]}마리 포획"),
    # Throw
    (r"Make (\d+) Excellent Throws? in a row",         lambda m: f"훌륭해요! 던지기 {m[1]}회 연속"),
    (r"Make (\d+) Great Curveball Throws? in a row",   lambda m: f"잘했어요! 커브볼 {m[1]}회 연속"),
    (r"Make (\d+) Great Throws? in a row",             lambda m: f"잘했어요! 던지기 {m[1]}회 연속"),
    (r"Make (\d+) Excellent Throws?",                  lambda m: f"훌륭해요! 던지기 {m[1]}회"),
    (r"Make (\d+) Great Throws?",                      lambda m: f"잘했어요! 던지기 {m[1]}회"),
    (r"Make (\d+) Nice Throws?",                       lambda m: f"좋아요! 던지기 {m[1]}회"),
    (r"Make (\d+) Curveball Throws?",                  lambda m: f"커브볼 던지기 {m[1]}회"),
    # Raid
    (r"Win (\d+) raids?",                              lambda m: f"레이드 {m[1]}회 승리"),
    (r"Win a three-star raid or higher",               lambda m: "별 3개 이상 레이드 승리"),
    (r"Win a raid",                                    lambda m: "레이드 승리"),
    # Explore / Walk
    (r"Explore (\d+) km",                              lambda m: f"{m[1]}km 탐험"),
    (r"Earn (\d+) Cand(?:y|ies) walking with your buddy", lambda m: f"버디와 걸어서 사탕 {m[1]}개 획득"),
    # Hatch
    (r"Hatch (\d+) Eggs?",                             lambda m: f"알 {m[1]}개 부화"),
    (r"Hatch an Egg",                                  lambda m: "알 부화"),
    # Spin
    (r"Spin (\d+) PokéStops? or Gyms?",               lambda m: f"포켓스탑/체육관 {m[1]}개 돌리기"),
    # Power up
    (r"Power up Pokémon (\d+) times?",                 lambda m: f"포켓몬 {m[1]}회 강화"),
    # Evolve
    (r"Evolve a Pokémon",                              lambda m: "포켓몬 진화"),
    # Snapshot
    (r"Take a snapshot of a wild Pokémon",             lambda m: "야생 포켓몬 사진 찍기"),
    # Trade
    (r"Trade a Pokémon",                               lambda m: "포켓몬 교환"),
    # Gift
    (r"Send (\d+) Gifts? and add a sticker to each",  lambda m: f"선물 {m[1]}개 보내고 스티커 붙이기"),
    # Rocket
    (r"Defeat a Team GO Rocket Grunt",                 lambda m: "팀 GO 로켓 그런트 처치"),
    (r"Defeat (\d+) Team GO Rocket Grunts?",          lambda m: f"팀 GO 로켓 그런트 {m[1]}명 처치"),
    (r"Defeat a Team GO Rocket Leader",               lambda m: "팀 GO 로켓 간부 처치"),
]

def translate(text: str) -> str:
    for pattern, fn in _PATTERNS:
        m = re.match(pattern, text, re.IGNORECASE)
        if m:
            return fn(m)
    return text  # 번역 실패 시 원문

def resolve_reward(pm: dict) -> dict:
    name_en = pm.get("name", "")
    ko = en2ko.get(name_en.lower(), name_en)
    dex_from_img = 0
    img = pm.get("image", "")
    m = re.search(r"/pm(\d+)\.", img)
    if m:
        dex_from_img = int(m.group(1))
    return {
        "en": name_en, "ko": ko,
        "dex": dex_from_img,
        "can_shiny": pm.get("canBeShiny", False),
        "cp_min": pm.get("combatPower", {}).get("min"),
        "cp_max": pm.get("combatPower", {}).get("max"),
    }

# ── 수집 ──────────────────────────────────────────────────────────
print("ScrapedDuck research.json 다운로드 중...")
r = requests.get(URL, headers=HEADERS, timeout=30)
r.raise_for_status()
raw: list[dict] = r.json()
print(f"  → {len(raw)}개 과제")

result = []
for task in raw:
    text_en = task.get("text", "")
    rewards = [resolve_reward(p) for p in task.get("rewards", [])]
    result.append({
        "text_en": text_en,
        "text_ko": translate(text_en),
        "rewards": rewards,
    })

os.makedirs(RAW_DIR, exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"[완료] {OUTPUT} 저장 ({len(result)}개)")
