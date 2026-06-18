import { useState, useEffect } from 'react';
import { TYPE_BG, TYPE_KO } from '../../utils/constants';

const KM_ORDER = ['2km','5km','7km','10km','12km','1km'];

function EggList({ eggs, onOpenPokemon }) {
  if (!eggs.length) return <div style={{ textAlign:'center', padding:'32px', color:'#475569' }}>해당 거리 알 데이터가 없어요.</div>;
  return eggs.map(p => {
    const spr = p.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png` : '';
    return (
      <div key={p.dex || p.ko} className="egg-card" onClick={() => p.dex && onOpenPokemon(p.dex)}>
        {spr ? <img className="egg-sprite" src={spr} alt={p.ko} onError={e => e.target.style.opacity='0.2'} /> : null}
        <div className="egg-name">{p.ko}</div>
        <div className="dex-types">
          {p.t1 && <span className="type-badge" style={{ background: TYPE_BG[p.t1] || '#71727a' }}>{TYPE_KO[p.t1] || p.t1}</span>}
          {p.t2 && <span className="type-badge" style={{ background: TYPE_BG[p.t2] || '#71727a' }}>{TYPE_KO[p.t2] || p.t2}</span>}
        </div>
        {p.rarity && <div className="egg-rarity">{p.rarity}</div>}
        <div className="egg-badges">
          {p.shiny && <span className="egg-badge shiny">✦색변</span>}
          {p.as_only && <span className="egg-badge as">AS전용</span>}
        </div>
      </div>
    );
  });
}

function RocketList({ onOpenPokemon }) {
  const [data, setData] = useState(null);
  const [filterType, setFilterType] = useState('');
  const [types, setTypes] = useState([]);

  useEffect(() => {
    fetch('/api/rockets').then(r => r.json()).then(d => {
      setData(d);
      const ts = [...new Set(d.filter(e => e.type).map(e => e.type))].sort();
      setTypes(ts);
    }).catch(() => setData([]));
  }, []);

  if (!data) return <div style={{ textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>;
  if (!data.length) return <div style={{ textAlign:'center', padding:'32px', color:'#475569' }}>데이터 없음</div>;

  const filtered = filterType ? data.filter(e => e.type === filterType) : data;

  return (
    <>
      <div id="rocket-type-filter">
        <button className={`type-chip${filterType===''?' active':''}`} style={{ background:'#334155' }} onClick={() => setFilterType('')}>전체</button>
        {types.map(t => (
          <button key={t} className={`type-chip${filterType===t?' active':''}`} style={{ background: TYPE_BG[t] || '#334155' }} onClick={() => setFilterType(t)}>
            {TYPE_KO[t] || t}
          </button>
        ))}
      </div>
      <div id="rocket-list">
        {filtered.map((e, i) => {
          const bg = TYPE_BG[e.type] || '#334155';
          const typeKo = e.type ? (TYPE_KO[e.type] || e.type) : '';
          const headerLabel = e.title === 'Team GO Rocket Boss' ? '👑 보스' :
                              e.title === 'Team GO Rocket Leader' ? '⭐ 간부' : `${typeKo} 그런트`;
          const mkSlot = (label, pms) => (
            <div className="rocket-slot" key={label}>
              <div className="rocket-slot-label">{label}</div>
              <div className="rocket-pm-list">
                {pms.map((pm, pi) => {
                  const spr = pm.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pm.dex}.png` : '';
                  return (
                    <div key={pi} className="rocket-pm" onClick={e => { e.stopPropagation(); pm.dex && onOpenPokemon(pm.dex); }}>
                      {spr ? <img src={spr} width={30} height={30} onError={ev => ev.target.style.opacity='0.2'} alt={pm.ko} /> : <div style={{ width:30, height:30 }} />}
                      <div className="rocket-pm-info">
                        <div className="rocket-pm-name">{pm.ko}</div>
                        {pm.is_encounter && <span className="rocket-pm-enc">✦ 만남</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
          return (
            <div key={i} className="rocket-card">
              <div className="rocket-card-header">
                <div className="rocket-type-dot" style={{ background: bg }} />
                <div className="rocket-name">{headerLabel} — {e.name}</div>
              </div>
              <div className="rocket-slots">
                {mkSlot('1번째', e.first || [])}
                {mkSlot('2번째', e.second || [])}
                {mkSlot('3번째', e.third || [])}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

export default function EggTab({ onOpenPokemon }) {
  const [mode, setMode] = useState('egg');
  const [eggData, setEggData] = useState(null);
  const [currentKm, setCurrentKm] = useState('2km');
  const [kmCounts, setKmCounts] = useState({});

  useEffect(() => {
    fetch('/api/eggs').then(r => r.json()).then(d => {
      setEggData(d);
      const counts = {};
      for (const km of KM_ORDER) counts[km] = (d[km] || []).length;
      setKmCounts(counts);
    }).catch(() => setEggData({}));
  }, []);

  const eggs = eggData?.[currentKm] || [];

  return (
    <div className="view" id="view-egg">
      <div id="egg-mode-toggle">
        <button className={`egg-mode-btn${mode==='egg'?' active':''}`} onClick={() => setMode('egg')}>🥚 알 부화</button>
        <button className={`egg-mode-btn${mode==='rocket'?' active':''}`} onClick={() => setMode('rocket')}>🚀 로켓단</button>
      </div>

      {mode === 'egg' && (
        <>
          <div id="egg-top">
            <div id="egg-km-tabs">
              {KM_ORDER.map(km => (
                <button
                  key={km}
                  className={`km-tab${currentKm===km?' active':''}`}
                  style={{ opacity: kmCounts[km] === 0 ? 0.4 : 1 }}
                  onClick={() => setCurrentKm(km)}
                >
                  {kmCounts[km] ? `${km} (${kmCounts[km]})` : km}
                </button>
              ))}
            </div>
            <div id="egg-count">{eggs.length}마리</div>
          </div>
          <div id="egg-grid">
            {!eggData && <div style={{ gridColumn:'1/-1', textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>}
            {eggData && <EggList eggs={eggs} onOpenPokemon={onOpenPokemon} />}
          </div>
        </>
      )}

      {mode === 'rocket' && (
        <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column', minHeight:0 }}>
          <RocketList onOpenPokemon={onOpenPokemon} />
        </div>
      )}
    </div>
  );
}
