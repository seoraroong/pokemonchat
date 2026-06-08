---
title: "PokéAPI Gen 1 데이터 임포트"
type: article
language: ko
created: 2026-06-05
modified: 2026-06-05
tags: [pokemon, gen1, pokeapi, import, data-source]
summary: "PokéAPI에서 1세대 포켓몬 151마리 스탯 및 18개 타입 상성 데이터를 가져와 위키에 구축한 기록"
source_hashes:
  - "2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5"
  - "bb8096ad5a0b2c74200879a8a90f450de39cf76898c0fd158d85011302b5f3d5"
status: published
---

# PokéAPI Gen 1 데이터 임포트

## Summary / 요약
PokéAPI(https://pokeapi.co)의 공개 REST API를 통해 1세대 포켓몬 151마리의 기본 스탯, 타입, 진화 정보와 18개 타입의 공격/방어 상성 데이터를 수집해 위키에 구축했습니다.

## Content / 내용

### 수집 데이터
- **type_effectiveness.json** — 18개 타입 × 6개 관계 (공격/방어 × 2배/0.5배/무효)
- **gen1_pokemon.json** — 151마리 × 스탯(HP/공/방/특공/특방/스피드) + 타입 + 진화 + 한국어/영어 이름

### 생성된 위키 페이지
- 타입 개념 페이지 18개: `type-fire.md`, `type-water.md` 등
- 타입 상성 허브: `type-chart.md`
- 포켓몬 개념 페이지 151개: `pokemon-pikachu.md` 등
- 포켓덱스 허브: `pokedex-gen1.md`

### 한계
- 포켓몬 GO 전용 스탯(CP 계수, IV 등)은 포함되지 않음 → LeekDuck 등 후속 ingestion 필요
- 2세대 이후 포켓몬 미포함 → 추가 ingestion 계획

## Key Takeaways / 핵심
- 타입 상성은 [[type-chart]]에서 한눈에 확인 가능
- 각 포켓몬은 `evolution_line` 태그로 계열 그룹화 가능
- 포켓몬 GO에서 배틀/레이드 시 타입 배율은 메인 시리즈와 다름 (×1.6 / ×0.625)

## 출처
| 소스 | 섹션/페이지 | URL |
|------|------------|-----|
| PokéAPI | /api/v2/type | https://pokeapi.co/api/v2/type |
| PokéAPI | /api/v2/pokemon | https://pokeapi.co/api/v2/pokemon |
| PokéAPI | /api/v2/pokemon-species | https://pokeapi.co/api/v2/pokemon-species |

## Related / 관련
- [[type-chart]] — 타입 상성 허브
- [[pokedex-gen1]] — 포켓몬 목록
