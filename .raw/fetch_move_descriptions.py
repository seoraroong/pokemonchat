"""
PokéAPI에서 기술 설명(flavor text) 수집
output: .raw/move_descriptions.json
  { "ACID": { "ko": "...", "en": "..." }, ... }

이미 수집된 항목은 건너뛰므로 중간에 중단해도 재실행 가능.
"""

import json
import time
import urllib.request
import urllib.error
import os

INPUT  = os.path.join(os.path.dirname(__file__), "go_moves.json")
OUTPUT = os.path.join(os.path.dirname(__file__), "move_descriptions.json")

VERSION_PRIORITY = [
    "scarlet-violet", "sword-shield", "sun-moon",
    "ultra-sun-ultra-moon", "x-y", "black-2-white-2",
    "black-white", "heartgold-soulsilver", "diamond-pearl",
]

def best_text(entries, lang):
    for ver in VERSION_PRIORITY:
        for e in entries:
            if e["language"]["name"] == lang and e["version_group"]["name"] == ver:
                return e["flavor_text"].replace("\n", " ").replace("\f", " ").strip()
    # 버전 무관하게 해당 언어 중 마지막 항목
    for e in reversed(entries):
        if e["language"]["name"] == lang:
            return e["flavor_text"].replace("\n", " ").replace("\f", " ").strip()
    return ""

def fetch(slug):
    url = f"https://pokeapi.co/api/v2/move/{slug}/"
    req = urllib.request.Request(url, headers={"User-Agent": "PokeMORE-data-collector/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def main():
    moves = json.load(open(INPUT, encoding="utf-8"))

    # 기존 결과 로드 (재실행 시 이어서)
    if os.path.exists(OUTPUT):
        result = json.load(open(OUTPUT, encoding="utf-8"))
    else:
        result = {}

    total = len(moves)
    done = 0
    skipped = 0
    failed = []

    for i, (move_id, info) in enumerate(moves.items(), 1):
        slug = info.get("slug", "")
        if not slug:
            skipped += 1
            continue

        if move_id in result:
            done += 1
            continue

        print(f"[{i}/{total}] {move_id} ({slug}) ...", end=" ", flush=True)
        try:
            data = fetch(slug)
            entries = data.get("flavor_text_entries", [])
            ko = best_text(entries, "ko")
            en = best_text(entries, "en")
            result[move_id] = {"ko": ko, "en": en}
            done += 1
            print(f"OK  ko={ko[:30]!r}" if ko else "OK  (ko없음)")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                result[move_id] = {"ko": "", "en": ""}
                print(f"404 (GO 전용 기술)")
            else:
                failed.append(move_id)
                print(f"HTTP {e.code}")
        except Exception as e:
            failed.append(move_id)
            print(f"ERR {e}")

        # 10개마다 저장
        if i % 10 == 0:
            json.dump(result, open(OUTPUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

        time.sleep(0.4)  # rate limit

    json.dump(result, open(OUTPUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n완료: {done}개 수집, {skipped}개 slug없음, {len(failed)}개 실패")
    if failed:
        print(f"실패 목록: {failed}")

if __name__ == "__main__":
    main()
