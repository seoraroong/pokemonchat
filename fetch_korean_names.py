# PokéAPI 한국어 이름 패치 스크립트
import sys
import urllib.request
import json
import time
import os

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = ".raw"
POKE_OUT = os.path.join(RAW_DIR, "gen1_pokemon.json")

def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pokeapi-wiki-builder/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    retry {attempt+1} after {wait}s ({e})")
                time.sleep(wait)
            else:
                raise

with open(POKE_OUT, encoding="utf-8") as f:
    pokemons = json.load(f)

print(f"[ko] {len(pokemons)}마리 한국어 이름 패치 중...")

for i, p in enumerate(pokemons, 1):
    if "name_ko" in p and p["name_ko"]:
        print(f"  skip #{p['id']:03d} {p['name']}")
        continue
    try:
        species_url = f"https://pokeapi.co/api/v2/pokemon-species/{p['id']}/"
        species = fetch(species_url)

        name_ko = ""
        name_ja = ""
        flavor_ko = ""
        for n in species.get("names", []):
            if n["language"]["name"] == "ko":
                name_ko = n["name"]
            if n["language"]["name"] == "ja":
                name_ja = n["name"]

        for entry in species.get("flavor_text_entries", []):
            if entry["language"]["name"] == "ko":
                flavor_ko = entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                break

        p["name_ko"] = name_ko
        p["name_ja"] = name_ja
        p["flavor_text_ko"] = flavor_ko
        p["evolution_line"] = p.get("evolves_from") or p["name"]  # root of line = self if no pre-evo

        print(f"  OK #{p['id']:03d} {p['name']} -> {name_ko}")
        time.sleep(0.3)
    except Exception as e:
        print(f"  NG #{p['id']} {p['name']}: {e}")
        p.setdefault("name_ko", "")
        p.setdefault("name_ja", "")
        p.setdefault("flavor_text_ko", "")
        p.setdefault("evolution_line", p["name"])

    if i % 10 == 0:
        with open(POKE_OUT, "w", encoding="utf-8") as f:
            json.dump(pokemons, f, ensure_ascii=False, indent=2)

with open(POKE_OUT, "w", encoding="utf-8") as f:
    json.dump(pokemons, f, ensure_ascii=False, indent=2)
print(f"\n[ko] 완료 -> {POKE_OUT}")
