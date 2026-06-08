"""
update_wiki_go.py
.raw/go_pokemon_stats.json 을 읽어 각 포켓몬 위키 페이지에
"## 포켓몬 GO 스탯" 섹션을 추가(또는 교체).
"""
import sys, json, os, re

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR   = ".raw"
WIKI_DIR  = "wiki"
INPUT     = os.path.join(RAW_DIR, "go_pokemon_stats.json")

GO_SECTION_MARKER = "## 포켓몬 GO 스탯"


def build_go_section(data: dict) -> str:
    atk  = data["atk"]
    def_ = data["def"]
    sta  = data["sta"]
    cp40 = data["cp_40"]
    cp50 = data["cp_50"]
    buddy = data["buddy_km"]
    fast    = data.get("fast_moves", [])
    charged = data.get("charged_moves", [])

    fast_str    = ", ".join(fast)    if fast    else "—"
    charged_str = ", ".join(charged) if charged else "—"

    return "\n".join([
        GO_SECTION_MARKER,
        "",
        "| 항목 | 수치 |",
        "|------|------|",
        f"| 공격 (GO) | {atk} |",
        f"| 방어 (GO) | {def_} |",
        f"| 체력 (GO) | {sta} |",
        f"| 최대 CP (Lv.40) | {cp40:,} |",
        f"| 최대 CP (Lv.50) | {cp50:,} |",
        f"| 버디 거리 | {buddy}km |",
        "",
        "### 기술 풀 (GO)",
        f"- **빠른 기술:** {fast_str}",
        f"- **스페셜 기술:** {charged_str}",
        "",
    ])


def update_page(path: str, go_section: str) -> bool:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    if GO_SECTION_MARKER in content:
        # 기존 섹션 교체: GO 섹션 시작부터 다음 ## 까지
        pattern = re.compile(
            r"(## 포켓몬 GO 스탯\n.*?)(?=\n## |\Z)",
            re.DOTALL,
        )
        new_content = pattern.sub(go_section.rstrip("\n"), content, count=1)
        changed = new_content != content
    else:
        # ## References 직전에 삽입, 없으면 맨 끝
        if "## References" in content:
            new_content = content.replace(
                "## References",
                go_section + "## References",
                1,
            )
        else:
            new_content = content.rstrip("\n") + "\n\n" + go_section

        changed = True

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return changed


# ── 메인 ─────────────────────────────────────────────────────────────
with open(INPUT, encoding="utf-8") as f:
    go_stats: dict[str, dict] = json.load(f)

updated = 0
skipped = 0

for slug, data in go_stats.items():
    wiki_path = os.path.join(WIKI_DIR, f"pokemon-{slug}.md")
    if not os.path.exists(wiki_path):
        print(f"  [없음] {wiki_path}")
        skipped += 1
        continue

    go_section = build_go_section(data)
    changed = update_page(wiki_path, go_section)
    status = "UPDATE" if changed else "SKIP"
    print(f"  {status}  #{data['id']:03d} {slug}  CP40={data['cp_40']:,}")
    if changed:
        updated += 1
    else:
        skipped += 1

print(f"\n[완료] {updated}개 업데이트, {skipped}개 건너뜀")
print("다음: python build_wiki_index.py  (인덱스 재빌드)")
