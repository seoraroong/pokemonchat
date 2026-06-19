import os
import re
import sys
import json
import base64
import asyncio
import logging
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
import anthropic
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

WIKI_DIR = Path("wiki")
INDEX_PATH = WIKI_DIR / ".llm-wiki" / "index.md"
MAX_CONTEXT_PAGES = 5

log = logging.getLogger("pogo-refresh")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── 자동 갱신 설정 ────────────────────────────────────────────────────
_REFRESH_SCRIPTS: list[dict] = [
    {"name": "raids",    "script": "fetch_current_raids.py",    "interval_h": 6},
    {"name": "eggs",     "script": "fetch_eggs_and_rockets.py","interval_h": 12},
    {"name": "research", "script": "fetch_field_research.py",  "interval_h": 24},
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
    if name == "raids":
        lock_path = Path(".raw/raids_lock")
        if lock_path.exists():
            import re as _re
            from datetime import date as _date
            text = lock_path.read_text(encoding="utf-8")
            m = _re.search(r'(\d{4}-\d{2}-\d{2})', text)
            if m:
                age = (_date.today() - _date.fromisoformat(m.group(1))).days
                if age < 7:
                    log.info(f"[raids] raids_lock 존재 ({age}일 경과) — 자동 갱신 건너뜀")
                    return
                log.info(f"[raids] raids_lock 만료 ({age}일 경과) — lock 해제 후 갱신")
                lock_path.unlink()
            else:
                log.info("[raids] raids_lock 존재 (날짜 없음) — 자동 갱신 건너뜀")
                return
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
            # 레이드 갱신 시 위키 페이지도 업데이트
            if name == "raids":
                try:
                    _update_raids_wiki()
                    log.info("[refresh] current-raids.md 위키 업데이트 완료")
                except Exception as e:
                    log.warning(f"[refresh] current-raids.md 위키 업데이트 실패: {e}")
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
- 레이드 카운터(raid-counters-*) 데이터가 위키에 있습니다.
- 현재 레이드 보스와 알 부화 정보는 ScrapedDuck에서 실시간으로 가져옵니다.
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


_REGION_PREFIX_KO: dict[str, str] = {
    "hisuian": "히스이",
    "galarian": "가라르",
    "alolan": "알로라",
    "paldean": "팔데아",
    "shadow": "다크",
    "mega": "메가",
}

_BONUS_TERM_KO: dict[str, str] = {
    "increased spawns": "야생 출현 증가",
    "increased spawn": "야생 출현 증가",
    "3x catch stardust": "포획 별의 모래 3배",
    "2x catch stardust": "포획 별의 모래 2배",
    "3x catch xp": "포획 경험치 3배",
    "2x catch xp": "포획 경험치 2배",
    "3x catch candy": "포획 사탕 3개",
    "2x catch candy": "포획 사탕 2개",
    "2x candy": "사탕 2배",
    "3x candy": "사탕 3배",
    "2x chance to receive candy xl": "왕사탕 획득 확률 2배",
    "candy xl": "왕사탕",
    "3-hour incense": "인센스 3시간",
    "1-hour lures": "루어 모듈 1시간",
    "lure modules": "루어 모듈",
    "one additional special trade": "스페셜 교환 1회 추가",
    "trades made will require 50% less stardust": "교환 별의 모래 50% 감소",
    "50% less stardust": "별의 모래 50% 감소",
    "half stardust": "별의 모래 절반",
    "egg hatch distance": "알 부화 거리",
    "1/4 egg hatch distance": "알 부화 거리 1/4",
    "1/2 egg hatch distance": "알 부화 거리 1/2",
    "buddy distance": "버디 거리",
    "stardust": "별의 모래",
    "special trade": "스페셜 교환",
    "pokemon go fest": "포켓몬 GO 페스트",
    "community day": "커뮤니티 데이",
}

def _translate_bonus(text: str) -> str:
    lower = text.lower()
    for en, ko in _BONUS_TERM_KO.items():
        if en in lower:
            return text.replace(text, ko) if lower == en else text
    return text

def _extract_bonuses_from_extra(ed: dict, etype: str) -> list[str]:
    bonuses: list[str] = []
    # Community Day 구조화 보너스
    cd = ed.get("communityday", {})
    for b in cd.get("bonuses", []):
        t = (b.get("text") or "").strip()
        if t:
            bonuses.append(_translate_bonus(t))
    # Raid Battles 보스 목록
    rb = ed.get("raidbattles", {})
    for boss in rb.get("bosses", []):
        name = (boss.get("name") or "").strip()
        if name:
            ko = _poke_en_to_ko(name)
            shiny = " ✦ 색변 가능" if boss.get("canBeShiny") else ""
            bonuses.append(f"레이드 보스: {ko}{shiny}")
    # Max Monday 보스
    mm = ed.get("maxmonday", {})
    for boss in mm.get("bosses", []):
        name = (boss.get("name") or "").strip()
        if name:
            bonuses.append(f"맥스 배틀 보스: {_poke_en_to_ko(name)}")
    return bonuses


_MONTH_KO: dict[str, str] = {
    "january": "1월", "february": "2월", "march": "3월", "april": "4월",
    "may": "5월", "june": "6월", "july": "7월", "august": "8월",
    "september": "9월", "october": "10월", "november": "11월", "december": "12월",
}

_KNOWN_EVENTS_KO: dict[str, str] = {
    "forever forward": "포에버 포워드",
    "go battle day": "GO 배틀 데이",
    "raid weekend": "레이드 위크엔드",
    "adventure week": "어드벤처 위크",
    "water festival": "워터 페스티벌",
    "halloween": "할로윈",
    "festival of lights": "빛의 축제",
    "spring into spring": "봄맞이 이벤트",
    "spring event": "봄 이벤트",
    "winter holiday": "겨울 이벤트",
    "shedding light on uxie": "유크시의 빛",
}

_EVENT_TERM_KO: dict[str, str] = {
    "community day": "커뮤니티 데이",
    "spotlight hour": "스포트라이트 아워",
    "raid hour": "레이드 아워",
    "raid day": "레이드 데이",
    "super mega raid day": "슈퍼 메가 레이드 데이",
    "raid battles": "레이드",
    "shadow raids": "쉐도우 레이드",
    "max monday": "맥스 먼데이",
    "great league": "슈퍼리그",
    "ultra league": "하이퍼리그",
    "master league": "마스터리그",
    "little cup": "리틀컵",
    "go battle league": "GO 배틀리그",
    "pokémon go fest": "포켓몬 GO 페스트",
    "pokemon go fest": "포켓몬 GO 페스트",
    "pokémon": "포켓몬",
    "pokemon": "포켓몬",
    "dynamax": "다이맥스",
    "gigantamax": "거다이맥스",
    "go tour": "GO 투어",
    "go pass": "GO 패스",
    "in mega raids": "메가 레이드",
    "in 5-star raid battles": "5성 레이드",
    "in 4-star raid battles": "4성 레이드",
    "in 3-star raid battles": "3성 레이드",
    "in 1-star raid battles": "1성 레이드",
    "during max monday": "맥스 먼데이 중",
    "north america": "북미",
    "europe": "유럽",
    "asia-pacific": "아시아태평양",
    "latin america": "중남미",
    "international championships": "인터내셔널 챔피언십",
    "championships": "챔피언십",
    "championship": "챔피언십",
    " and ": " & ",
    "edition": "에디션",
    "cup": "컵",
    "season": "시즌",
    "choose your path": "나만의 여정 선택",
}

def _build_en_ko_lookup() -> dict[str, str]:
    if not _names_raw:
        return {}
    result: dict[str, str] = {}
    for nd in _names_raw.values():
        en = (nd.get("en_name") or "").strip()
        ko = (nd.get("ko_name") or "").strip()
        if en and ko:
            result[en.lower()] = ko
    return result

_en_ko_cache: dict[str, str] | None = None

def _poke_en_to_ko(en_name: str) -> str:
    global _en_ko_cache
    if _en_ko_cache is None or (not _en_ko_cache and _names_raw):
        _en_ko_cache = _build_en_ko_lookup()
    name = en_name.strip()
    lower = name.lower()
    # 직접 매칭
    if lower in _en_ko_cache:
        return _en_ko_cache[lower]
    # 지역 접두사 처리 (e.g. "Hisuian Growlithe")
    for prefix_en, prefix_ko in _REGION_PREFIX_KO.items():
        if lower.startswith(prefix_en + " "):
            base = name[len(prefix_en)+1:]
            base_ko = _en_ko_cache.get(base.lower(), base)
            return f"{prefix_ko} {base_ko}"
    return name  # 번역 없으면 원문 유지

def _apply_terms(text: str) -> str:
    import re as _re
    result = text
    for en, ko in _EVENT_TERM_KO.items():
        result = _re.sub(_re.escape(en), ko, result, flags=_re.IGNORECASE)
    return result.strip()

def _translate_event_name(name: str, event_type: str) -> str:
    """이벤트 이름을 한국어로 번역."""
    import re as _re
    n = name.strip()

    # 알려진 고유 이벤트명 직접 매핑
    if n.lower() in _KNOWN_EVENTS_KO:
        return _KNOWN_EVENTS_KO[n.lower()]

    # Community Day
    m = _re.match(r"^(.+?)\s+Community Day$", n, _re.IGNORECASE)
    if m:
        return f"{_poke_en_to_ko(m.group(1))} 커뮤니티 데이"

    # Spotlight Hour
    m = _re.match(r"^(.+?)\s+Spotlight Hour$", n, _re.IGNORECASE)
    if m:
        return f"{_poke_en_to_ko(m.group(1))} 스포트라이트 아워"

    # Raid Hour: "Necrozma Raid Hour" / "Celesteela and Kartana Raid Hour"
    m = _re.match(r"^(.+?)\s+Raid Hour$", n, _re.IGNORECASE)
    if m:
        pokemons = [p.strip() for p in _re.split(r"\s+and\s+", m.group(1), flags=_re.IGNORECASE)]
        ko_names = " & ".join(_poke_en_to_ko(p) for p in pokemons)
        return f"{ko_names} 레이드 아워"

    # Raid Day
    m = _re.match(r"^(.+?)\s+(?:Super Mega )?Raid Day$", n, _re.IGNORECASE)
    if m:
        return f"{_poke_en_to_ko(m.group(1))} 레이드 데이"

    # N-star Raid Battles: "Zekrom in 5-star Raid Battles"
    m = _re.match(r"^(.+?)\s+in\s+(\d+)-star Raid Battles$", n, _re.IGNORECASE)
    if m:
        return f"{_poke_en_to_ko(m.group(1))} {m.group(2)}성 레이드"

    # Mega Raids: "Mega Lopunny in Mega Raids"
    m = _re.match(r"^Mega (.+?)\s+in Mega Raids$", n, _re.IGNORECASE)
    if m:
        return f"메가 {_poke_en_to_ko(m.group(1))} 메가 레이드"

    # Shadow Raids: "Shadow Dialga in Shadow Raids"
    m = _re.match(r"^Shadow (.+?)\s+in Shadow Raids$", n, _re.IGNORECASE)
    if m:
        return f"다크 {_poke_en_to_ko(m.group(1))} 쉐도우 레이드"

    # Max Monday: "Dynamax Roggenrola during Max Monday"
    m = _re.match(r"^Dynamax (.+?)\s+during Max Monday$", n, _re.IGNORECASE)
    if m:
        return f"맥스 먼데이: 다이맥스 {_poke_en_to_ko(m.group(1))}"

    # GO Fest: "Pokémon GO Fest 2026: Copenhagen"
    m = _re.match(r"^Pok[eé]mon GO Fest (\d+):\s*(.+)$", n, _re.IGNORECASE)
    if m:
        return f"포켓몬 GO 페스트 {m.group(1)}: {m.group(2)}"

    # GO Tour: "Pokémon GO Tour: Unova"
    m = _re.match(r"^Pok[eé]mon GO Tour:\s*(.+)$", n, _re.IGNORECASE)
    if m:
        return f"포켓몬 GO 투어: {m.group(1)}"

    # GO Pass: "GO Pass: June"
    m = _re.match(r"^GO Pass:\s*(.+)$", n, _re.IGNORECASE)
    if m:
        month_ko = _MONTH_KO.get(m.group(1).strip().lower(), m.group(1).strip())
        return f"GO 패스: {month_ko}"

    # Go Battle League — 파이프 구분자로 구분된 경우 앞부분만 번역
    if event_type == "go-battle-league" or "|" in n:
        parts = [p.strip() for p in n.split("|")]
        return _apply_terms(parts[0])

    # 매칭 없으면 알려진 용어만 치환
    return _apply_terms(n)


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
            "dex":      dex,
            "ko":       nd["ko_name"],
            "en":       nd["en_name"],
            "gen":      nd["gen"],
            "t1":       gm_d.get("type1", ""),
            "t2":       t2,
            "has_mega": any("mega" in k for k in gm_d.get("variant_forms", {})),
        })

    _pokedex_cache = result
    return result


# ── Pokémon detail / Events / Raids APIs ────────────────────────────

_names_raw:         dict | None = None
_gm_raw:            dict | None = None
_pve_moves:         dict | None = None
_move_en2ko:        dict | None = None   # en_name → ko_name
_move_type_map:     dict | None = None  # en_name → (type_en, type_ko)
_go_moves_en:       dict | None = None   # en_name → full move dict (for raid DPS)
_evo_extras:        dict | None = None   # dex_str → GO-specific evolution conditions
_type_effectiveness: dict | None = None  # type → {double_damage_from, half_damage_from, no_damage_from}
_flavor_texts:      dict | None = None  # dex_str → {ko, en}


def _ensure_raw() -> bool:
    global _names_raw, _gm_raw, _pve_moves, _move_en2ko, _move_type_map, _go_moves_en, _evo_extras, _type_effectiveness, _flavor_texts
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
    p4 = Path(".raw/go_moves.json")
    if p4.exists():
        go_moves = json.loads(p4.read_text(encoding="utf-8"))
        _move_en2ko   = {v["en_name"]: v["ko_name"] for v in go_moves.values() if v.get("en_name") and v.get("ko_name")}
        _move_type_map = {v["en_name"]: (v.get("type", ""), v.get("type_ko", "")) for v in go_moves.values() if v.get("en_name")}
        _go_moves_en  = {v["en_name"]: v for v in go_moves.values() if v.get("en_name")}
    else:
        _move_en2ko = {}; _move_type_map = {}; _go_moves_en = {}
    p5 = Path(".raw/go_evo_extras.json")
    _evo_extras = json.loads(p5.read_text(encoding="utf-8")) if p5.exists() else {}
    p6 = Path(".raw/type_effectiveness.json")
    _type_effectiveness = json.loads(p6.read_text(encoding="utf-8")) if p6.exists() else {}
    p7 = Path(".raw/flavor_texts.json")
    _flavor_texts = json.loads(p7.read_text(encoding="utf-8")) if p7.exists() else {}
    return True


def _calc_weaknesses(t1: str, t2: str) -> dict[str, list]:
    """주어진 타입 조합에 대한 약점/내성/무효 계산."""
    te = _type_effectiveness or {}
    if not te or not t1:
        return {}
    result: dict[str, list] = {"weak": [], "resist": [], "immune": []}
    for atk_t in te:
        def eff(defender_type: str) -> float:
            td = te.get(defender_type, {})
            if atk_t in td.get("double_damage_from", []): return 2.0
            if atk_t in td.get("no_damage_from",     []): return 0.0
            if atk_t in td.get("half_damage_from",   []): return 0.5
            return 1.0
        combined = eff(t1) * (eff(t2) if t2 else 1.0)
        if combined >= 2:
            result["weak"].append({"type": atk_t, "mult": combined})
        elif combined == 0:
            result["immune"].append({"type": atk_t, "mult": 0})
        elif combined < 1:
            result["resist"].append({"type": atk_t, "mult": combined})
    return result


def _make_move_info(mid: str) -> dict:
    """기술 이름(en) → id/ko/타입/DPS/EPS 딕셔너리."""
    ko = (_move_en2ko or {}).get(mid, mid)
    type_en, type_ko = (_move_type_map or {}).get(mid, ("", ""))
    pve_key = mid.upper().replace(" ", "_")
    pve = (_pve_moves or {}).get(pve_key, {})
    return {
        "id": mid, "ko": ko, "type": type_en, "type_ko": type_ko,
        "dps": round(pve["dps_pve"], 2) if pve.get("dps_pve") is not None else None,
        "eps": round(pve["eps_pve"], 2) if pve.get("is_fast") and pve.get("eps_pve") is not None else None,
    }


@app.get("/api/pokemon/{dex}")
async def get_pokemon_detail(dex: int):
    if not _ensure_raw():
        return {}
    dex_str = str(dex)
    nd  = (_names_raw or {}).get(dex_str)
    gmd = (_gm_raw or {}).get(dex_str, {})
    if not nd:
        return {}

    t1 = gmd.get("type1", "")
    t2 = gmd.get("type2", "") or ""
    if t2 == "none":
        t2 = ""

    return {
        "dex":           dex,
        "ko":            nd["ko_name"],
        "en":            nd["en_name"],
        "gen":           nd["gen"],
        "t1":            t1,
        "t2":            t2,
        "atk":           gmd.get("atk", 0),
        "def":           gmd.get("def", 0),
        "sta":           gmd.get("sta", 0),
        "cp40":          gmd.get("cp_40", 0),
        "fast_moves":    [_make_move_info(m) for m in gmd.get("fast_moves", [])],
        "charged_moves": [_make_move_info(m) for m in gmd.get("charged_moves", [])],
        "elite_fast":    [_make_move_info(m) for m in gmd.get("elite_fast", [])],
        "elite_charged": [_make_move_info(m) for m in gmd.get("elite_charged", [])],
        "weaknesses":    _calc_weaknesses(t1, t2),
        "forms":         _get_forms_for_dex(dex),
        "flavor_text":   (_flavor_texts or {}).get(dex_str, {}).get("ko") or
                         (_flavor_texts or {}).get(dex_str, {}).get("en", ""),
    }


# ── Evolution chain API ──────────────────────────────────────────────
_evo_cache: dict[int, dict] = {}


def _flatten_evo_chain(node: dict) -> list[list[int]]:
    """진화 트리를 단계별 dex 목록 [[stage0], [stage1], ...]으로 변환."""
    result: list[list[int]] = []

    def _walk(n: dict, depth: int) -> None:
        dex = int(n["species"]["url"].rstrip("/").split("/")[-1])
        while len(result) <= depth:
            result.append([])
        if dex not in result[depth]:
            result[depth].append(dex)
        for child in n.get("evolves_to", []):
            _walk(child, depth + 1)

    _walk(node, 0)
    return [s for s in result if s]


@app.get("/api/evolutions/{dex}")
async def get_evolutions(dex: int):
    if dex in _evo_cache:
        return _evo_cache[dex]
    _ensure_raw()
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            spec_r = await c.get(f"https://pokeapi.co/api/v2/pokemon-species/{dex}/")
            spec_r.raise_for_status()
            evo_url = spec_r.json()["evolution_chain"]["url"]
            evo_r = await c.get(evo_url)
            evo_r.raise_for_status()
            stages_raw = _flatten_evo_chain(evo_r.json()["chain"])
    except Exception:
        return {"chain": []}

    chain = []
    for stage in stages_raw:
        s = []
        for d in stage:
            nd = (_names_raw or {}).get(str(d))
            if nd:
                s.append({"dex": d, "ko": nd["ko_name"], "en": nd["en_name"]})
        if s:
            chain.append(s)

    # GO 전용 진화 조건 주입
    if _evo_extras:
        for stage in chain:
            for entry in stage:
                cond = _evo_extras.get(str(entry["dex"]))
                if cond:
                    entry["cond"] = cond

    result = {"chain": chain}
    _evo_cache[dex] = result
    return result


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
        ds  = (start - now).total_seconds()
        ed  = e.get("extraData", {})
        has_spawns = bool(
            ed.get("generic", {}).get("hasSpawns") or
            ed.get("communityday", {}).get("spawns") or
            ed.get("raidbattles", {})
        )
        etype = e.get("eventType", "")
        _ensure_raw()
        bonuses = _extract_bonuses_from_extra(ed, etype)
        # 레이드 보스 상세 (이벤트 시트 정보 탭용)
        raid_bosses = []
        for boss in (ed.get("raidbattles") or {}).get("bosses", []):
            en = (boss.get("name") or "").strip()
            if not en:
                continue
            en2 = _get_en2info()
            info = en2.get(en.lower())
            dex = info[0] if info else 0
            ko  = info[1] if info else _poke_en_to_ko(en)
            slug = re.sub(r"[^a-z0-9-]", "", en.lower().replace(" ", "-").replace("'", ""))
            raid_bosses.append({"en": en, "ko": ko, "dex": dex, "slug": slug,
                                "can_shiny": bool(boss.get("canBeShiny", False))})
        item = {
            "name": _translate_event_name(e["name"], etype),
            "type": etype,
            "link": e.get("link", ""), "start": e["start"], "end": e["end"],
            "has_spawns": has_spawns,
            "bonuses": bonuses,
            "raid_bosses": raid_bosses,
        }
        if ds <= 0:
            active.append(item)
        elif ds <= 7 * 86400:
            upcoming.append(item)
    active.sort(key=lambda x: x["end"])
    upcoming.sort(key=lambda x: x["start"])
    return {"active": active, "upcoming": upcoming}


_html_cache: dict[str, tuple[float, str]] = {}
HTML_CACHE_TTL = 3600

async def _fetch_html(url: str) -> str:
    import time
    cached = _html_cache.get(url)
    if cached and time.time() - cached[0] < HTML_CACHE_TTL:
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
    _html_cache[url] = (time.time(), html)
    return html


# ── 레이드 라이브 fetch ───────────────────────────────────────────
SCRAPED_DUCK_RAIDS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/raids.json"
_raids_live_cache: dict = {}
_raids_live_at: float = 0.0
RAIDS_LIVE_TTL = 600  # 10분 캐시

_TIER_NORM = {
    "1-star raids": "1", "1-star": "1",
    "3-star raids": "3", "3-star": "3",
    "5-star raids": "5", "5-star": "5",
    "mega raids": "mega", "mega": "mega",
    "mega legendary raids": "mega_legendary",
    "elite raids": "elite",
}
_RAID_TYPE_KO = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기",
    "grass":"풀","ice":"얼음","fighting":"격투","poison":"독",
    "ground":"땅","flying":"비행","psychic":"에스퍼","bug":"벌레",
    "rock":"바위","ghost":"고스트","dragon":"드래곤","dark":"악",
    "steel":"강철","fairy":"페어리",
}
_RAID_PREFIXES = [
    ("mega ", "메가 "), ("shadow ", "다크 "), ("alolan ", "알로라 "),
    ("galarian ", "가라르 "), ("hisuian ", "히스이 "), ("paldean ", "팔데아 "),
]

# PokeAPI regional form IDs (일반 dex 번호와 다른 경우만)
_REGIONAL_FORM_DEX: dict[str, int] = {
    "alolan rattata": 10091, "alolan raticate": 10092, "alolan raichu": 10100,
    "alolan sandshrew": 10101, "alolan sandslash": 10102, "alolan vulpix": 10103,
    "alolan ninetales": 10104, "alolan diglett": 10105, "alolan dugtrio": 10106,
    "alolan meowth": 10107, "alolan persian": 10108, "alolan geodude": 10109,
    "alolan graveler": 10110, "alolan golem": 10111, "alolan grimer": 10112,
    "alolan muk": 10113, "alolan exeggutor": 10114, "alolan marowak": 10115,
    "galarian meowth": 10161, "galarian ponyta": 10162, "galarian rapidash": 10163,
    "galarian slowpoke": 10164, "galarian slowbro": 10165, "galarian farfetch'd": 10166,
    "galarian weezing": 10167, "galarian mr. mime": 10168, "galarian corsola": 10173,
    "galarian zigzagoon": 10174, "galarian linoone": 10175, "galarian darumaka": 10176,
    "galarian darmanitan": 10177, "galarian yamask": 10179, "galarian stunfisk": 10180,
    "hisuian growlithe": 10229, "hisuian arcanine": 10230, "hisuian voltorb": 10231,
    "hisuian electrode": 10232, "hisuian typhlosion": 10233, "hisuian qwilfish": 10234,
    "hisuian sneasel": 10235, "hisuian samurott": 10236, "hisuian lilligant": 10237,
    "hisuian zorua": 10238, "hisuian zoroark": 10239, "hisuian braviary": 10240,
    "hisuian sliggoo": 10241, "hisuian goodra": 10242, "hisuian avalugg": 10243,
    "hisuian decidueye": 10244,
}

# 특수/합체/폼 변화 포켓몬 — base dex → [(라벨, PokeAPI form id, 변신 조건), ...]
_SPECIAL_FORM_DEX: dict[int, list[tuple[str, int, str]]] = {
    386: [                                                                  # 데오키시스
        ("어택",   10001, "운석 상호작용으로 폼 변경"),
        ("디펜스", 10002, "운석 상호작용으로 폼 변경"),
        ("스피드", 10003, "운석 상호작용으로 폼 변경"),
    ],
    413: [                                                                  # 도롱마담
        ("모래 망토",   10004, "모래 지형에서 번데기 진화"),
        ("쓰레기 망토", 10005, "건물 지형에서 번데기 진화"),
    ],
    479: [                                                                  # 로토무
        ("열기", 10008, "전자레인지에 빙의"),
        ("세탁", 10009, "세탁기에 빙의"),
        ("냉동", 10010, "냉장고에 빙의"),
        ("선풍", 10011, "선풍기에 빙의"),
        ("제초", 10012, "잔디깎기에 빙의"),
    ],
    483: [("오리진", 10245, "아다만트 구슬 장착")],                         # 디아루가
    484: [("오리진", 10246, "루스트로스 구슬 장착")],                       # 펄기아
    487: [("오리진", 10007, "그리시아스 구슬 장착")],                       # 기라티나
    492: [("스카이",  10006, "감사의 꽃(그레이시아) 사용")],                # 쉐이미
    641: [("영물", 10019, "영물의 거울 사용")],                             # 토네로스
    642: [("영물", 10020, "영물의 거울 사용")],                             # 볼토로스
    645: [("영물", 10021, "영물의 거울 사용")],                             # 랜드로스
    646: [                                                                  # 큐레무
        ("블랙", 10022, "제크로무와 DNA 합체"),
        ("화이트", 10023, "레시라무와 DNA 합체"),
    ],
    648: [("피루에트", 10018, "전투 중 고래 노래 기술 사용")],              # 메로엣타
    718: [                                                                  # 지가르데
        ("10%",   10181, "특정 상황에서 자동 변신"),
        ("퍼펙트", 10120, "HP 절반 이하 시 자동 변신"),
    ],
    720: [("언바운드", 10086, "감옥의 항아리 사용")],                       # 후파
    800: [                                                                  # 네크로즈마
        ("황혼의 갈기", 10155, "솔가레오와 합체"),
        ("새벽의 날개", 10156, "루나아라와 합체"),
        ("울트라",     10157, "황혼의 갈기 or 새벽의 날개 상태에서 울트라 버스트"),
    ],
    898: [                                                                  # 칼리렉스
        ("아이스 라이더", 10193, "블리자포스와 합체"),
        ("섀도 라이더",   10194, "스펙트라이어와 합체"),
    ],
    905: [("영물", 10249, "영물의 거울 사용")],                             # 에나모러스
}

def _normalize_raid_tier(raw: str) -> str:
    return _TIER_NORM.get(raw.lower().strip(), raw)

def _strip_form(en: str) -> str:
    """'Indeedee (Male)' → 'Indeedee', 'Basculin (White Striped)' → 'Basculin'"""
    return re.sub(r"\s*\([^)]+\)", "", en).strip()

def _raid_ko(en: str) -> tuple[int | None, str]:
    en2info = _get_en2info()
    prefix_ko, base = "", en
    # 접두사를 모두 벗길 때까지 반복 ("Shadow Alolan Marowak" → "다크 알로라 " + "Marowak")
    changed = True
    while changed:
        changed = False
        for en_pfx, ko_pfx in _RAID_PREFIXES:
            if base.lower().startswith(en_pfx):
                prefix_ko += ko_pfx
                base = base[len(en_pfx):]
                changed = True
                break
    info = en2info.get(base.lower()) or en2info.get(_strip_form(base).lower())
    dex = info[0] if info else None
    ko  = prefix_ko + (info[1] if info else base)
    return dex, ko

def _raid_form_dex(en: str) -> int | None:
    """리전폼의 PokeAPI form ID 반환 (스프라이트 전용, 데이터 조회에는 사용 금지)"""
    key = en.lower().replace("shadow ", "").strip()
    return _REGIONAL_FORM_DEX.get(key)

_FORM_PREFIX_KO: dict[str, tuple[str, str]] = {
    "alolan ":   ("알로라", "알로라 지역 변형 폼"),
    "galarian ": ("가라르", "가라르 지역 변형 폼"),
    "hisuian ":  ("히스이", "히스이 지역(고대 시놀) 변형 폼"),
}

# PokeAPI form_dex → gamemaster variant_forms 키
_FORM_DEX_TO_VARIANT: dict[int, str] = {
    10001:  "deoxys_attack",
    10002:  "deoxys_defense",
    10003:  "deoxys_speed",
    10007:  "giratina_origin",
    10019:  "tornadus_therian",
    10020:  "thundurus_therian",
    10021:  "landorus_therian",
    10022:  "kyurem_black",
    10023:  "kyurem_white",
    10086:  "hoopa_unbound",
    10120:  "zygarde_complete",
    10155:  "necrozma_dusk_mane",
    10156:  "necrozma_dawn_wings",
    10157:  "necrozma_ultra",
    10193:  "calyrex_ice_rider",
    10194:  "calyrex_shadow_rider",
    10245:  "dialga_origin",
    10246:  "palkia_origin",
    10249:  "enamorus_therian",
}

def _vf_stats(vf: dict) -> dict:
    t2_raw = vf.get("type2", "") or ""
    t1 = vf.get("type1", "")
    t2 = "" if t2_raw == "none" else t2_raw
    return {
        "atk":           vf.get("atk"),
        "def":           vf.get("def"),
        "sta":           vf.get("sta"),
        "cp40":          vf.get("cp_40"),
        "t1":            t1,
        "t2":            t2,
        "weaknesses":    _calc_weaknesses(t1, t2),
        "fast_moves":    [_make_move_info(m) for m in vf.get("fast_moves", [])],
        "charged_moves": [_make_move_info(m) for m in vf.get("charged_moves", [])],
        "elite_fast":    [_make_move_info(m) for m in vf.get("elite_fast", [])],
        "elite_charged": [_make_move_info(m) for m in vf.get("elite_charged", [])],
    }

def _get_forms_for_dex(base_dex: int) -> list[dict]:
    """주어진 base dex 번호에 존재하는 모든 폼(지역 변형 + 특수/합체) 목록 반환"""
    en2info = _get_en2info()
    gm_entry = (_gm_raw or {}).get(str(base_dex), {})
    variant_data = gm_entry.get("variant_forms", {})
    species_id = gm_entry.get("species_id", "")
    forms = []

    # 지역 변형 (알로라/가라르/히스이)
    for form_key, form_dex_id in _REGIONAL_FORM_DEX.items():
        for prefix_en, (prefix_ko, note) in _FORM_PREFIX_KO.items():
            if form_key.startswith(prefix_en):
                base_name = form_key[len(prefix_en):]
                info = en2info.get(base_name)
                if info and info[0] == base_dex:
                    entry: dict = {"label": prefix_ko, "form_dex": form_dex_id, "note": note}
                    vk = f"{species_id}_{prefix_en.rstrip()}"  # e.g. "raichu_alolan"
                    vf = variant_data.get(vk, {})
                    if vf:
                        entry.update(_vf_stats(vf))
                    forms.append(entry)
                break

    # 특수/합체/폼 변화
    for label_ko, form_dex_id, note in _SPECIAL_FORM_DEX.get(base_dex, []):
        entry = {"label": label_ko, "form_dex": form_dex_id, "note": note}
        vk = _FORM_DEX_TO_VARIANT.get(form_dex_id)
        if vk:
            vf = variant_data.get(vk, {})
            if vf:
                entry.update(_vf_stats(vf))
        forms.append(entry)

    return forms

def _build_raids_from_scraped(raw_data: list) -> dict:
    by_tier: dict[str, list] = {}
    if isinstance(raw_data, list) and raw_data:
        if "tier" in (raw_data[0] if raw_data else {}):
            for boss in raw_data:
                tier = _normalize_raid_tier(boss.get("tier", "?"))
                by_tier.setdefault(tier, []).append(boss)
        else:
            for obj in raw_data:
                tier = _normalize_raid_tier(str(obj.get("tier", obj.get("name", "?"))))
                by_tier[tier] = obj.get("bosses", obj.get("pokemon", []))
    elif isinstance(raw_data, dict):
        for k, v in raw_data.items():
            by_tier[_normalize_raid_tier(k)] = v if isinstance(v, list) else []

    result: dict[str, list] = {}
    for tier, bosses in by_tier.items():
        lst = []
        for boss in bosses:
            en = boss.get("name", "") if isinstance(boss, dict) else str(boss)
            if not en:
                continue
            dex, ko = _raid_ko(en)
            types = [t.get("name","") if isinstance(t,dict) else t for t in (boss.get("types",[]) if isinstance(boss,dict) else [])]
            types_ko = " / ".join(_RAID_TYPE_KO.get(t.lower(), t) for t in types if t)
            slug = re.sub(r"[^a-z0-9-]","",en.lower().replace(" ","-").replace("'","").replace(".",""))
            cp     = (boss.get("combatPower") or {}) if isinstance(boss, dict) else {}
            cp_n   = cp.get("normal") or {}
            cp_b   = cp.get("boosted") or {}
            weather = [w.get("name","").lower() for w in (boss.get("boostedWeather") or []) if isinstance(w,dict)]
            form_dex = _raid_form_dex(en)
            lst.append({
                "en_name": en, "ko_name": ko, "slug": slug, "dex": dex,
                "form_dex": form_dex,  # 리전폼 스프라이트 전용, None이면 dex 사용
                "types_ko": types_ko,
                "is_shiny": bool(boss.get("shiny", boss.get("canBeShiny", False)) if isinstance(boss, dict) else False),
                "cp_min": cp_n.get("min"), "cp_max": cp_n.get("max"),
                "cp_boosted_min": cp_b.get("min"), "cp_boosted_max": cp_b.get("max"),
                "weather": weather,
            })
        if lst:
            result[tier] = lst
    return result


# ── 이벤트 HTML 파싱 ──────────────────────────────────────────────
_IMG_PAT = re.compile(r"pokemon_icon_(\d+)_\d+\.png|pm(\d+)\.[^.\"]+\.icon\.png")
_PREFIX_MAP = [
    ("Hisuian ", "히스이 "), ("Galarian ", "가라르 "), ("Alolan ", "알로라 "),
    ("Shadow ", "다크 "), ("Mega ", "메가 "), ("Paldean ", "팔데아 "),
]
_TIER_IDS   = ["one-star-raids", "three-star-raids", "five-star-raids", "mega-raids", "elite-raids"]
_TIER_KEYS  = {"one-star-raids": "1", "three-star-raids": "3", "five-star-raids": "5",
               "mega-raids": "mega", "elite-raids": "elite"}

_en2info_cache: dict | None = None

def _get_en2info() -> dict:
    global _en2info_cache
    if _en2info_cache is not None:
        return _en2info_cache
    _ensure_raw()
    _en2info_cache = {v["en_name"].lower().replace("’", "'"): (int(k), v["ko_name"]) for k, v in (_names_raw or {}).items()}
    return _en2info_cache

def _resolve_en(en: str, dex_fallback: int) -> tuple[int, str]:
    en2info = _get_en2info()
    info = en2info.get(en.lower())
    if info:
        return info
    prefix_ko, base = "", en
    for p_en, p_ko in _PREFIX_MAP:
        if en.startswith(p_en):
            prefix_ko, base = p_ko, en[len(p_en):]
            break
    info = en2info.get(base.lower()) or en2info.get(_strip_form(base).lower())
    dex = info[0] if info else dex_fallback
    ko  = prefix_ko + (info[1] if info else _strip_form(base))
    return dex, ko

def _parse_pkmn(html_chunk: str) -> list[dict]:
    items: list[dict] = []
    seen: set[int] = set()
    for m in _IMG_PAT.finditer(html_chunk):
        dex_img = int(m.group(1) or m.group(2))
        after   = html_chunk[m.end(): m.end() + 300]
        name_m  = re.search(r'(?:pkmn-name|reward-label)[^>]*>(?:<[^>]+>)*([^<]+)<', after)
        en      = name_m.group(1).strip() if name_m else ""
        shiny   = "shiny-icon" in html_chunk[m.start() - 30: m.end() + 300]
        dex, ko = _resolve_en(en, dex_img)
        if dex not in seen:
            seen.add(dex)
            items.append({"dex": dex, "ko": ko, "en": en, "shiny": shiny})
    return items

def _get_section(html: str, start_id: str, stop_ids: list[str]) -> str:
    start = html.find(f'id="{start_id}"')
    if start < 0:
        return ""
    end = len(html)
    for sid in stop_ids:
        i = html.find(f'id="{sid}"', start + 1)
        if 0 < i < end:
            end = i
    return html[start:end]

def _get_section_any(html: str, start_ids: list[str], stop_ids: list[str]) -> str:
    for sid in start_ids:
        s = _get_section(html, sid, stop_ids)
        if s:
            return s
    return ""

def _parse_event_bonuses(html: str) -> list[str]:
    bonus_ids = ["event-bonuses", "bonuses", "features", "event-features",
                 "bonuses-and-features", "bonus", "event-bonus"]
    stop_ids  = ["wild-encounters", "spawns", "wild-spawns", "featured-pokemon",
                 "one-star-raids", "three-star-raids", "five-star-raids", "mega-raids",
                 "field-research", "research-tasks", "go-pass", "sales", "footer"]
    section = _get_section_any(html, bonus_ids, stop_ids)
    if not section:
        return []
    items = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", section, re.DOTALL):
        text = re.sub(r"<[^>]+>", "", li)
        for ent, rep in [("&amp;", "&"), ("&nbsp;", " "), ("&#x27;", "'"),
                         ("&apos;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&times;", "×")]:
            text = text.replace(ent, rep)
        text = re.sub(r"\s+", " ", text).strip()
        if 5 < len(text) < 400:
            items.append(text)
    return items[:25]


def _parse_event_html(html: str) -> dict:
    _STOP_ALL = ["go-pass", "sales", "graphic", "footer"]
    wild_ids = ["wild-encounters", "spawns", "wild-spawns", "featured-pokemon", "boosted-spawns"]
    wild = _parse_pkmn(_get_section_any(html, wild_ids, ["raids", "one-star-raids", "research", "field-research"] + _STOP_ALL))

    raids: dict[str, list] = {}
    for i, tid in enumerate(_TIER_IDS):
        stops = _TIER_IDS[i + 1:] + ["research", "field-research"] + _STOP_ALL
        chunk = _get_section(html, tid, stops)
        pokes = _parse_pkmn(chunk)
        if pokes:
            raids[_TIER_KEYS[tid]] = pokes

    research_ids = ["field-research-task-encounters", "field-research", "research-tasks", "timed-research"]
    research_html = _get_section_any(html, research_ids, _STOP_ALL)
    tasks = []
    for li in re.findall(r"<li>(.*?)</li>", research_html, re.DOTALL):
        task_m = re.search(r'class="task"[^>]*>(.*?)</(?:span|div|p)', li, re.DOTALL)
        if not task_m:
            task_m = re.search(r'class="task">([^<]+)<', li)
        if not task_m:
            continue
        task = re.sub(r"<[^>]+>", "", task_m.group(1))
        task = re.sub(r"&nbsp;", " ", task).strip()
        if not task:
            continue
        rewards = _parse_pkmn(li)
        if rewards:
            tasks.append({"task": task, "rewards": rewards})

    return {"wild": wild, "raids": raids, "research": tasks}


_event_summary_cache: dict[str, tuple[float, list[str]]] = {}
_EVENT_SUMMARY_TTL = 3600

@app.get("/api/event-summary")
async def event_summary(url: str):
    """Claude로 이벤트 페이지 한국어 요약 (구조화 데이터 없는 이벤트용)."""
    import time
    cached = _event_summary_cache.get(url)
    if cached and time.time() - cached[0] < _EVENT_SUMMARY_TTL:
        return {"bullets": cached[1]}

    text = await _fetch_event_page(url)
    if not text:
        return {"bullets": []}

    try:
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "다음은 포켓몬 GO 이벤트 페이지 내용이야. "
                    "핵심 정보만 추려서 한국어 bullet point로 5~8개 작성해줘.\n"
                    "포함할 내용: 이벤트 기간, 주요 특전(보너스), 특이사항.\n"
                    "각 항목은 한 줄로 간결하게. 번호나 기호 없이 텍스트만.\n\n"
                    f"{text[:2500]}"
                )
            }]
        )
        raw = msg.content[0].text.strip()
        bullets = [l.lstrip("-•·* ").strip() for l in raw.splitlines() if l.strip()]
        bullets = [b for b in bullets if b]
    except Exception as e:
        log.warning(f"[event-summary] Claude 호출 실패: {e}")
        bullets = []

    _event_summary_cache[url] = (time.time(), bullets)
    return {"bullets": bullets}


@app.get("/api/event-detail")
async def event_detail(url: str):
    html = await _fetch_html(url)
    if not html:
        return {"wild": [], "raids": {}, "research": []}
    return _parse_event_html(html)


@app.get("/api/event-spawns")
async def event_spawns(url: str):
    result = await event_detail(url)
    spawns = result.get("wild", [])
    return {"spawns": spawns}


@app.get("/api/raids")
async def get_raids_api():
    import time
    # 로컬 파일 우선 반환 (수동 수정 및 자동 갱신 결과 모두 반영)
    p = Path(".raw/current_raids.json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # 파일 없을 때만 ScrapedDuck 직접 조회 (초기 부트스트랩)
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(SCRAPED_DUCK_RAIDS_URL)
            r.raise_for_status()
            processed = _build_raids_from_scraped(r.json())
        if processed:
            p.write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")
            return processed
    except Exception as ex:
        log.warning(f"[raids] live fetch 실패: {ex}")
    return {}


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
                move_ko = all_links[1] if len(all_links) >= 2 else (all_links[0] if all_links else "")
                # 마지막 숫자 컬럼 = DPS 배율 점수
                score_m = re.search(r'\|\s*([\d.]+)\s*\|?\s*$', line.strip())
                counters.append({
                    "rank":  rank_m.group(1),
                    "dex":   slug_dex.get(pm.group(1)),
                    "ko":    pm.group(2),
                    "move":  move_ko,
                    "score": float(score_m.group(1)) if score_m else None,
                })
        elif in_table and line.strip() and not line.strip().startswith("|") and not line.strip().startswith(">"):
            break

    return {"counters": counters[:15], "boss_ko": boss_ko, "weakness": weakness}


# ── 레이드 위키 자동 갱신 ────────────────────────────────────────────
_TIER_LABEL = {"mega": "메가 레이드", "5": "5성 레이드", "3": "3성 레이드", "1": "1성 레이드", "elite": "엘리트 레이드"}

def _update_raids_wiki() -> None:
    """current_raids.json 내용으로 wiki/current-raids.md 재생성."""
    p = Path(".raw/current_raids.json")
    if not p.exists():
        return
    raids: dict = json.loads(p.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = sum(len(v) for v in raids.values())

    lines = [
        '---',
        'title: "Current Raids / 현재 레이드 보스"',
        'type: concept',
        'language: ko',
        f'created: 2026-06-05',
        f'modified: {today}',
        'tags: ["raid", "current", "boss", "event"]',
        'aliases: ["현재 레이드", "레이드 보스", "레이드 보스 목록", "raid boss", "current raids"]',
        f'summary: "현재 포켓몬 GO 레이드 보스 목록 — {today} 기준, 총 {total}마리"',
        '---',
        '',
        '# 현재 레이드 보스',
        '',
        f'> 데이터 출처: [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck) (LeekDuck 기반)',
        f'> 기준일: {today}',
        '> ⚠️ 레이드 보스는 자주 변경됩니다. 최신 정보는 [LeekDuck](https://leekduck.com/boss/) 에서 확인하세요.',
    ]

    for tier_key in ["mega", "elite", "5", "3", "1"]:
        bosses = raids.get(tier_key, [])
        if not bosses:
            continue
        label = _TIER_LABEL.get(tier_key, f"{tier_key}성 레이드")
        lines += ['', f'### {label}', '', '| 포켓몬 | 타입 | 색변 |', '|--------|------|------|']
        for b in bosses:
            ko   = b.get("ko_name", b.get("en_name", ""))
            slug = b.get("slug", "")
            t    = b.get("types_ko", "")
            shy  = "O" if b.get("is_shiny") else "-"
            lines.append(f'| [[pokemon-{slug}|{ko}]] | {t} | {shy} |')

    lines += [
        '',
        '## 레이드 카운터 찾기',
        '',
        '각 레이드 보스 이름을 클릭하면 개별 포켓몬 페이지로 이동합니다.',
        '카운터 정보는 `raid-counters-{slug}` 페이지에서 확인할 수 있습니다.',
        '',
        '## Related Concepts',
        '- [[type-chart]] — 타입 상성표',
        '- [[moves-fast]] — 빠른 기술 목록',
        '- [[moves-charged]] — 스페셜 기술 목록',
    ]

    wiki_path = Path("wiki/current-raids.md")
    wiki_path.write_text("\n".join(lines), encoding="utf-8")
    # 위키 인덱스 캐시 무효화
    global _wiki_index_cache
    _wiki_index_cache = None


# ── Rockets API ───────────────────────────────────────────────────────
@app.get("/api/rockets")
async def get_rockets_api():
    p = Path(".raw/rocket_lineups.json")
    if not p.exists():
        return []
    _ensure_raw()
    lineups: list[dict] = json.loads(p.read_text(encoding="utf-8"))
    en2info = _get_en2info()

    def resolve(pms: list) -> list:
        out = []
        for pm in (pms or []):
            en = pm.get("name", "")
            dex, ko = _resolve_en(en, 0)
            out.append({
                "en": en, "ko": ko,
                "dex": dex,
                "types": pm.get("types", []),
                "is_encounter": pm.get("isEncounter", False),
                "can_shiny": pm.get("canBeShiny", False),
            })
        return out

    result = []
    for entry in lineups:
        result.append({
            "name":   entry.get("name", ""),
            "title":  entry.get("title", ""),
            "type":   entry.get("type", ""),
            "first":  resolve(entry.get("firstPokemon", [])),
            "second": resolve(entry.get("secondPokemon", [])),
            "third":  resolve(entry.get("thirdPokemon", [])),
        })
    return result


# ── Community Days API ────────────────────────────────────────────────
@app.get("/api/community-days")
async def get_community_days_api():
    events = await get_events()
    _ensure_raw()
    en2info = _get_en2info()

    def resolve_pm(en: str) -> dict:
        info = en2info.get(en.lower())
        return {"en": en, "ko": info[1] if info else en, "dex": info[0] if info else 0}

    cdays = []
    for e in events:
        if e.get("eventType") != "community-day":
            continue
        ed = e.get("extraData", {})
        cd = ed.get("communityday", {})
        spawns_raw = cd.get("spawns", [])
        pokemon = [resolve_pm(sp["name"]) for sp in spawns_raw if sp.get("name")]
        # extraData에 없으면 이벤트명에서 포켓몬 이름 파싱
        if not pokemon:
            m = re.match(r'^(.+?)\s*커뮤니티', _translate_event_name(e["name"], "community-day"))
            if m:
                pokemon = [resolve_pm(m.group(1).strip())]
        cdays.append({
            "name":    _translate_event_name(e["name"], "community-day"),
            "start":   e["start"],
            "end":     e["end"],
            "link":    e.get("link", ""),
            "pokemon": pokemon,
        })

    cdays.sort(key=lambda x: x["start"], reverse=True)
    return cdays


# ── Field Research API ───────────────────────────────────────────────
@app.get("/api/field-research")
async def get_field_research_api():
    p = Path(".raw/field_research.json")
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


# ── Eggs API ─────────────────────────────────────────────────────────
SCRAPED_DUCK_EGGS_URL = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data/eggs.json"
_eggs_live_cache: dict = {}
_eggs_live_at: float = 0.0
EGGS_LIVE_TTL = 3600  # 1시간 캐시 (알은 자주 안 바뀜)

def _build_eggs_from_raw(eggs_raw: list) -> dict:
    _ensure_raw()
    rarity_label = {1: "흔함", 2: "보통", 3: "드묾", 4: "레어", 5: "초레어"}
    result: dict[str, list] = {}
    for egg in eggs_raw:
        km      = egg.get("eggType", "").replace(" ", "")
        en      = egg["name"]
        dex, ko = _raid_ko(en)   # 접두사(Galarian 등) + 폼(Male 등) 처리 통합
        gmd     = (_gm_raw or {}).get(str(dex), {}) if dex else {}
        t2      = gmd.get("type2", "") or ""
        if t2 == "none":
            t2 = ""
        result.setdefault(km, []).append({
            "en":         en,
            "ko":         ko,
            "dex":        dex,
            "t1":         gmd.get("type1", ""),
            "t2":         t2,
            "shiny":      egg.get("canBeShiny", False),
            "rarity":     rarity_label.get(egg.get("rarity", 1), ""),
            "rarity_num": egg.get("rarity", 1),
            "as_only":    egg.get("isAdventureSync", False),
        })
    for km in result:
        result[km].sort(key=lambda x: (-x["rarity_num"], x["dex"] or 9999))
    return result

@app.get("/api/eggs")
async def get_eggs_api():
    import time
    global _eggs_live_cache, _eggs_live_at
    if _eggs_live_cache and time.time() - _eggs_live_at < EGGS_LIVE_TTL:
        return _eggs_live_cache
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(SCRAPED_DUCK_EGGS_URL)
            r.raise_for_status()
            result = _build_eggs_from_raw(r.json())
        if result:
            _eggs_live_cache = result
            _eggs_live_at = time.time()
            return result
    except Exception as ex:
        log.warning(f"[eggs] live fetch 실패: {ex}")
    # 파일 캐시 fallback
    eggs_path = Path(".raw/eggs.json")
    if eggs_path.exists():
        return _build_eggs_from_raw(json.loads(eggs_path.read_text(encoding="utf-8")))
    return {}


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


_pvp_moveset_cache: dict | None = None

@app.get("/api/pvp-moveset/{dex}")
async def get_pvp_moveset(dex: int):
    """dex 번호로 각 리그 추천 기술셋 반환."""
    global _pvp_moveset_cache
    pvp_path = Path(".raw/pvp_rankings.json")
    if not pvp_path.exists():
        return {}
    if _pvp_moveset_cache is None:
        pvp = json.loads(pvp_path.read_text(encoding="utf-8"))
        def _strip(s: str) -> str:
            return re.sub(r'\[\[[^\]|]+\|([^\]]+)\]\]', r'\1', s)
        cache: dict[int, dict] = {}
        for lk, ld in pvp.items():
            for e in ld.get("entries", []):
                d = e.get("dex")
                if not d:
                    continue
                cache.setdefault(d, {})[lk] = {
                    "rank":    e["rank"],
                    "score":   e.get("score", 0),
                    "fast":    _strip(e.get("fast_ko", "")),
                    "charged": _strip(e.get("charged_ko", "")),
                }
        _pvp_moveset_cache = cache
    return _pvp_moveset_cache.get(dex, {})


# ── Raid Rankings ─────────────────────────────────────────────────────
_raid_rank_cache: dict | None = None

@app.get("/api/raid_rankings")
async def get_raid_rankings():
    global _raid_rank_cache
    if _raid_rank_cache is not None:
        return _raid_rank_cache
    if not _ensure_raw() or not _gm_raw or not _go_moves_en:
        return {}

    type_entries: dict[str, list] = {}

    for dex_str, gm in _gm_raw.items():
        atk = gm.get("atk", 0)
        if not atk:
            continue
        nd = (_names_raw or {}).get(dex_str, {})
        ko = nd.get("ko_name", "")
        if not ko:
            continue
        dex = int(dex_str)
        t1 = gm.get("type1", "")
        t2 = gm.get("type2", "") or ""
        if t2 == "none":
            t2 = ""
        types = {t for t in [t1, t2] if t}
        fast_ids   = gm.get("fast_moves", [])
        charged_ids = gm.get("charged_moves", [])

        for ptype in types:
            stab_fast    = [_go_moves_en[n] for n in fast_ids    if n in _go_moves_en and _go_moves_en[n].get("type") == ptype]
            stab_charged = [_go_moves_en[n] for n in charged_ids if n in _go_moves_en and _go_moves_en[n].get("type") == ptype]
            if not stab_fast or not stab_charged:
                continue
            bf = max(stab_fast,    key=lambda m: m.get("dps_pve", 0))
            bc = max(stab_charged, key=lambda m: m.get("power", 0) / max(m.get("energy_cost", 1), 1))
            score = round(atk * (bf.get("dps_pve", 0) + bf.get("eps_pve", 0) * bc.get("power", 0) / max(bc.get("energy_cost", 1), 1)))
            type_entries.setdefault(ptype, []).append({
                "dex": dex, "ko": ko,
                "fast_ko": bf.get("ko_name") or bf.get("en_name", ""),
                "charged_ko": bc.get("ko_name") or bc.get("en_name", ""),
                "score": score,
            })

    result = {}
    for ptype, entries in type_entries.items():
        ranked = sorted(entries, key=lambda x: x["score"], reverse=True)[:20]
        for i, e in enumerate(ranked, 1):
            e["rank"] = i
        result[ptype] = ranked

    _raid_rank_cache = result
    return result


# ── Mega Rankings ─────────────────────────────────────────────────────
_mega_rank_cache: dict | None = None

def _mega_display_name(ko: str, form_name: str) -> str:
    suffix = form_name.split("_mega")[-1].strip("_").upper()
    return f"메가 {ko} {suffix}" if suffix else f"메가 {ko}"

@app.get("/api/mega_rankings")
async def get_mega_rankings():
    global _mega_rank_cache
    if _mega_rank_cache is not None:
        return _mega_rank_cache
    if not _ensure_raw() or not _gm_raw or not _go_moves_en:
        return {}

    type_entries: dict[str, list] = {}

    for dex_str, gm in _gm_raw.items():
        variant_forms = gm.get("variant_forms") or {}
        fast_ids    = gm.get("fast_moves", [])
        charged_ids = gm.get("charged_moves", [])
        nd  = (_names_raw or {}).get(dex_str, {})
        ko_base = nd.get("ko_name", "")
        if not ko_base:
            continue
        dex = int(dex_str)

        for form_name, fd in variant_forms.items():
            if "_mega" not in form_name:
                continue
            atk = fd.get("atk", 0)
            t1  = fd.get("type1", "")
            t2  = fd.get("type2", "") or ""
            if t2 == "none":
                t2 = ""
            if not atk or not t1:
                continue
            types = {t for t in [t1, t2] if t}
            display = _mega_display_name(ko_base, form_name)

            for ptype in types:
                stab_fast    = [_go_moves_en[n] for n in fast_ids    if n in _go_moves_en and _go_moves_en[n].get("type") == ptype]
                stab_charged = [_go_moves_en[n] for n in charged_ids if n in _go_moves_en and _go_moves_en[n].get("type") == ptype]
                if not stab_fast or not stab_charged:
                    continue
                bf = max(stab_fast,    key=lambda m: m.get("dps_pve", 0))
                bc = max(stab_charged, key=lambda m: m.get("power", 0) / max(m.get("energy_cost", 1), 1))
                score = round(atk * (bf.get("dps_pve", 0) + bf.get("eps_pve", 0) * bc.get("power", 0) / max(bc.get("energy_cost", 1), 1)))
                type_entries.setdefault(ptype, []).append({
                    "dex": dex, "ko": display,
                    "fast_ko": bf.get("ko_name") or bf.get("en_name", ""),
                    "charged_ko": bc.get("ko_name") or bc.get("en_name", ""),
                    "score": score,
                })

    result = {}
    for ptype, entries in type_entries.items():
        ranked = sorted(entries, key=lambda x: x["score"], reverse=True)[:10]
        for i, e in enumerate(ranked, 1):
            e["rank"] = i
        result[ptype] = ranked

    _mega_rank_cache = result
    return result


# ── Community Chat Rooms ──────────────────────────────────────────────
import uuid   as _uuid
import time   as _time
import random as _random

_ROOM_MAX_USERS = 10
_ROOM_MAX_MSGS  = 50
_SERVER_EPOCH   = _time.time()
_KST            = timezone(timedelta(hours=9))

# ── 퀴즈 헬퍼 ─────────────────────────────────────────────────────────
_CHOSUNG_LIST = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
_TYPE_KO_QUIZ = {
    "normal":"노말","fire":"불꽃","water":"물","electric":"전기","grass":"풀",
    "ice":"얼음","fighting":"격투","poison":"독","ground":"땅","flying":"비행",
    "psychic":"에스퍼","bug":"벌레","rock":"바위","ghost":"고스트",
    "dragon":"드래곤","dark":"악","steel":"강철","fairy":"페어리",
}

def _chosung(text: str) -> str:
    return "".join(
        _CHOSUNG_LIST[(ord(c) - 0xAC00) // 588]
        if 0 <= ord(c) - 0xAC00 <= 11171 else c
        for c in text
    )

def _type_ko_str(t1: str, t2: str) -> str:
    s = _TYPE_KO_QUIZ.get(t1, t1)
    if t2:
        s += " / " + _TYPE_KO_QUIZ.get(t2, t2)
    return s


class _QuizState:
    def __init__(self) -> None:
        self.active           = True
        self.current_dex: int = 0
        self.current_ko:  str = ""
        self.current_en:  str = ""
        self.current_t1:  str = ""
        self.current_t2:  str = ""
        self.current_answer: str = ""
        self.answered         = False
        self.answered_event   = asyncio.Event()
        self.scores: dict[str, int] = {}
        self.question_num     = 1
        self.hint_idx:    int = 0
        self.current_hints: list = []
        self.msg_count:   int = 0
        self.skipped:     bool = False
        self.gens:        list = []  # 빈 리스트 = 전체
        self.quiz_type:   str = "silhouette"

    @staticmethod
    def build_pool(gens: list | None = None) -> list:
        if not _gm_raw or not _names_raw:
            return []
        pool = []
        for dex_str, gm in _gm_raw.items():
            nd  = _names_raw.get(dex_str, {})
            ko  = nd.get("ko_name", "")
            en  = nd.get("en_name", "")
            t1  = gm.get("type1", "")
            t2  = gm.get("type2", "") or ""
            if t2 == "none":
                t2 = ""
            gen = nd.get("gen") or 0
            if gens and gen not in gens:
                continue
            if ko and t1:
                pool.append((int(dex_str), ko, en, t1, t2, gen))
        return pool


async def _run_quiz(room) -> None:
    MAX_SCORE = 10
    _ensure_raw()
    pool = _QuizState.build_pool(room.quiz.gens or None)
    if not pool:
        room.quiz = None
        return
    try:
        while room.quiz and room.quiz.active:
            if room.count == 0:
                break
            dex, ko, en, t1, t2, gen = _random.choice(pool)
            q = room.quiz
            q.current_dex    = dex
            q.current_ko     = ko
            q.current_en     = en
            q.current_t1     = t1
            q.current_t2     = t2
            q.answered       = False
            q.skipped        = False
            q.hint_idx       = 0
            q.msg_count      = 0
            quiz_type = q.quiz_type
            if quiz_type == "type":
                t1_ko = _TYPE_KO_QUIZ.get(t1, t1)
                t2_ko = _TYPE_KO_QUIZ.get(t2, t2) if t2 else ""
                q.current_answer = _type_ko_str(t1, t2)
                q.current_hints  = [
                    f"세대: {gen}세대" if gen else "세대: ?",
                    f"타입 수: {'이중타입' if t2 else '단일타입'}",
                    f"타입 첫 글자: {t1_ko[0] if t1_ko else '?'}",
                    f"초성: {_chosung(ko)}",
                ]
            elif quiz_type == "chosung":
                q.current_answer = ko
                q.current_hints  = [
                    f"타입: {_type_ko_str(t1, t2)}",
                    f"세대: {gen}세대" if gen else "세대: ?",
                    f"이름: {len(ko)}글자",
                ]
            else:  # silhouette
                q.current_answer = ko
                q.current_hints  = [
                    f"타입: {_type_ko_str(t1, t2)}",
                    f"세대: {gen}세대" if gen else "세대: ?",
                    f"이름: {len(ko)}글자",
                    f"초성: {_chosung(ko)}",
                ]
            q.answered_event.clear()
            msg_data: dict = {
                "type": "quiz_question", "dex": dex,
                "question_num": q.question_num, "scores": dict(q.scores),
                "quiz_type": quiz_type,
            }
            if quiz_type == "chosung":
                msg_data["chosung"] = _chosung(ko)
            elif quiz_type == "type":
                msg_data["name_ko"] = ko
                msg_data["name_en"] = en
            await room.broadcast(msg_data)
            await q.answered_event.wait()
            if not room.quiz or not room.quiz.active:
                return
            if q.skipped:
                await room.broadcast({
                    "type": "quiz_skip", "answer": q.current_answer, "dex": dex,
                    "scores": dict(room.quiz.scores),
                })
                await asyncio.sleep(3)
                if not room.quiz or not room.quiz.active:
                    return
                room.quiz.question_num += 1
                continue
            await asyncio.sleep(3)
            if max(room.quiz.scores.values(), default=0) >= MAX_SCORE:
                break
            room.quiz.question_num += 1
    except asyncio.CancelledError:
        pass
    finally:
        if room.quiz:
            sc = dict(room.quiz.scores)
            winner = max(sc, key=sc.get, default=None) if sc else None
            await room.broadcast({"type": "quiz_end", "winner": winner, "scores": sc})
            room.quiz = None


class _Room:
    def __init__(self, room_id: str, name: str) -> None:
        self.id         = room_id
        self.name       = name
        self.conns:     list[tuple[WebSocket, str]] = []
        self.msgs:      list[dict] = []
        self.created_at: float = _time.time()
        self.quiz: _QuizState | None = None

    @property
    def count(self) -> int:
        return len(self.conns)

    def remove(self, ws: WebSocket) -> None:
        self.conns = [(w, n) for w, n in self.conns if w is not ws]

    async def broadcast(self, msg: dict, exclude: WebSocket | None = None) -> None:
        data = json.dumps(msg, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws, _ in list(self.conns):
            if ws is exclude:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)


_rooms: dict[str, _Room] = {}


@app.get("/api/rooms")
async def list_rooms():
    return {
        "epoch": _SERVER_EPOCH,
        "rooms": [
            {"id": r.id, "name": r.name, "count": r.count,
             "max": _ROOM_MAX_USERS, "created_at": r.created_at}
            for r in list(_rooms.values())
        ],
    }


class _CreateRoomReq(BaseModel):
    name: str


@app.post("/api/rooms")
async def create_room(req: _CreateRoomReq):
    name = req.name.strip()[:30]
    if not name:
        return JSONResponse({"error": "방 이름을 입력하세요."}, status_code=400)
    room_id = _uuid.uuid4().hex[:8]
    _rooms[room_id] = _Room(room_id, name)
    return {"id": room_id, "name": name}


@app.websocket("/ws/room/{room_id}")
async def room_ws(ws: WebSocket, room_id: str, nick: str = "트레이너") -> None:
    room = _rooms.get(room_id)
    if not room:
        await ws.close(code=4004); return
    if room.count >= _ROOM_MAX_USERS:
        await ws.close(code=4003); return

    nick = nick.strip()[:15] or "트레이너"
    await ws.accept()
    room.conns.append((ws, nick))

    await ws.send_text(json.dumps({
        "type": "init",
        "messages": room.msgs[-30:],
        "count": room.count,
        "room_name": room.name,
    }, ensure_ascii=False))
    await room.broadcast(
        {"type": "notice", "text": f"{nick}님이 입장했습니다.", "count": room.count},
        exclude=ws,
    )

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "typing":
                await room.broadcast(
                    {"type": "typing", "nick": nick, "is_typing": bool(msg.get("is_typing"))},
                    exclude=ws,
                )
                continue
            if msg.get("type") == "quiz_start":
                if not room.quiz and _ensure_raw() and _gm_raw:
                    raw_gens = msg.get("gens") or []
                    gens = sorted({int(g) for g in raw_gens if str(g).isdigit()})
                    qt = msg.get("quiz_type", "silhouette")
                    if qt not in ("silhouette", "chosung", "type"):
                        qt = "silhouette"
                    room.quiz = _QuizState()
                    room.quiz.gens = gens
                    room.quiz.quiz_type = qt
                    gens_label = "전체" if not gens else " · ".join(f"{g}세대" for g in gens)
                    await room.broadcast({"type": "quiz_started", "nick": nick, "scores": {}, "gens_label": gens_label, "quiz_type": qt})
                    asyncio.create_task(_run_quiz(room))
                continue
            if msg.get("type") == "quiz_stop":
                if room.quiz:
                    room.quiz.active = False
                    room.quiz.answered_event.set()
                continue
            if msg.get("type") != "message":
                continue
            text = (msg.get("text") or "").strip()
            if not text or len(text) > 300:
                continue
            # 퀴즈 정답/오답 처리
            if room.quiz and room.quiz.active and not room.quiz.answered:
                qt = room.quiz.quiz_type
                if qt == "type":
                    t1v = room.quiz.current_t1
                    t2v = room.quiz.current_t2
                    valid = {t1v.lower(), _TYPE_KO_QUIZ.get(t1v, t1v).lower()}
                    if t2v:
                        valid |= {t2v.lower(), _TYPE_KO_QUIZ.get(t2v, t2v).lower()}
                    is_correct = text.lower() in valid
                else:
                    is_correct = (text.lower() == room.quiz.current_ko.lower() or
                                  text.lower() == room.quiz.current_en.lower())
                if is_correct:
                    room.quiz.answered = True
                    room.quiz.scores[nick] = room.quiz.scores.get(nick, 0) + 1
                    room.quiz.answered_event.set()
                    await room.broadcast({
                        "type": "quiz_correct", "nick": nick,
                        "answer": room.quiz.current_answer,
                        "dex": room.quiz.current_dex,
                        "scores": dict(room.quiz.scores),
                    })
                else:
                    if room.quiz.hint_idx < len(room.quiz.current_hints):
                        hint_text = room.quiz.current_hints[room.quiz.hint_idx]
                        room.quiz.hint_idx += 1
                        await room.broadcast({
                            "type": "quiz_hint",
                            "hint": hint_text,
                            "hint_num": room.quiz.hint_idx,
                        })
                    room.quiz.msg_count += 1
                    if room.quiz.msg_count >= 10:
                        room.quiz.skipped = True
                        room.quiz.answered_event.set()
            record: dict = {
                "type": "message", "nick": nick, "text": text,
                "ts": datetime.now(_KST).strftime("%H:%M"),
            }
            room.msgs.append(record)
            if len(room.msgs) > _ROOM_MAX_MSGS:
                room.msgs.pop(0)
            await room.broadcast(record)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        room.remove(ws)
        if room.count == 0:
            if room.quiz:
                room.quiz.active = False
                room.quiz.answered_event.set()
            _rooms.pop(room_id, None)
        else:
            await room.broadcast(
                {"type": "notice", "text": f"{nick}님이 퇴장했습니다.", "count": room.count},
            )


# ── Routes ──────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    import time
    now = time.time()
    live_at_map = {"raids": _raids_live_at, "eggs": _eggs_live_at}
    result = {}
    for s in _REFRESH_SCRIPTS:
        name    = s["name"]
        st      = _refresh_status[name]
        live_at = live_at_map.get(name, 0.0)
        result[name] = {
            "last_ok":    st["last_ok"],
            "last_err":   st["last_err"],
            "running":    st["running"],
            "live_age_s": int(now - live_at) if live_at > 0 else None,
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


# ── Catch Mind ──────────────────────────────────────────────────────────
import uuid as _cm_uuid

_cm_rooms: dict[str, dict] = {}
_CM_ROUND_SEC = 120
_CM_WAIT_SEC  = 60
_CM_WIN_SCORE = 3
_CM_MAX_PLAYERS = 8


_CM_DIFF_RANGE = {"easy": 151, "normal": 493, "hard": 9999}

def _cm_rand_word(difficulty: str = "normal") -> str:
    if not _names_raw:
        return "이상해씨"
    max_dex = _CM_DIFF_RANGE.get(difficulty, 493)
    pool = [v["ko_name"] for k, v in _names_raw.items()
            if v.get("ko_name") and 1 <= int(k) <= max_dex]
    return _random.choice(pool) if pool else "이상해씨"


async def _cm_send(ws: WebSocket, msg: dict) -> None:
    try:
        await ws.send_json(msg)
    except Exception:
        pass


async def _cm_bcast(room_id: str, msg: dict, skip: WebSocket | None = None) -> None:
    room = _cm_rooms.get(room_id)
    if not room:
        return
    dead = []
    for pid, p in list(room["players"].items()):
        if p["ws"] is skip:
            continue
        try:
            await p["ws"].send_json(msg)
        except Exception:
            dead.append(pid)
    for pid in dead:
        room["players"].pop(pid, None)


def _cm_scores(room: dict) -> dict:
    return {p["name"]: p["score"] for p in room["players"].values()}


async def _cm_start_round(room_id: str) -> None:
    room = _cm_rooms.get(room_id)
    if not room:
        return
    word = _cm_rand_word(room.get("difficulty", "normal"))
    room.update(word=word, status="playing", guessed=set())
    if room.get("round_task"):
        room["round_task"].cancel()

    drawer_id = room["drawer_id"]
    drawer_name = (room["players"].get(drawer_id) or {}).get("name", "???")
    for pid, p in list(room["players"].items()):
        msg: dict = {"type": "round_start", "drawer": drawer_name, "time": _CM_ROUND_SEC}
        if pid == drawer_id:
            msg["word"] = word
        await _cm_send(p["ws"], msg)

    room["round_task"] = asyncio.create_task(_cm_round_timer(room_id))


async def _cm_round_timer(room_id: str) -> None:
    try:
        for t in range(_CM_ROUND_SEC, -1, -1):
            if room_id not in _cm_rooms:
                return
            if _cm_rooms[room_id].get("status") != "playing":
                return
            await _cm_bcast(room_id, {"type": "timer", "t": t})
            if t == 0:
                await _cm_end_round(room_id, winner_id=None)
                return
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


async def _cm_end_round(room_id: str, winner_id: str | None) -> None:
    room = _cm_rooms.get(room_id)
    if not room or room.get("status") in ("round_end", "game_over", "waiting"):
        return
    room["status"] = "round_end"
    if room.get("round_task"):
        room["round_task"].cancel()

    if winner_id and winner_id in room["players"]:
        room["players"][winner_id]["score"] += 1

    scores = _cm_scores(room)
    game_winner = next((name for name, s in scores.items() if s >= _CM_WIN_SCORE), None)

    if game_winner:
        await _cm_bcast(room_id, {
            "type": "game_over", "winner": game_winner,
            "word": room.get("word", ""), "scores": scores,
        })
        room["status"] = "game_over"
        return

    winner_name = room["players"].get(winner_id, {}).get("name") if winner_id else None
    await _cm_bcast(room_id, {
        "type": "round_end",
        "word": room.get("word", ""), "winner": winner_name, "scores": scores,
    })

    # 다음 drawer: 정답자 or 순환
    pids = list(room["players"].keys())
    if winner_id and winner_id in pids:
        room["drawer_id"] = winner_id
    elif pids:
        cur = pids.index(room["drawer_id"]) if room["drawer_id"] in pids else -1
        room["drawer_id"] = pids[(cur + 1) % len(pids)]

    await asyncio.sleep(3)
    if room_id in _cm_rooms and _cm_rooms[room_id]["status"] == "round_end":
        await _cm_start_round(room_id)


async def _cm_wait_timer(room_id: str) -> None:
    try:
        await asyncio.sleep(_CM_WAIT_SEC)
        room = _cm_rooms.get(room_id)
        if room and room.get("status") == "waiting" and len(room["players"]) < 2:
            await _cm_bcast(room_id, {"type": "room_closed"})
            _cm_rooms.pop(room_id, None)
    except asyncio.CancelledError:
        pass


class _CmCreateReq(BaseModel):
    nick: str
    difficulty: str = "normal"


@app.post("/api/catchmind/create")
async def cm_create_room(req: _CmCreateReq):
    room_id = _cm_uuid.uuid4().hex[:6].upper()
    diff = req.difficulty if req.difficulty in _CM_DIFF_RANGE else "normal"
    room: dict = {
        "room_id": room_id,
        "creator": req.nick.strip()[:15] or "트레이너",
        "difficulty": diff,
        "players": {},
        "status": "waiting",
        "word": None,
        "drawer_id": None,
        "round_task": None,
        "wait_task": None,
        "guessed": set(),
    }
    _cm_rooms[room_id] = room
    room["wait_task"] = asyncio.create_task(_cm_wait_timer(room_id))
    return {"room_id": room_id}


@app.get("/api/catchmind/rooms")
async def cm_list_rooms():
    return [
        {"room_id": r["room_id"], "creator": r["creator"],
         "status": r["status"], "players": len(r["players"]),
         "difficulty": r.get("difficulty", "normal")}
        for r in _cm_rooms.values()
        if r["status"] in ("waiting", "playing")
    ]


@app.websocket("/ws/catchmind/{room_id}")
async def catchmind_ws(ws: WebSocket, room_id: str, nick: str = "트레이너") -> None:
    room = _cm_rooms.get(room_id)
    if not room:
        await ws.close(code=4004); return
    if len(room["players"]) >= _CM_MAX_PLAYERS:
        await ws.close(code=4003); return

    nick = nick.strip()[:15] or "트레이너"
    await ws.accept()
    pid = _cm_uuid.uuid4().hex[:8]
    room["players"][pid] = {"ws": ws, "name": nick, "score": 0}

    await _cm_send(ws, {
        "type": "joined", "pid": pid,
        "players": [{"name": p["name"], "score": p["score"]} for p in room["players"].values()],
        "status": room["status"],
    })
    await _cm_bcast(room_id, {
        "type": "player_join", "name": nick, "count": len(room["players"]),
    }, skip=ws)

    if room["status"] == "waiting" and len(room["players"]) >= 2:
        if room.get("wait_task"):
            room["wait_task"].cancel()
        room["drawer_id"] = _random.choice(list(room["players"].keys()))
        await asyncio.sleep(0.5)
        await _cm_start_round(room_id)

    try:
        while True:
            data = await ws.receive_json()
            t = data.get("type")
            is_drawer = room.get("drawer_id") == pid
            is_playing = room.get("status") == "playing"

            if t == "draw" and is_drawer and is_playing:
                await _cm_bcast(room_id, {"type": "draw", "d": data.get("d")}, skip=ws)

            elif t == "clear" and is_drawer:
                await _cm_bcast(room_id, {"type": "clear"}, skip=ws)

            elif t == "guess" and is_playing and not is_drawer:
                if pid in room.get("guessed", set()):
                    continue
                text = (data.get("text") or "").strip()
                correct = text == room.get("word", "")
                await _cm_bcast(room_id, {
                    "type": "guess", "name": room["players"][pid]["name"],
                    "text": text, "correct": correct,
                })
                if correct:
                    room["guessed"].add(pid)
                    await _cm_end_round(room_id, winner_id=pid)

            elif t == "restart" and room.get("status") == "game_over":
                for p in room["players"].values():
                    p["score"] = 0
                room["drawer_id"] = _random.choice(list(room["players"].keys()))
                await _cm_start_round(room_id)

    except (WebSocketDisconnect, Exception):
        pass
    finally:
        left = room["players"].pop(pid, {}).get("name", "???")
        await _cm_bcast(room_id, {
            "type": "player_leave", "name": left, "count": len(room["players"]),
        })
        if not room["players"]:
            for k in ("round_task", "wait_task"):
                if room.get(k):
                    room[k].cancel()
            _cm_rooms.pop(room_id, None)
        elif pid == room.get("drawer_id") and room.get("status") == "playing":
            pids = list(room["players"].keys())
            if pids:
                room["drawer_id"] = pids[0]
            await _cm_end_round(room_id, winner_id=None)


_REACT_DIR = Path("static") / "react"
_LEGACY_HTML = Path("static") / "index.html"

@app.get("/", response_class=HTMLResponse)
async def index():
    from fastapi.responses import HTMLResponse as _HTMLResponse
    react_index = _REACT_DIR / "index.html"
    html = react_index.read_text(encoding="utf-8") if react_index.exists() else _LEGACY_HTML.read_text(encoding="utf-8")
    return _HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

# React SPA assets (CSS/JS bundles)
if (_REACT_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_REACT_DIR / "assets")), name="react-assets")


@app.get("/sw.js")
async def service_worker():
    from fastapi.responses import Response
    content = (Path("static") / "sw.js").read_text(encoding="utf-8")
    return Response(content=content, media_type="application/javascript")


@app.get("/manifest.json")
async def manifest():
    from fastapi.responses import Response
    content = (Path("static") / "manifest.json").read_text(encoding="utf-8")
    return Response(content=content, media_type="application/manifest+json")


@app.get("/icon-192.png")
async def icon_192():
    from fastapi.responses import Response
    return Response(content=(Path("static") / "icon-192.png").read_bytes(), media_type="image/png")


@app.get("/icon-512.png")
async def icon_512():
    from fastapi.responses import Response
    return Response(content=(Path("static") / "icon-512.png").read_bytes(), media_type="image/png")


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
