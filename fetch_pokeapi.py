# PokéAPI data fetcher - Gen1 + type effectiveness
import sys
import urllib.request
import json
import time
import os

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = ".raw"
os.makedirs(RAW_DIR, exist_ok=True)

BASE = "https://pokeapi.co/api/v2"

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

# ── 1. Type effectiveness ──────────────────────────────────────
TYPE_IDS = {
    "normal":1,"fighting":2,"flying":3,"poison":4,"ground":5,
    "rock":6,"bug":7,"ghost":8,"steel":9,"fire":10,"water":11,
    "grass":12,"electric":13,"psychic":14,"ice":15,"dragon":16,
    "dark":17,"fairy":18
}

TYPE_OUT = os.path.join(RAW_DIR, "type_effectiveness.json")
type_data = {}
if os.path.exists(TYPE_OUT):
    with open(TYPE_OUT, encoding="utf-8") as f:
        type_data = json.load(f)
    print(f"[type] loaded {len(type_data)} existing types")

print("[type] fetching...")
for tname, tid in TYPE_IDS.items():
    if tname in type_data:
        print(f"  skip {tname}")
        continue
    d = fetch(f"{BASE}/type/{tid}/")
    dr = d["damage_relations"]
    type_data[tname] = {
        "double_damage_to":   [x["name"] for x in dr["double_damage_to"]],
        "half_damage_to":     [x["name"] for x in dr["half_damage_to"]],
        "no_damage_to":       [x["name"] for x in dr["no_damage_to"]],
        "double_damage_from": [x["name"] for x in dr["double_damage_from"]],
        "half_damage_from":   [x["name"] for x in dr["half_damage_from"]],
        "no_damage_from":     [x["name"] for x in dr["no_damage_from"]],
    }
    print(f"  OK {tname}")
    with open(TYPE_OUT, "w", encoding="utf-8") as f:
        json.dump(type_data, f, ensure_ascii=False, indent=2)
    time.sleep(0.5)

print(f"[type] done -> {TYPE_OUT} ({len(type_data)} types)\n")

# ── 2. Gen 1 Pokemon 151 ────────────────────────────────────────
POKE_OUT = os.path.join(RAW_DIR, "gen1_pokemon.json")
existing = {}
if os.path.exists(POKE_OUT):
    with open(POKE_OUT, encoding="utf-8") as f:
        data = json.load(f)
    existing = {p["name"]: p for p in data}
    print(f"[pokemon] loaded {len(existing)} existing entries")

print("[pokemon] fetching Gen 1...")
poke_list = fetch(f"{BASE}/pokemon?limit=151")["results"]

for i, p in enumerate(poke_list, 1):
    name = p["name"]
    if name in existing:
        print(f"  skip #{i:03d} {name}")
        continue
    try:
        d = fetch(p["url"])
        species_d = fetch(d["species"]["url"])

        flavor = ""
        for entry in species_d.get("flavor_text_entries", []):
            if entry["language"]["name"] == "en":
                flavor = entry["flavor_text"].replace("\n", " ").replace("\f", " ")
                break

        existing[name] = {
            "id":   d["id"],
            "name": name,
            "types": [t["type"]["name"] for t in d["types"]],
            "stats": {s["stat"]["name"]: s["base_stat"] for s in d["stats"]},
            "height_dm": d["height"],
            "weight_hg": d["weight"],
            "base_experience": d["base_experience"],
            "abilities": [a["ability"]["name"] for a in d["abilities"]],
            "flavor_text": flavor,
            "evolves_from": (species_d.get("evolves_from_species") or {}).get("name"),
            "generation": species_d.get("generation", {}).get("name"),
            "is_legendary": species_d.get("is_legendary", False),
            "is_mythical":  species_d.get("is_mythical", False),
            "capture_rate": species_d.get("capture_rate"),
        }
        print(f"  OK #{i:03d} {name}")
        # save after every 10 pokemon
        if i % 10 == 0:
            pokemons_sorted = sorted(existing.values(), key=lambda x: x["id"])
            with open(POKE_OUT, "w", encoding="utf-8") as f:
                json.dump(pokemons_sorted, f, ensure_ascii=False, indent=2)
        time.sleep(0.3)
    except Exception as e:
        print(f"  NG #{i} {name}: {e}")

pokemons_sorted = sorted(existing.values(), key=lambda x: x["id"])
with open(POKE_OUT, "w", encoding="utf-8") as f:
    json.dump(pokemons_sorted, f, ensure_ascii=False, indent=2)
print(f"\n[pokemon] done -> {POKE_OUT} ({len(existing)} pokemon)")
