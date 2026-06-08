---
title: "Dark 타입 / 악 타입"
type: concept
language: ko
created: 2026-06-05
modified: 2026-06-05
tags: [pokemon, type, type-chart, gen1]
aliases: ["악", "dark"]
summary: "포켓몬 악 타입의 공격/방어 상성 관계"
---

# Dark 타입 / 악 타입

## Definition / 정의
포켓몬의 18개 타입 중 하나인 **악 타입**의 공격 및 방어 상성 정보입니다.
포켓몬 GO 레이드/배틀에서 타입 상성은 데미지 배율에 직접 영향을 줍니다.

## 공격 상성 (이 타입 기술 사용 시)

| 효과 | 배율 | 대상 타입 |
|------|------|----------|
| 효과 굉장 | ×2 | [[type-ghost|고스트]], [[type-psychic|에스퍼]] |
| 효과 별로 | ×0.5 | [[type-fighting|격투]], [[type-dark|악]], [[type-fairy|페어리]] |
| 효과 없음 | ×0 | 없음 |

## 방어 상성 (이 타입 포켓몬이 받는 데미지)

| 효과 | 배율 | 공격 타입 |
|------|------|----------|
| 약점 (2배 피해) | ×2 | [[type-fighting|격투]], [[type-bug|벌레]], [[type-fairy|페어리]] |
| 저항 (0.5배 피해) | ×0.5 | [[type-ghost|고스트]], [[type-dark|악]] |
| 무효 (0배 피해) | ×0 | [[type-psychic|에스퍼]] |

## Related Concepts / 관련 개념
- [[type-chart]] — 전체 18타입 상성표
- [[pokedex-gen1]] — 1세대 포켓몬 목록

## References / 참고
- Source: PokéAPI v2 type endpoint
- Hash: `2e27dd7b35c198fa1ceb16b2596ea6655f59bc74eb1f5006d1880e369ee71fe5`
