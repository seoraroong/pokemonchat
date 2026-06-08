import os
import re
import sys
import json
import base64
import asyncio
import logging
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
import anthropic
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

load_dotenv()

WIKI_DIR = Path("wiki")
INDEX_PATH = WIKI_DIR / ".llm-wiki" / "index.md"
MAX_CONTEXT_PAGES = 5

log = logging.getLogger("pogo-refresh")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 자동 갱신 설정 ────────────────────────────────────────────────────
_REFRESH_SCRIPTS: list[dict] = [
    {"name": "raids",  "script": "fetch_current_raids.py",  "interval_h": 6},
    {"name": "eggs",   "script": "fetch_eggs_and_rockets.py","interval_h": 12},
]
_refresh_status: dict[str, dict] = {
    s["name"]: {"last_ok": None, "last_err": None, "running": False}
    for s in _REFRESH_SCRIPTS
}

async def _run_script(script_name: str) -> tuple[bool, str]:
    """fetch_*.py 를 서브프로세스로 실행. (success, output) 반환."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path(__file__).parent,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        ok = proc.returncode == 0
        return ok, stdout.decode("utf-8", errors="replace").strip()
    except asyncio.TimeoutError:
        return False, "timeout (120s)"
    except Exception as e:
        return False, str(e)

async def _refresh_one(name: str, script: str) -> None:
    st = _refresh_status[name]
    if st["running"]:
        return
    st["running"] = True
    log.info(f"[refresh] {name} 갱신 시작...")
    try:
        ok, out = await _run_script(script)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if ok:
            st["last_ok"] = now
            # 캐시 무효화
            global _wiki_index_cache, _slug_dex_cache
            _wiki_index_cache = None
            _slug_dex_cache   = None
            log.info(f"[refresh] {name} 완료")
        else:
            st["last_err"] = f"{now}: {out[:200]}"
            log.warning(f"[refresh] {name} 실패: {out[:200]}")
    finally:
        st["running"] = False

async def _auto_refresh_loop() -> None:
    """서버 시작 시 1회 즉시 실행 후, 각 스크립트별 interval_h 주기로 반복."""
    # 시작 직후 첫 갱신 (10초 뒤 — 서버 완전 기동 대기)
    await asyncio.sleep(10)
    tasks = [asyncio.create_task(_refresh_one(s["name"], s["script"])) for s in _REFRESH_SCRIPTS]
    await asyncio.gather(*tasks, return_exceptions=True)

    # 이후 주기 갱신
    elapsed: dict[str, float] = {s["name"]: 0.0 for s in _REFRESH_SCRIPTS}
    tick = 60  # 1분마다 체크
    while True:
        await asyncio.sleep(tick)
        for s in _REFRESH_SCRIPTS:
            elapsed[s["name"]] = elapsed.get(s["name"], 0.0) + tick / 3600
            if elapsed[s["name"]] >= s["interval_h"]:
                elapsed[s["name"]] = 0.0
                asyncio.create_task(_refresh_one(s["name"], s["script"]))

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_auto_refresh_loop())
    log.info("[lifespan] 자동 갱신 루프 시작")
    yield
    task.cancel()
    log.info("[lifespan] 자동 갱신 루프 종료")

app = FastAPI(lifespan=lifespan)
client = anthropic.AsyncAnthropic()


@app.on_event("startup")
async def startup():
    await get_events()  # 앱 시작 시 이벤트 캐시 워밍업

SYSTEM_PROMPT = """당신은 포켓몬 GO 전문 도우미 챗봇입니다.

답변 규칙:
- 한국어로 간결하고 친절하게 답변하세요.
- 제공된 위키 데이터를 우선적으로 활용하세요.
- 포켓몬 스탯, 타입 상성, 진화 정보 등을 정확하게 안내하세요.
- 레이드 카운터(raid-counters-*), 현재 레이드 보스(current-raids) 데이터가 위키에 있습니다.
- 알 부화(eggs-1km ~ eggs-12km, eggs-hub), 로켓단 그런트(rocket-grunt-*), 로켓단 간부(rocket-leaders) 데이터가 위키에 있습니다.
- 이벤트 정보가 <event_context>로 제공된 경우 그 데이터를 기반으로 답변하세요.
- 스탯 수치나 타입 정보는 표나 목록 형식으로 깔끔하게 정리해 주세요.
"""


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


# ── Wiki index ──────────────────────────────────────────────────────

_wiki_index_cache: list[dict] | None = None


def get_wiki_index() -> list[dict]:
    global _wiki_index_cache
    if _wiki_index_cache is not None:
        return _wiki_index_cache

    if not INDEX_PATH.exists():
        return []

    pages = []
    in_table = False
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        if "| Slug | Title |" in line:
            in_table = True
            continue
        if in_table and "|---" in line:
            continue
        if in_table and line.startswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 5 and cols[0]:
                pages.append({
                    "slug": cols[0],
                    "title": cols[1],
                    "type": cols[2],
                    "lang": cols[3],
                    "summary": cols[4],
                })
        elif in_table and not line.startswith("|"):
            in_table = False

    _wiki_index_cache = pages
    return pages


# ── Event cache ─────────────────────────────────────────────────────

EVENTS_URL      = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/events.json"
EVENT_CACHE_TTL = 3600  # 1시간마다 갱신

_event_cache: list[dict] = []
_event_cache_at: float   = 0.0

EVENT_TYPE_KO = {
    "event":           "이벤트",
    "community-day":   "커뮤니티 데이",
    "raid-battles":    "레이드 배틀",
    "raid-hour":       "레이드 아워",
    "raid-day":        "레이드 데이",
    "go-battle-league":"GO 배틀리그",
    "pokemon-go-fest": "포켓몬 GO 페스트",
    "max-mondays":     "맥스 먼데이",
    "season":          "시즌",
    "twitch-drops":    "트위치 드롭",
    "go-pass":         "GO 패스",
}

_EVENT_KW = {
    "이벤트", "event", "커뮤니티데이", "커뮤니티", "community", "communityda",
    "레이드아워", "축제", "페스트", "fest",
    "배틀리그", "시즌", "season", "주간", "이번주", "진행중",
}


async def _fetch_events() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client_h:
            r = await client_h.get(EVENTS_URL)
            r.raise_for_status()
            return r.json()
    except Exception:
        return []


# ── 이벤트 상세 페이지 캐시 (URL → 텍스트, TTL 1시간) ────────────
_page_cache: dict[str, tuple[float, str]] = {}  # url → (fetched_at, text)
PAGE_CACHE_TTL = 3600

async def _fetch_event_page(url: str) -> str:
    """LeekDuck 이벤트 페이지를 fetch해서 핵심 텍스트만 반환."""
    import time
    cached = _page_cache.get(url)
    if cached and time.time() - cached[0] < PAGE_CACHE_TTL:
        return cached[1]
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as c:
            r = await c.get(url)
            html = r.text
    except Exception:
        return ""

    # CSS/JS 제거 후 텍스트 추출
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
    html = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", html)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 최대 3000자로 제한 (LLM 컨텍스트 절약)
    if len(text) > 3000:
        text = text[:3000] + "\n...(이하 생략)"

    _page_cache[url] = (time.time(), text)
    return text


# 이벤트 타입별 쿼리 감지
_EVENT_TYPE_KW: dict[str, set[str]] = {
    "community-day":    {"커뮤니티데이", "커뮤니티 데이", "community day", "communityda", "cd"},
    "pokemon-go-fest":  {"고페스트", "go fest", "gofest", "페스트", "fest"},
    "raid-hour":        {"레이드아워", "레이드 아워", "raid hour"},
    "raid-day":         {"레이드데이", "레이드 데이", "raid day"},
    "max-mondays":      {"맥스먼데이", "맥스 먼데이", "max monday"},
}

def _detect_event_type(query: str) -> str | None:
    """쿼리에서 이벤트 타입 감지. 매칭되면 eventType 문자열 반환."""
    q = query.lower()
    for etype, kws in _EVENT_TYPE_KW.items():
        if any(kw in q for kw in kws):
            return etype
    return None


async def get_events() -> list[dict]:
    """캐시된 이벤트 반환. TTL 초과 시 백그라운드 갱신."""
    global _event_cache, _event_cache_at
    import time
    now = time.time()
    if now - _event_cache_at > EVENT_CACHE_TTL:
        _event_cache = await _fetch_events()
        _event_cache_at = now
    return _event_cache


def _parse_dt(s: str) -> datetime:
    """ISO8601 문자열을 항상 timezone-aware datetime으로 파싱."""
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _format_events(events: list[dict]) -> str:
    """현재 진행 중 + 7일 이내 예정 이벤트를 LLM용 텍스트로 포맷."""
    now = datetime.now(timezone.utc)

    active, upcoming = [], []
    for e in events:
        try:
            start = _parse_dt(e["start"])
            end   = _parse_dt(e["end"])
            # offset-naive 방어
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        delta_start = (start - now).total_seconds()
        delta_end   = (end   - now).total_seconds()

        if delta_end < 0:
            continue  # 이미 종료
        if delta_start <= 0:
            active.append((start, end, e))
        elif delta_start <= 7 * 86400:
            upcoming.append((start, end, e))

    lines = []

    if active:
        lines.append("### 현재 진행 중인 이벤트")
        for start, end, e in sorted(active, key=lambda x: x[1]):
            etype = EVENT_TYPE_KO.get(e.get("eventType", ""), e.get("eventType", ""))
            end_str = end.strftime("%m/%d %H:%M") + " UTC"
            lines.append(f"- [{etype}] **{e['name']}** (~{end_str})")
            extras = e.get("extraData", {}).get("generic", {})
            notes = []
            if extras.get("hasSpawns"):       notes.append("특별 출현 포켓몬 있음")
            if extras.get("hasFieldResearchTasks"): notes.append("필드 리서치 있음")
            if notes:
                lines.append(f"  ※ {', '.join(notes)}")

    if upcoming:
        lines.append("\n### 7일 이내 예정 이벤트")
        for start, end, e in sorted(upcoming, key=lambda x: x[0]):
            etype = EVENT_TYPE_KO.get(e.get("eventType", ""), e.get("eventType", ""))
            start_str = start.strftime("%m/%d %H:%M") + " UTC"
            lines.append(f"- [{etype}] **{e['name']}** ({start_str} 시작)")

    if not lines:
        return "현재 진행 중이거나 예정된 이벤트 정보가 없습니다."

    return "\n".join(lines)


def _is_event_query(query: str) -> bool:
    tokens = _tokenize(query)
    if _EVENT_KW & tokens:
        return True
    # 복합어/공백 포함 키워드는 substring 매칭으로 추가 감지
    q = query.lower()
    return any(kw in q for kws in _EVENT_TYPE_KW.values() for kw in kws)


# ── Wiki search ─────────────────────────────────────────────────────

_TYPE_KEYWORDS = {
    "불꽃": "fire", "화염": "fire",
    "물": "water", "워터": "water",
    "전기": "electric",
    "풀": "grass", "잔디": "grass",
    "얼음": "ice",
    "격투": "fighting",
    "독": "poison",
    "땅": "ground",
    "비행": "flying",
    "에스퍼": "psychic", "사이킥": "psychic",
    "벌레": "bug",
    "바위": "rock",
    "고스트": "ghost",
    "드래곤": "dragon",
    "악": "dark",
    "강철": "steel",
    "페어리": "fairy",
    "노말": "normal",
}

_TYPE_QUERY_KEYWORDS = ["약점", "상성", "효과", "저항", "무효", "타입 상성"]

# Korean grammatical postfixes to strip when tokenizing
_KO_POSTFIXES = sorted(
    ["이야", "이에", "야", "은", "는", "이", "가", "을", "를", "의", "에", "도", "란", "랑", "으로", "로"],
    key=len, reverse=True,
)


def _tokenize(query: str) -> set[str]:
    """Split Korean/English query into tokens, stripping common postfixes."""
    raw = re.split(r"[\s?!.,/()\[\]]+", query.lower())
    result: set[str] = set()
    for t in raw:
        if not t:
            continue
        result.add(t)
        for suffix in _KO_POSTFIXES:
            if t.endswith(suffix) and len(t) > len(suffix) + 1:
                result.add(t[:-len(suffix)])
                break
    return result


def _ko_name(page: dict) -> str:
    """Extract the Korean (or right-side) name from a page title 'En / 한국어'."""
    title = page["title"]
    if "/" not in title:
        return title.lower()
    raw = title.split("/")[-1].strip().lower()
    return raw.replace(" 타입", "").strip()


_MOVE_HUB_KW = {"기술", "무브", "moves", "move"}

# 레이드 관련 키워드
_RAID_KW = {"레이드", "raid", "보스", "boss", "레이드보스", "공략", "카운터", "counter"}
_CURRENT_RAID_KW = {"현재", "지금", "이번", "today", "current", "오늘"}

# 알 관련 키워드
_EGG_KW = {"알", "egg", "eggs", "부화", "hatch", "인큐베이터"}
_EGG_KM_MAP = {
    "1km": "eggs-1km", "1킬로": "eggs-1km",
    "2km": "eggs-2km", "2킬로": "eggs-2km",
    "5km": "eggs-5km", "5킬로": "eggs-5km",
    "7km": "eggs-7km", "7킬로": "eggs-7km", "선물알": "eggs-7km",
    "10km": "eggs-10km", "10킬로": "eggs-10km",
    "12km": "eggs-12km", "12킬로": "eggs-12km", "로켓알": "eggs-12km",
}

# 로켓단 관련 키워드
_ROCKET_KW = {"로켓단", "rocket", "그런트", "grunt", "조반니", "giovanni",
              "클리프", "cliff", "아를로", "arlo", "시에라", "sierra",
              "간부", "보스", "로켓"}
_ROCKET_LEADER_KW = {"조반니", "giovanni", "클리프", "cliff", "아를로", "arlo",
                     "시에라", "sierra", "간부"}

# PvP 리그 토큰 → slug 매핑
_PVP_LEAGUE_MAP = {
    "슈퍼리그": "pvp-gl", "gl": "pvp-gl", "1500": "pvp-gl",
    "하이퍼리그": "pvp-ul", "ul": "pvp-ul", "2500": "pvp-ul",
    "마스터리그": "pvp-ml", "ml": "pvp-ml", "10000": "pvp-ml",
}
_PVP_RANK_KW = {"최강", "순위", "랭킹", "메타", "강한", "추천", "최고", "top", "강자", "배틀", "리그", "pvp"}


def _score(page: dict, tokens: set[str]) -> int:
    slug = page["slug"].lower()
    ko = _ko_name(page)
    ko_words = set(ko.split()) if ko else set()

    en_base = slug.replace("pokemon-", "").replace("type-", "").replace("move-", "")
    en = en_base.replace("-", "")

    score = 0

    # Exact single-token Korean name match
    if ko and ko in tokens:
        score += 5
    # Multi-word Korean name: 첫 단어만 일치해도 부분 점수
    elif len(ko_words) > 1:
        if ko_words <= tokens:
            score += 4
        elif ko_words & tokens:          # 일부 단어 일치
            score += len(ko_words & tokens)

    # English slug match
    if en and en in tokens:
        score += 3
    elif slug.startswith("move-"):
        parts = set(en_base.split("-"))
        matched = len(parts & tokens)
        if matched >= 2:
            score += 2
        elif matched == 1 and len(parts) == 1:
            score += 2

    # Type page: keyword match
    for ko_kw, en_type in _TYPE_KEYWORDS.items():
        if ko_kw in tokens and slug == f"type-{en_type}":
            score += 5

    # Move hub pages
    if _MOVE_HUB_KW & tokens:
        if slug == "moves-fast" and ("빠른" in tokens or "fast" in tokens):
            score += 4
        if slug == "moves-charged" and (
            "스페셜" in tokens or "차지" in tokens or "charged" in tokens
        ):
            score += 4

    # 알 페이지
    if slug.startswith("eggs-"):
        if _EGG_KW & tokens:
            if slug == "eggs-hub":
                score += 3
            else:
                km_part = slug.replace("eggs-", "")  # "1km", "2km" ...
                for token, target in _EGG_KM_MAP.items():
                    if token in tokens and target == slug:
                        score += 6
                        break
                else:
                    score += 2  # 알 키워드만 있으면 기본 점수

    # 로켓단 페이지
    if _ROCKET_KW & tokens:
        if slug == "rocket-grunts":
            score += 3
            if "그런트" in tokens or "grunt" in tokens:
                score += 2
        elif slug == "rocket-leaders":
            score += 3
            if _ROCKET_LEADER_KW & tokens:
                score += 3
        elif slug.startswith("rocket-grunt-"):
            grunt_type = slug.replace("rocket-grunt-", "")
            # 해당 타입 키워드가 쿼리에 있으면
            for ko_kw, en_type in _TYPE_KEYWORDS.items():
                if ko_kw in tokens and en_type == grunt_type:
                    score += 5
                    break
            if _ROCKET_KW & tokens:
                score += 1

    # 레이드 카운터 페이지 (raid-counters-{pokemon})
    if slug.startswith("raid-counters-"):
        if _RAID_KW & tokens:
            score += 3
            # 포켓몬 이름이 쿼리에 있으면 추가 점수
            boss_part = slug.replace("raid-counters-", "").replace("-", "")
            if boss_part and boss_part in tokens:
                score += 4
            else:
                for part in slug.replace("raid-counters-", "").split("-"):
                    if part and part in tokens:
                        score += 2
                        break

    # 현재 레이드 보스 페이지
    if slug == "current-raids":
        if _RAID_KW & tokens:
            score += 4
            if _CURRENT_RAID_KW & tokens:
                score += 3

    # 날씨 부스트 페이지
    if slug == "weather-boost":
        if {"날씨", "weather", "부스트", "boost", "맑음", "비", "구름", "흐림", "바람", "눈", "안개"} & tokens:
            score += 5

    # PvP 랭킹 허브 페이지
    if slug in ("pvp-gl", "pvp-ul", "pvp-ml"):
        for league_token, target_slug in _PVP_LEAGUE_MAP.items():
            if league_token in tokens and slug == target_slug:
                score += 5
                if _PVP_RANK_KW & tokens:
                    score += 2
                break
        # "pvp", "배틀리그", "리그" 등 일반 PvP 키워드
        if not score and _PVP_RANK_KW & tokens:
            score += 1

    return score


def find_relevant_slugs(query: str, n: int = 3) -> list[str]:
    tokens = _tokenize(query)
    scored = [(_score(p, tokens), p["slug"]) for p in get_wiki_index()]
    scored = sorted([(s, slug) for s, slug in scored if s > 0], reverse=True)
    return [slug for _, slug in scored[:n]]


def load_page(slug: str) -> str | None:
    path = WIKI_DIR / f"{slug}.md"
    return path.read_text(encoding="utf-8") if path.exists() else None


def build_wiki_context(query: str) -> tuple[str, int | None]:
    """Returns (context_text, pokemon_id_or_None)."""
    initial_slugs = find_relevant_slugs(query, n=3)

    loaded: dict[str, str] = {}
    for slug in initial_slugs:
        content = load_page(slug)
        if content:
            loaded[slug] = content

    # For type-related queries: follow [[type-X]] links from loaded Pokémon pages
    if any(kw in query.lower() for kw in _TYPE_QUERY_KEYWORDS):
        for content in list(loaded.values()):
            for type_slug in re.findall(r"\[\[(type-\w+)[^\]]*\]\]", content):
                if type_slug not in loaded and len(loaded) < MAX_CONTEXT_PAGES:
                    page = load_page(type_slug)
                    if page:
                        loaded[type_slug] = page

    if not loaded:
        fallback = load_page("type-chart")
        if fallback:
            return f"=== type-chart ===\n{fallback}", None
        return "", None

    # Extract primary Pokémon ID for sprite display
    pokemon_id: int | None = None
    index_map = {p["slug"]: p for p in get_wiki_index()}
    for slug in initial_slugs:
        if not slug.startswith("pokemon-"):
            continue
        page_meta = index_map.get(slug)
        if page_meta:
            m = re.search(r"#(\d+)", page_meta["summary"])
            if m:
                pokemon_id = int(m.group(1))
                break

    context = "\n\n".join(f"=== {slug} ===\n{content}" for slug, content in loaded.items())
    return context, pokemon_id


# ── Pokédex API ─────────────────────────────────────────────────────
_pokedex_cache: list[dict] | None = None

@app.get("/api/pokedex")
async def get_pokedex():
    global _pokedex_cache
    if _pokedex_cache is not None:
        return _pokedex_cache

    names_path = Path(".raw/go_all_names.json")
    gm_path    = Path(".raw/game_master_pokemon.json")
    if not names_path.exists() or not gm_path.exists():
        return []

    names  = json.loads(names_path.read_text(encoding="utf-8"))
    gm_raw = json.loads(gm_path.read_text(encoding="utf-8"))

    result = []
    for dex_str, nd in sorted(names.items(), key=lambda x: int(x[0])):
        dex  = int(dex_str)
        gm_d = gm_raw.get(dex_str, {})
        t2   = gm_d.get("type2", "") or ""
        if t2 == "none":
            t2 = ""
        result.append({
            "dex": dex,
            "ko":  nd["ko_name"],
            "en":  nd["en_name"],
            "gen": nd["gen"],
            "t1":  gm_d.get("type1", ""),
            "t2":  t2,
        })

    _pokedex_cache = result
    return result


# ── Pokémon detail / Events / Raids APIs ────────────────────────────

_names_raw: dict | None = None
_gm_raw:    dict | None = None
_pve_moves: dict | None = None


def _ensure_raw() -> bool:
    global _names_raw, _gm_raw, _pve_moves
    if _names_raw is not None:
        return True
    p1 = Path(".raw/go_all_names.json")
    p2 = Path(".raw/game_master_pokemon.json")
    if not p1.exists() or not p2.exists():
        return False
    _names_raw = json.loads(p1.read_text(encoding="utf-8"))
    _gm_raw    = json.loads(p2.read_text(encoding="utf-8"))
    p3 = Path(".raw/pve_moves.json")
    _pve_moves = json.loads(p3.read_text(encoding="utf-8")) if p3.exists() else {}
    return True


@app.get("/api/pokemon/{dex}")
async def get_pokemon_detail(dex: int):
    if not _ensure_raw():
        return {}
    dex_str = str(dex)
    nd  = (_names_raw or {}).get(dex_str)
    gmd = (_gm_raw or {}).get(dex_str, {})
    if not nd:
        return {}

    def move_info(mid: str) -> dict:
        m  = (_pve_moves or {}).get(mid, {})
        ko = m.get("ko_name") or mid.replace("_FAST", "").replace("_", " ").title().strip()
        return {"id": mid, "ko": ko, "type": m.get("type", "")}

    t2 = gmd.get("type2", "") or ""
    if t2 == "none":
        t2 = ""

    return {
        "dex":           dex,
        "ko":            nd["ko_name"],
        "en":            nd["en_name"],
        "gen":           nd["gen"],
        "t1":            gmd.get("type1", ""),
        "t2":            t2,
        "atk":           gmd.get("atk", 0),
        "def":           gmd.get("def", 0),
        "sta":           gmd.get("sta", 0),
        "cp40":          gmd.get("cp_40", 0),
        "fast_moves":    [move_info(m) for m in gmd.get("fast_moves", [])],
        "charged_moves": [move_info(m) for m in gmd.get("charged_moves", [])],
        "elite_fast":    [move_info(m) for m in gmd.get("elite_fast", [])],
        "elite_charged": [move_info(m) for m in gmd.get("elite_charged", [])],
    }


@app.get("/api/events")
async def get_events_api():
    events = await get_events()
    now    = datetime.now(timezone.utc)
    active: list[dict] = []
    upcoming: list[dict] = []
    for e in events:
        try:
            start = _parse_dt(e["start"])
            end   = _parse_dt(e["end"])
        except Exception:
            continue
        if (end - now).total_seconds() < 0:
            continue
        ds   = (start - now).total_seconds()
        item = {"name": e["name"], "type": e.get("eventType", ""),
                "link": e.get("link", ""), "start": e["start"], "end": e["end"]}
        if ds <= 0:
            active.append(item)
        elif ds <= 7 * 86400:
            upcoming.append(item)
    active.sort(key=lambda x: x["end"])
    upcoming.sort(key=lambda x: x["start"])
    return {"active": active, "upcoming": upcoming}


@app.get("/api/raids")
async def get_raids_api():
    p = Path(".raw/current_raids.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ── Slug → dex lookup ────────────────────────────────────────────────
_slug_dex_cache: dict[str, int] | None = None

def _get_slug_dex_map() -> dict[str, int]:
    global _slug_dex_cache
    if _slug_dex_cache is not None:
        return _slug_dex_cache
    if not _ensure_raw():
        _slug_dex_cache = {}
        return _slug_dex_cache
    result: dict[str, int] = {}
    for dex_str, nd in (_names_raw or {}).items():
        en   = nd["en_name"]
        slug = re.sub(r"[^a-z0-9-]", "", en.lower().replace(" ", "-").replace("'", "").replace(".", ""))
        result[slug] = int(dex_str)
    _slug_dex_cache = result
    return result


# ── Raid counters API ────────────────────────────────────────────────
_COUNTER_PREFIXES = ("shadow-", "mega-", "alolan-", "galarian-", "hisuian-", "paldean-")

@app.get("/api/raid-counters/{slug}")
async def get_raid_counters_api(slug: str):
    path = WIKI_DIR / f"raid-counters-{slug}.md"
    if not path.exists():
        base = slug
        found = False
        for pfx in _COUNTER_PREFIXES:
            if base.startswith(pfx):
                base = base[len(pfx):]
                candidate = WIKI_DIR / f"raid-counters-{base}.md"
                if candidate.exists():
                    path  = candidate
                    found = True
                    break
        if not found and not path.exists():
            return {"counters": [], "boss_ko": slug, "weakness": ""}

    content   = path.read_text(encoding="utf-8")
    boss_ko   = slug
    m = re.search(r'^# (.+?) 레이드 카운터', content, re.MULTILINE)
    if m:
        boss_ko = m.group(1).strip()

    weakness = ""
    w = re.search(r'\*\*약점:\*\* (.+?)(?:\n|$)', content)
    if w:
        weakness = w.group(1).strip()

    slug_dex = _get_slug_dex_map()
    counters: list[dict] = []
    in_table = False
    for line in content.splitlines():
        if "| 순위 |" in line:
            in_table = True; continue
        if in_table and "|---" in line:
            continue
        if in_table and line.strip().startswith("|"):
            # wikilink 내부 | 때문에 split 불가 → 라인 전체에서 regex로 직접 추출
            rank_m = re.match(r'^\|\s*(\d+)\s*\|', line.strip())
            pm = re.search(r'\[\[pokemon-([^\]|]+)\|([^\]]+)\]\]', line)
            all_links = re.findall(r'\[\[[^\]|]+\|([^\]]+)\]\]', line)
            if rank_m and pm:
                # all_links: [포켓몬명, 기술명, ...] 순서 — move는 두 번째 링크
                move_ko = all_links[1] if len(all_links) >= 2 else (all_links[0] if all_links else "")
                counters.append({
                    "rank": rank_m.group(1),
                    "dex":  slug_dex.get(pm.group(1)),
                    "ko":   pm.group(2),
                    "move": move_ko,
                })
        elif in_table and line.strip() and not line.strip().startswith("|") and not line.strip().startswith(">"):
            break

    return {"counters": counters[:15], "boss_ko": boss_ko, "weakness": weakness}


# ── Eggs API ─────────────────────────────────────────────────────────
@app.get("/api/eggs")
async def get_eggs_api():
    eggs_path = Path(".raw/eggs.json")
    if not eggs_path.exists():
        return {}
    eggs_raw = json.loads(eggs_path.read_text(encoding="utf-8"))
    _ensure_raw()

    en_to_info: dict[str, dict] = {}
    if _names_raw and _gm_raw:
        for dex_str, nd in _names_raw.items():
            gmd = _gm_raw.get(dex_str, {})
            t2  = gmd.get("type2", "") or ""
            if t2 == "none":
                t2 = ""
            en_to_info[nd["en_name"].lower()] = {
                "ko":  nd["ko_name"],
                "dex": int(dex_str),
                "t1":  gmd.get("type1", ""),
                "t2":  t2,
            }

    rarity_label = {1: "흔함", 2: "보통", 3: "드묾", 4: "레어", 5: "초레어"}
    result: dict[str, list] = {}
    for egg in eggs_raw:
        km   = egg.get("eggType", "").replace(" ", "")
        info = en_to_info.get(egg["name"].lower(), {})
        result.setdefault(km, []).append({
            "en":         egg["name"],
            "ko":         info.get("ko", egg["name"]),
            "dex":        info.get("dex"),
            "t1":         info.get("t1", ""),
            "t2":         info.get("t2", ""),
            "shiny":      egg.get("canBeShiny", False),
            "rarity":     rarity_label.get(egg.get("rarity", 1), ""),
            "rarity_num": egg.get("rarity", 1),
            "as_only":    egg.get("isAdventureSync", False),
        })
    for km in result:
        result[km].sort(key=lambda x: (-x["rarity_num"], x["dex"] or 9999))
    return result


# ── PvP Rankings API ─────────────────────────────────────────────────
_PVP_VARIANT_SUFFIXES: list[tuple[str, str]] = [
    (" (Shadow)",   "다크 "),
    (" (Galarian)",  "가라르 "),
    (" (Alolan)",    "알로라 "),
    (" (Hisuian)",   "히스이 "),
    (" (Paldean)",   "팔데아 "),
    (" (Mega)",      "메가 "),
]

def _resolve_pvp_entry(e: dict, en_lower_to_dex: dict) -> dict:
    """dex·ko_name 이 없거나 영문 그대로인 Shadow/Galarian 변형 보완."""
    dex = e.get("dex")
    ko  = e.get("ko_name") or ""
    en  = e.get("en_name") or ko or ""

    # 이미 완전한 경우
    if dex and ko and ko != en:
        return {"dex": dex, "ko": ko}

    prefix_ko = ""
    base_en   = en
    for suffix_en, pfx_ko in _PVP_VARIANT_SUFFIXES:
        if en.endswith(suffix_en):
            prefix_ko = pfx_ko
            base_en   = en[: -len(suffix_en)]
            break

    # dex 보완
    if not dex:
        dex = en_lower_to_dex.get(base_en.lower())

    # 한국어 이름 보완
    if dex and _names_raw:
        nd      = _names_raw.get(str(dex), {})
        base_ko = nd.get("ko_name") or base_en
        ko      = prefix_ko + base_ko
    elif not ko or ko == en:
        ko = prefix_ko + base_en if prefix_ko else en

    return {"dex": dex, "ko": ko}


@app.get("/api/pvp/{league}")
async def get_pvp_api(league: str):
    pvp_path = Path(".raw/pvp_rankings.json")
    if not pvp_path.exists():
        return {"entries": [], "name": league, "cp": 0}
    pvp_data = json.loads(pvp_path.read_text(encoding="utf-8"))
    league_d = pvp_data.get(league.lower())
    if not league_d:
        return {"entries": [], "name": league, "cp": 0}

    _ensure_raw()
    en_lower_to_dex: dict[str, int] = (
        {nd["en_name"].lower(): int(k) for k, nd in _names_raw.items()}
        if _names_raw else {}
    )

    def strip_wiki(s: str) -> str:
        return re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', s)

    entries = []
    for e in league_d["entries"][:50]:
        resolved = _resolve_pvp_entry(e, en_lower_to_dex)
        entries.append({
            "rank":     e["rank"],
            "dex":      resolved["dex"],
            "ko":       resolved["ko"],
            "types_ko": e.get("types_ko", ""),
            "score":    e.get("score", 0),
            "fast":     strip_wiki(e.get("fast_ko", "")),
            "charged":  strip_wiki(e.get("charged_ko", "")),
        })
    return {"entries": entries, "name": league_d["name"], "cp": league_d["cp"]}


# ── Routes ──────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """각 데이터 소스의 마지막 갱신 시각과 다음 갱신까지 시간 반환."""
    result = {}
    for s in _REFRESH_SCRIPTS:
        name = s["name"]
        st   = _refresh_status[name]
        raw_path = {
            "raids": ".raw/current_raids.json",
            "eggs":  ".raw/eggs.json",
        }.get(name)
        file_mtime = None
        if raw_path:
            p = Path(raw_path)
            if p.exists():
                from datetime import datetime as dt2
                file_mtime = dt2.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
        result[name] = {
            "last_ok":    st["last_ok"],
            "last_err":   st["last_err"],
            "running":    st["running"],
            "file_mtime": file_mtime,
            "interval_h": s["interval_h"],
        }
    return result


@app.post("/api/admin/refresh")
async def manual_refresh(name: str | None = None):
    """수동 즉시 갱신. name 미지정 시 전체 실행."""
    targets = [s for s in _REFRESH_SCRIPTS if name is None or s["name"] == name]
    if not targets:
        return JSONResponse({"error": f"unknown: {name}"}, status_code=400)
    tasks = [asyncio.create_task(_refresh_one(s["name"], s["script"])) for s in targets]
    await asyncio.gather(*tasks, return_exceptions=True)
    return {t["name"]: _refresh_status[t["name"]] for t in targets}


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path("static") / "index.html").read_text(encoding="utf-8")


@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        _stream(req.message, req.history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream(message: str, history: list[dict]) -> AsyncGenerator[str, None]:
    wiki_context, pokemon_id = build_wiki_context(message)
    system = SYSTEM_PROMPT
    if wiki_context:
        system += f"\n\n<wiki_context>\n{wiki_context}\n</wiki_context>"

    if _is_event_query(message):
        events = await get_events()
        event_text = _format_events(events)

        # 특정 이벤트 타입 감지 시 해당 페이지 상세 내용 fetch
        detected_type = _detect_event_type(message)
        detail_text = ""
        if detected_type:
            now = datetime.now(timezone.utc)
            # 진행 중 → 가장 빨리 끝나는 것 / 예정 → 가장 빨리 시작하는 것
            candidates = [
                e for e in events
                if e.get("eventType") == detected_type and e.get("link")
                and _parse_dt(e["end"]) > now
            ]
            candidates.sort(
                key=lambda e: _parse_dt(e["start"])
                if _parse_dt(e["start"]) > now
                else _parse_dt(e["end"])
            )
            if candidates:
                page_text = await _fetch_event_page(candidates[0]["link"])
                if page_text:
                    detail_text = (
                        f"\n\n### {candidates[0]['name']} 상세 정보\n"
                        f"출처: {candidates[0]['link']}\n\n{page_text}"
                    )

        system += f"\n\n<event_context>\n{event_text}{detail_text}\n</event_context>"

    # Send Pokémon ID metadata first so the frontend can show the sprite immediately
    if pokemon_id is not None:
        yield f"data: {json.dumps({'type': 'meta', 'pokemon_id': pokemon_id})}\n\n"

    messages = history + [{"role": "user", "content": message}]

    try:
        async with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    except anthropic.RateLimitError:
        yield f"data: {json.dumps({'error': '요청 한도 초과. 잠시 후 다시 시도해 주세요.'})}\n\n"
        yield "data: [DONE]\n\n"
    except anthropic.AuthenticationError:
        yield f"data: {json.dumps({'error': 'API 키 오류. .env 파일의 ANTHROPIC_API_KEY를 확인해 주세요.'})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': f'오류: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"


# ── 포켓몬 카드 스캔 ──────────────────────────────────────────────────
_CARD_SCAN_PROMPT = """\
이 이미지를 분석해줘. 포켓몬 트레이딩 카드(TCG)가 맞으면 아래 JSON 형식으로만 답해줘.
포켓몬 카드가 아니거나 카드를 인식할 수 없으면 {"error": "포켓몬 카드를 인식할 수 없어요."} 만 반환.

{
  "name_ko": "한국어 포켓몬 이름",
  "name_en": "영어 포켓몬 이름",
  "set_name": "세트/확장팩 이름",
  "card_number": "카드 번호 (예: 025/198)",
  "rarity": "희귀도 기호 (C/U/R/RR/RRR/SR/SAR/SSR/UR/HR 등)",
  "hp": HP 수치 숫자 또는 null,
  "card_type": "포켓몬/트레이너/에너지",
  "pokemon_type": "포켓몬 타입 (불꽃/물/풀/전기/에스퍼 등, 포켓몬 카드일 때만)",
  "variant": "일반/EX/V/VMAX/VSTAR/GX/ex/Full Art/Special Art 등",
  "regulation_mark": "규정 마크 알파벳 (예: F, G, H, I) 또는 null",
  "illustrator": "일러스트레이터 이름 또는 null",
  "description": "카드 한 줄 설명 (예: '팔데아 유혹 EX — 포케카 SV 시리즈')"
}

JSON 외 다른 텍스트 없이 JSON만 반환.\
"""

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

@app.post("/api/card-scan")
async def card_scan(file: UploadFile = File(...)):
    content_type = (file.content_type or "image/jpeg").split(";")[0].strip()
    if content_type not in ALLOWED_IMAGE_TYPES:
        return {"error": f"지원하지 않는 파일 형식이에요. (JPEG/PNG/WEBP/GIF)"}

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        return {"error": "파일 크기는 10MB 이하로 올려주세요."}

    b64 = base64.standard_b64encode(raw).decode()

    try:
        resp = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}},
                    {"type": "text", "text": _CARD_SCAN_PROMPT},
                ],
            }],
        )
        text = resp.content[0].text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return {"error": "카드 정보를 읽을 수 없어요."}
        card = json.loads(m.group())
        if "error" not in card:
            name_ko  = card.get("name_ko") or card.get("name_en") or "포켓몬"
            set_name = card.get("set_name") or ""
            card_num = card.get("card_number") or ""
            q_kream  = urllib.parse.quote(f"{name_ko} 포켓몬 카드")
            q_google = urllib.parse.quote(f"{name_ko} {set_name} {card_num} 포켓몬카드 시세")
            card["kream_url"]  = f"https://kream.co.kr/search?keyword={q_kream}"
            card["google_url"] = f"https://www.google.com/search?q={q_google}"
        return card
    except json.JSONDecodeError:
        return {"error": "카드 정보 파싱에 실패했어요."}
    except anthropic.AuthenticationError:
        return {"error": "API 키 오류"}
    except Exception as e:
        return {"error": f"오류: {str(e)}"}
