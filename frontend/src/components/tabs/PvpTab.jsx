import { useState, useEffect } from 'react';
import { TYPE_BG, TYPE_KO, TYPE_EN_FROM_KO } from '../../utils/constants';

const PVP_TABS = [
  { id:'gl',   label:'슈퍼리그',   cp:'≤1500CP' },
  { id:'ul',   label:'하이퍼리그', cp:'≤2500CP' },
  { id:'ml',   label:'마스터리그', cp:'무제한' },
  { id:'raid', label:'레이드',      cp:'공격랭킹' },
  { id:'mega', label:'메가',         cp:'메가랭킹' },
];

function PvpList({ entries, onOpenPokemon }) {
  if (!entries.length) return <div style={{ textAlign:'center', padding:'32px', color:'#475569' }}>데이터가 없어요.</div>;
  return entries.map(e => {
    const spr = e.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${e.dex}.png` : '';
    const rc = e.rank <= 3 ? ' top3' : '';
    const typeKos = (e.types_ko || '').split(' / ').filter(Boolean);
    return (
      <div key={`${e.dex}-${e.rank}`} className="pvp-row" onClick={() => e.dex && onOpenPokemon(e.dex)}>
        <span className={`pvp-rank${rc}`}>#{e.rank}</span>
        {spr ? <img className="pvp-sprite" src={spr} alt={e.ko} onError={ev => ev.target.style.opacity='0.2'} /> : <div className="pvp-sprite" />}
        <div className="pvp-info">
          <div className="pvp-name-line">
            <span className="pvp-name">{e.ko}</span>
            <span className="pvp-type-badges">
              {typeKos.map(t => {
                const en = TYPE_EN_FROM_KO[t] || '';
                return <span key={t} className="type-badge" style={{ background: TYPE_BG[en] || '#71727a', fontSize:'0.55rem', padding:'1px 4px' }}>{t}</span>;
              })}
            </span>
          </div>
          <div className="pvp-moves">{e.fast} / {e.charged}</div>
        </div>
        <span className="pvp-score">{e.score}</span>
      </div>
    );
  });
}

function RaidRankingList({ onOpenPokemon }) {
  const [data, setData] = useState(null);
  const [raidType, setRaidType] = useState('fire');
  const [types, setTypes] = useState([]);

  useEffect(() => {
    fetch('/api/raid_rankings').then(r => r.json()).then(d => {
      setData(d);
      const ts = Object.keys(d).sort((a, b) => (TYPE_KO[a] || a).localeCompare(TYPE_KO[b] || b));
      setTypes(ts);
      if (ts.length && !ts.includes('fire')) setRaidType(ts[0]);
    }).catch(() => setData({}));
  }, []);

  if (!data) return <div style={{ textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>;
  const entries = data[raidType] || [];

  return (
    <>
      <div id="raid-type-filter" style={{ display:'flex' }}>
        {types.map(t => (
          <button key={t} className={`raid-type-btn${raidType===t?' active':''}`} style={{ background: TYPE_BG[t] || '#71727a', color:'#fff' }} onClick={() => setRaidType(t)}>
            {TYPE_KO[t] || t}
          </button>
        ))}
      </div>
      <div id="pvp-list">
        {entries.length > 0 && (
          <div style={{ fontSize:'0.75rem', color:'#64748b', padding:'4px 0 8px', textAlign:'center' }}>
            {TYPE_KO[raidType] || raidType}타입 최강 레이드 공격자 TOP {entries.length}
          </div>
        )}
        {entries.map(e => {
          const spr = e.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${e.dex}.png` : '';
          const rc = e.rank <= 3 ? ' top3' : '';
          return (
            <div key={`${e.dex}-${e.rank}`} className="raid-row" onClick={() => e.dex && onOpenPokemon(e.dex)}>
              <span className={`pvp-rank${rc}`}>#{e.rank}</span>
              {spr ? <img className="pvp-sprite" src={spr} alt={e.ko} onError={ev => ev.target.style.opacity='0.2'} /> : <div className="pvp-sprite" />}
              <div className="pvp-info">
                <div className="pvp-name-line"><span className="pvp-name">{e.ko}</span></div>
                <div className="pvp-moves">{e.fast_ko} / {e.charged_ko}</div>
              </div>
              <span className="raid-score-badge">{e.score?.toLocaleString()}</span>
            </div>
          );
        })}
      </div>
    </>
  );
}

function MegaRankingList({ onOpenPokemon }) {
  const [data, setData] = useState(null);
  const [megaType, setMegaType] = useState('dragon');
  const [types, setTypes] = useState([]);

  useEffect(() => {
    fetch('/api/mega_rankings').then(r => r.json()).then(d => {
      setData(d);
      const ts = Object.keys(d).sort((a, b) => (TYPE_KO[a] || a).localeCompare(TYPE_KO[b] || b));
      setTypes(ts);
      if (ts.length && !ts.includes('dragon')) setMegaType(ts[0]);
    }).catch(() => setData({}));
  }, []);

  if (!data) return <div style={{ textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>;
  const entries = data[megaType] || [];

  return (
    <>
      <div id="mega-type-filter" style={{ display:'flex' }}>
        {types.map(t => (
          <button key={t} className={`raid-type-btn${megaType===t?' active':''}`} style={{ background: TYPE_BG[t] || '#71727a', color:'#fff' }} onClick={() => setMegaType(t)}>
            {TYPE_KO[t] || t}
          </button>
        ))}
      </div>
      <div id="pvp-list">
        {entries.map(e => {
          const spr = e.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${e.dex}.png` : '';
          const rc = e.rank <= 3 ? ' top3' : '';
          return (
            <div key={`${e.dex}-${e.rank}`} className="raid-row" onClick={() => e.dex && onOpenPokemon(e.dex)}>
              <span className={`pvp-rank${rc}`}>#{e.rank}</span>
              {spr ? <img className="pvp-sprite" src={spr} alt={e.ko} onError={ev => ev.target.style.opacity='0.2'} /> : <div className="pvp-sprite" />}
              <div className="pvp-info">
                <div className="pvp-name-line"><span className="pvp-name">{e.ko}</span></div>
                <div className="pvp-moves">{e.fast_ko} / {e.charged_ko}</div>
              </div>
              <span className="raid-score-badge">{e.score?.toLocaleString()}</span>
            </div>
          );
        })}
      </div>
    </>
  );
}

export default function PvpTab({ onOpenPokemon }) {
  const [league, setLeague] = useState('gl');
  const [pvpCache, setPvpCache] = useState({});

  useEffect(() => {
    if (league === 'raid' || league === 'mega') return;
    if (pvpCache[league]) return;
    fetch(`/api/pvp/${league}`).then(r => r.json()).then(d => {
      setPvpCache(prev => ({ ...prev, [league]: d }));
    }).catch(() => {});
  }, [league]);

  return (
    <div className="view" id="view-pvp">
      <div id="pvp-top">
        {PVP_TABS.map(t => (
          <button key={t.id} className={`pvp-tab${league===t.id?' active':''}`} onClick={() => setLeague(t.id)}>
            {t.label}<span className="pvp-cp">{t.cp}</span>
          </button>
        ))}
      </div>
      {league === 'raid' ? (
        <RaidRankingList onOpenPokemon={onOpenPokemon} />
      ) : league === 'mega' ? (
        <MegaRankingList onOpenPokemon={onOpenPokemon} />
      ) : (
        <div id="pvp-list">
          {!pvpCache[league] && <div style={{ textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>}
          {pvpCache[league] && <PvpList entries={pvpCache[league].entries || []} onOpenPokemon={onOpenPokemon} />}
        </div>
      )}
    </div>
  );
}
