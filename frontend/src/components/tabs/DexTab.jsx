import { useState, useEffect, useRef, useCallback } from 'react';
import { TYPE_BG, TYPE_KO, TYPE_LIST, WMO_TO_POGO, POGO_WEATHER } from '../../utils/constants';

const GENS = [0,1,2,3,4,5,6,7,8,9];
const BLANK_IMG = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';

function WeatherBar() {
  const [weather, setWeather] = useState(null);
  const [locText, setLocText] = useState('');

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(async pos => {
      try {
        const { latitude: lat, longitude: lon } = pos.coords;
        const [wRes, gRes] = await Promise.all([
          fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=weather_code`),
          fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&accept-language=ko&zoom=10`, {
            headers: { 'User-Agent': 'PokemonGoChatbot/1.0' },
          }),
        ]);
        const d = await wRes.json();
        const code = d?.current?.weather_code;
        const key = WMO_TO_POGO[code];
        if (!key) return;
        setWeather(POGO_WEATHER[key]);
        try {
          const geo = await gRes.json();
          const addr = geo?.address || {};
          const parts = [addr.state || addr.province, addr.city || addr.county || addr.city_district, addr.suburb || addr.town].filter(Boolean);
          const loc = parts.slice(0, 2).join(' ');
          if (loc) setLocText('📍 ' + loc);
        } catch (_) {}
      } catch (_) {}
    }, () => {}, { timeout: 8000 });
  }, []);

  if (!weather) return null;
  return (
    <div id="weather-bar">
      {locText && <><span id="weather-location">{locText}</span><span style={{ color:'#2d3f55', margin:'0 4px' }}>|</span></>}
      <span>{weather.emoji}</span>
      <span className="w-name">{weather.name}</span>
      <span style={{ color:'#475569', fontSize:'0.68rem' }}>부스트:</span>
      <div className="w-types">
        {weather.types.map(t => (
          <span key={t} className="type-badge" style={{ background: TYPE_BG[t] || '#71727a' }}>{TYPE_KO[t] || t}</span>
        ))}
      </div>
    </div>
  );
}

function DexCard({ p, onOpen, observe }) {
  const ref = useRef(null);
  const [imgSrc, setImgSrc] = useState(BLANK_IMG);
  const loaded = useRef(false);

  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const obs = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && !loaded.current) {
        loaded.current = true;
        setImgSrc(`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png`);
        obs.disconnect();
      }
    }, { rootMargin: '120px' });
    obs.observe(el);
    return () => obs.disconnect();
  }, [p.dex]);

  const num = String(p.dex).padStart(4, '0');
  return (
    <div className="dex-card" onClick={() => onOpen(p.dex)} ref={ref}>
      {p.has_mega && <span className="mega-badge">MEGA</span>}
      <div className="dex-num">#{num}</div>
      <img className={`dex-sprite${imgSrc === BLANK_IMG ? ' loading' : ''}`} src={imgSrc} alt={p.ko} />
      <div className="dex-name">{p.ko}</div>
      <div className="dex-types">
        <span className="type-badge" style={{ background: TYPE_BG[p.t1] || '#71727a' }}>{TYPE_KO[p.t1] || p.t1}</span>
        {p.t2 && <span className="type-badge" style={{ background: TYPE_BG[p.t2] || '#71727a' }}>{TYPE_KO[p.t2] || p.t2}</span>}
      </div>
    </div>
  );
}

export default function DexTab({ onOpenPokemon }) {
  const [dexData, setDexData] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [currentGen, setCurrentGen] = useState(0);
  const [currentType, setCurrentType] = useState('');
  const [search, setSearch] = useState('');
  const [genCounts, setGenCounts] = useState({});
  const searchTimer = useRef(null);
  const [displaySearch, setDisplaySearch] = useState('');

  useEffect(() => {
    fetch('/api/pokedex').then(r => r.json()).then(data => {
      setDexData(data);
      setLoaded(true);
      const counts = {};
      for (const p of data) counts[p.gen] = (counts[p.gen] || 0) + 1;
      setGenCounts(counts);
    });
  }, []);

  const handleSearchInput = (val) => {
    setDisplaySearch(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setSearch(val), 180);
  };

  const filtered = dexData.filter(p => {
    if (currentGen > 0 && p.gen !== currentGen) return false;
    if (currentType && p.t1 !== currentType && p.t2 !== currentType) return false;
    const q = search.trim().toLowerCase();
    if (q) return p.ko.includes(q) || p.en.toLowerCase().includes(q) || String(p.dex).includes(q);
    return true;
  });

  return (
    <div className="view" id="view-dex">
      <div id="dex-top">
        <div id="dex-search-wrap">
          <input
            id="dex-search"
            type="text"
            placeholder="포켓몬 이름으로 검색..."
            value={displaySearch}
            onChange={e => handleSearchInput(e.target.value)}
          />
        </div>
        <WeatherBar />
        <div id="gen-tabs">
          {GENS.map(g => (
            <button
              key={g}
              className={`gen-tab${currentGen === g ? ' active' : ''}`}
              onClick={() => setCurrentGen(g)}
            >
              {g === 0 ? `전체 (${dexData.length})` : `${g}세대${genCounts[g] ? ` (${genCounts[g]})` : ''}`}
            </button>
          ))}
        </div>
        <div id="type-filter-row">
          {TYPE_LIST.map(t => (
            <button
              key={t}
              className={`type-chip${currentType === t ? ' active' : ''}`}
              style={{ background: TYPE_BG[t] || '#71727a' }}
              onClick={() => setCurrentType(currentType === t ? '' : t)}
            >{TYPE_KO[t] || t}</button>
          ))}
        </div>
        <div id="dex-count">{filtered.length.toLocaleString()}마리</div>
      </div>
      <div id="dex-grid">
        {!loaded && <div id="dex-empty">불러오는 중...</div>}
        {loaded && !filtered.length && <div id="dex-empty">검색 결과가 없어요.</div>}
        {filtered.map(p => (
          <DexCard key={p.dex} p={p} onOpen={onOpenPokemon} />
        ))}
      </div>
    </div>
  );
}
