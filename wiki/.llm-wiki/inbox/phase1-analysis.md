# Ingest Analysis — PokéAPI Gen 1 Data
**Source hashes:**
- `2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5` (type_effectiveness.json)
- `bb8096ad5a0b2c74200879a8a90f450de39cf76898c0fd158d85011302b5f3d5` (gen1_pokemon.json)
**Language detected:** en
**Analyzed:** 2026-06-05

---

## Source Summary
두 개의 JSON 파일로 구성된 PokéAPI 데이터 세트:
1. **type_effectiveness.json** — 18개 타입의 공격/방어 상성 관계 (double/half/no damage to/from)
2. **gen1_pokemon.json** — 1세대 포켓몬 151마리의 기본 스탯, 타입, 특성, 진화 정보, 전설/신화 여부, 포획률

이 데이터는 포켓몬 GO 챗봇의 핵심 지식 베이스가 될 예정이며, 레이드 카운터 계산, 배틀 타입 상성 안내, 포켓몬별 스탯 정보 제공에 활용됩니다.

---

## Concepts to Extract

### 타입 상성 페이지 (18개)

| Concept | Action | Reason |
|---------|--------|--------|
| type-normal | create | 노말 타입 상성 데이터 |
| type-fighting | create | 격투 타입 상성 데이터 |
| type-flying | create | 비행 타입 상성 데이터 |
| type-poison | create | 독 타입 상성 데이터 |
| type-ground | create | 땅 타입 상성 데이터 |
| type-rock | create | 바위 타입 상성 데이터 |
| type-bug | create | 벌레 타입 상성 데이터 |
| type-ghost | create | 고스트 타입 상성 데이터 |
| type-steel | create | 강철 타입 상성 데이터 |
| type-fire | create | 불꽃 타입 상성 데이터 |
| type-water | create | 물 타입 상성 데이터 |
| type-grass | create | 풀 타입 상성 데이터 |
| type-electric | create | 전기 타입 상성 데이터 |
| type-psychic | create | 에스퍼 타입 상성 데이터 |
| type-ice | create | 얼음 타입 상성 데이터 |
| type-dragon | create | 드래곤 타입 상성 데이터 |
| type-dark | create | 악 타입 상성 데이터 |
| type-fairy | create | 페어리 타입 상성 데이터 |

### 포켓몬 페이지 (진화 계열별 그룹, ~60개)

진화 계열 단위로 묶어서 페이지 생성 (개별 151개 대신 계열별로 묶으면 검색성↑):

| Concept | Action | Pokémon included |
|---------|--------|-----------------|
| pokemon-bulbasaur-line | create | Bulbasaur → Ivysaur → Venusaur |
| pokemon-charmander-line | create | Charmander → Charmeleon → Charizard |
| pokemon-squirtle-line | create | Squirtle → Wartortle → Blastoise |
| pokemon-caterpie-line | create | Caterpie → Metapod → Butterfree |
| pokemon-weedle-line | create | Weedle → Kakuna → Beedrill |
| pokemon-pidgey-line | create | Pidgey → Pidgeotto → Pidgeot |
| pokemon-rattata-line | create | Rattata → Raticate |
| pokemon-spearow-line | create | Spearow → Fearow |
| pokemon-ekans-line | create | Ekans → Arbok |
| pokemon-pikachu-line | create | Pichu (후속) / Pikachu → Raichu |
| pokemon-sandshrew-line | create | Sandshrew → Sandslash |
| pokemon-nidoran-f-line | create | Nidoran-F → Nidorina → Nidoqueen |
| pokemon-nidoran-m-line | create | Nidoran-M → Nidorino → Nidoking |
| pokemon-clefairy-line | create | Clefairy → Clefable |
| pokemon-vulpix-line | create | Vulpix → Ninetales |
| pokemon-jigglypuff-line | create | Jigglypuff → Wigglytuff |
| pokemon-zubat-line | create | Zubat → Golbat (→ Crobat) |
| pokemon-oddish-line | create | Oddish → Gloom → Vileplume |
| pokemon-paras-line | create | Paras → Parasect |
| pokemon-venonat-line | create | Venonat → Venomoth |
| pokemon-diglett-line | create | Diglett → Dugtrio |
| pokemon-meowth-line | create | Meowth → Persian |
| pokemon-psyduck-line | create | Psyduck → Golduck |
| pokemon-mankey-line | create | Mankey → Primeape |
| pokemon-growlithe-line | create | Growlithe → Arcanine |
| pokemon-poliwag-line | create | Poliwag → Poliwhirl → Poliwrath |
| pokemon-abra-line | create | Abra → Kadabra → Alakazam |
| pokemon-machop-line | create | Machop → Machoke → Machamp |
| pokemon-bellsprout-line | create | Bellsprout → Weepinbell → Victreebel |
| pokemon-tentacool-line | create | Tentacool → Tentacruel |
| pokemon-geodude-line | create | Geodude → Graveler → Golem |
| pokemon-ponyta-line | create | Ponyta → Rapidash |
| pokemon-slowpoke-line | create | Slowpoke → Slowbro |
| pokemon-magnemite-line | create | Magnemite → Magneton |
| pokemon-farfetchd | create | Farfetch'd (진화 없음) |
| pokemon-doduo-line | create | Doduo → Dodrio |
| pokemon-seel-line | create | Seel → Dewgong |
| pokemon-grimer-line | create | Grimer → Muk |
| pokemon-shellder-line | create | Shellder → Cloyster |
| pokemon-gastly-line | create | Gastly → Haunter → Gengar |
| pokemon-onix | create | Onix (→ Steelix 후속) |
| pokemon-drowzee-line | create | Drowzee → Hypno |
| pokemon-krabby-line | create | Krabby → Kingler |
| pokemon-voltorb-line | create | Voltorb → Electrode |
| pokemon-exeggcute-line | create | Exeggcute → Exeggutor |
| pokemon-cubone-line | create | Cubone → Marowak |
| pokemon-hitmons | create | Hitmonlee / Hitmonchan (+ Hitmontop 후속) |
| pokemon-lickitung | create | Lickitung |
| pokemon-koffing-line | create | Koffing → Weezing |
| pokemon-rhyhorn-line | create | Rhyhorn → Rhydon (→ Rhyperior 후속) |
| pokemon-chansey | create | Chansey (→ Blissey 후속) |
| pokemon-tangela | create | Tangela |
| pokemon-kangaskhan | create | Kangaskhan |
| pokemon-horsea-line | create | Horsea → Seadra (→ Kingdra 후속) |
| pokemon-goldeen-line | create | Goldeen → Seaking |
| pokemon-staryu-line | create | Staryu → Starmie |
| pokemon-mr-mime | create | Mr. Mime |
| pokemon-scyther | create | Scyther (→ Scizor 후속) |
| pokemon-jynx | create | Jynx |
| pokemon-electabuzz | create | Electabuzz (→ Electivire 후속) |
| pokemon-magmar | create | Magmar (→ Magmortar 후속) |
| pokemon-pinsir | create | Pinsir |
| pokemon-tauros | create | Tauros |
| pokemon-magikarp-line | create | Magikarp → Gyarados |
| pokemon-lapras | create | Lapras |
| pokemon-ditto | create | Ditto |
| pokemon-eevee-line | create | Eevee → Vaporeon / Jolteon / Flareon (+ 후속 이볼루션) |
| pokemon-porygon | create | Porygon (→ Porygon2 후속) |
| pokemon-omanyte-line | create | Omanyte → Omastar |
| pokemon-kabuto-line | create | Kabuto → Kabutops |
| pokemon-aerodactyl | create | Aerodactyl |
| pokemon-snorlax | create | Snorlax |
| pokemon-articuno | create | Articuno (전설) |
| pokemon-zapdos | create | Zapdos (전설) |
| pokemon-moltres | create | Moltres (전설) |
| pokemon-dratini-line | create | Dratini → Dragonair → Dragonite |
| pokemon-mewtwo | create | Mewtwo (전설) |
| pokemon-mew | create | Mew (신화) |

### 허브 페이지 (2개)

| Concept | Action | Reason |
|---------|--------|--------|
| type-chart | create | 전체 18타입 상성 한눈에 보기 (허브) |
| pokedex-gen1 | create | 1세대 151마리 인덱스 허브 |

---

## Pages to Create

| Filename | Type | Title |
|----------|------|-------|
| `2026-06-05-pokeapi-gen1-import.md` | article | PokéAPI Gen 1 데이터 임포트 |
| `type-chart.md` | concept | 포켓몬 타입 상성표 |
| `pokedex-gen1.md` | concept | 1세대 포켓덱스 |
| `type-{name}.md` × 18 | concept | 각 타입 상성 |
| `pokemon-{line}.md` × ~72 | concept | 진화 계열별 포켓몬 |

**총 예상 페이지 수: ~95개**

---

## Contradictions Detected
없음 (신규 위키이므로 기존 페이지 없음)

## Proposed Cross-Links
- `type-chart` ↔ 각 `type-{name}` 페이지
- `pokedex-gen1` ↔ 각 `pokemon-{line}` 페이지
- 각 포켓몬 페이지 ↔ 해당 타입 페이지
- 전설 포켓몬 페이지 ↔ 레이드 관련 태그

## Items for User Review
- [ ] 포켓몬을 진화 계열별로 묶는 방식 OK? (개별 151페이지 vs 계열별 ~72페이지)
- [ ] 포켓몬 GO 전용 스탯(CP, IV)은 이 데이터에 없음 — LeekDuck 등 추가 ingestion 시 보완 필요
- [ ] 한국어 포켓몬 이름은 현재 없음 (PokéAPI는 영어 기준) — 별도 매핑 추가 여부?
