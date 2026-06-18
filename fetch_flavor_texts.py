"""
fetch_flavor_texts.py
PokeAPI에서 전체 포켓몬 한국어(없으면 영어) 도감 설명문 수집.
출력: .raw/flavor_texts.json  { "dex": { "ko": "...", "en": "..." } }

PokeAPI rate limit: 비인증 100 req/s → asyncio로 동시 50개 처리
"""
import sys, json, os, asyncio, re
sys.stdout.reconfigure(encoding="utf-8")

import aiohttp

RAW_DIR = ".raw"
OUTPUT  = os.path.join(RAW_DIR, "flavor_texts.json")
NAMES_PATH = os.path.join(RAW_DIR, "go_all_names.json")

names_data = json.load(open(NAMES_PATH, encoding="utf-8"))
dex_list   = sorted(int(k) for k in names_data.keys())   # GO에 있는 포켓몬만

SEMAPHORE = asyncio.Semaphore(40)

def clean(text: str) -> str:
    return re.sub(r"[\n\f\r]+", " ", text).strip()

async def fetch_one(session: aiohttp.ClientSession, dex: int) -> tuple[int, dict]:
    url = f"https://pokeapi.co/api/v2/pokemon-species/{dex}"
    async with SEMAPHORE:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return dex, {}
            data = await r.json()

    entries = data.get("flavor_text_entries", [])
    ko_text = next(
        (clean(e["flavor_text"]) for e in entries
         if e["language"]["name"] == "ko"),
        None,
    )
    en_text = next(
        (clean(e["flavor_text"]) for e in reversed(entries)
         if e["language"]["name"] == "en"),
        None,
    )
    return dex, {"ko": ko_text or en_text or "", "en": en_text or ""}

async def main():
    existing: dict = {}
    if os.path.exists(OUTPUT):
        existing = json.loads(open(OUTPUT, encoding="utf-8").read())
        print(f"기존 {len(existing)}개 로드 (증분 업데이트)")

    todo = [d for d in dex_list if str(d) not in existing]
    print(f"수집 대상: {len(todo)}개 (전체 {len(dex_list)}개)")
    if not todo:
        print("모두 최신 상태입니다.")
        return

    results = dict(existing)
    done = 0

    async with aiohttp.ClientSession(
        headers={"User-Agent": "pogo-wiki-builder/1.0"}
    ) as session:
        for batch_start in range(0, len(todo), 100):
            batch = todo[batch_start: batch_start + 100]
            tasks = [fetch_one(session, d) for d in batch]
            for dex, info in await asyncio.gather(*tasks):
                if info:
                    results[str(dex)] = info
                done += 1
            print(f"  {done}/{len(todo)} 완료...")
            await asyncio.sleep(0.5)

    os.makedirs(RAW_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] {OUTPUT} — {len(results)}개 저장")

asyncio.run(main())
