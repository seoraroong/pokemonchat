import { useState, useEffect, useRef } from 'react';
import { TYPE_BG, TYPE_KO, WEATHER_BOOST } from '../utils/constants';
import { esc, toSlug, weatherBoostTypes } from '../utils/helpers';

function MoveChip({ move, isElite }) {
  const dot = move.type
    ? <span className="move-type-dot" style={{ background: TYPE_BG[move.type] || '#71727a' }} />
    : null;
  const dps  = move.dps  != null ? <span className="move-dps">{move.dps}</span>  : null;
  const eps  = move.eps  != null ? <span className="move-eps">⚡{move.eps}</span> : null;
  return (
    <span className={`move-chip${isElite ? ' elite' : ''}`}>
      {dot}{move.ko}{isElite ? ' ✦' : ''}{dps}{eps}
    </span>
  );
}

function WeaknessSection({ weaknesses }) {
  if (!weaknesses) return null;
  const { weak = [], resist = [], immune = [] } = weaknesses;
  if (!weak.length && !resist.length && !immune.length) return null;

  const mkBadge = (item, cls) => {
    const bg = TYPE_BG[item.type] || '#71727a';
    const ko = TYPE_KO[item.type] || item.type;
    const mult = item.mult === 4 ? '4×' : item.mult === 2 ? '2×' :
                 item.mult === 0.5 ? '½×' : item.mult === 0.25 ? '¼×' :
                 item.mult === 0 ? '0×' : `${item.mult}×`;
    return (
      <span key={item.type} className="w-badge">
        <span className="type-badge" style={{ background: bg }}>{ko}</span>
        <span className={`w-mult ${cls}`}>{mult}</span>
      </span>
    );
  };
  const weaks   = [...weak].sort((a, b) => b.mult - a.mult);
  const resists = [...resist, ...immune].sort((a, b) => a.mult - b.mult);

  return (
    <div className="weakness-section">
      {weaks.length > 0 && (
        <div className="weakness-row">
          <span className="weakness-label">약점</span>
          {weaks.map(x => mkBadge(x, x.mult >= 4 ? 'weak4x' : 'weak'))}
        </div>
      )}
      {resists.length > 0 && (
        <div className="weakness-row">
          <span className="weakness-label">내성</span>
          {resists.map(x => mkBadge(x, x.mult === 0 ? 'immune' : 'resist'))}
        </div>
      )}
    </div>
  );
}

function PvpMoveset({ dex }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    fetch(`/api/pvp-moveset/${dex}`).then(r => r.json()).then(setData).catch(() => {});
  }, [dex]);

  if (!data) return <div style={{ textAlign:'center', padding:'6px', color:'#64748b', fontSize:'0.78rem' }}>불러오는 중...</div>;
  const leagues = [['gl','슈퍼'],['ul','하이퍼'],['ml','마스터']];
  const rows = leagues.filter(([k]) => data[k]);
  if (!rows.length) return <div style={{ textAlign:'center', padding:'6px', color:'#475569', fontSize:'0.78rem' }}>PvP 랭킹 데이터 없음</div>;
  return (
    <div className="pvp-moveset-section">
      {rows.map(([k, name]) => {
        const d = data[k];
        return (
          <div key={k} className="pvp-league-row">
            <span className="pvp-league-label">{name}</span>
            <span className="pvp-league-rank">#{d.rank}</span>
            <div className="pvp-league-moves">{d.fast} / {d.charged}</div>
          </div>
        );
      })}
    </div>
  );
}

function Counters({ slug, onOpenPokemon }) {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(!!slug);

  useEffect(() => {
    if (!expanded || !slug) return;
    fetch(`/api/raid-counters/${slug}`).then(r => r.json()).then(setData).catch(() => setData({}));
  }, [expanded, slug]);

  if (!expanded) return (
    <button className="popup-secondary-btn" onClick={() => setExpanded(true)}>▶ 카운터 보기</button>
  );
  if (!data) return <div style={{ textAlign:'center', padding:'10px', color:'#64748b', fontSize:'0.8rem' }}>불러오는 중...</div>;
  if (!data.counters?.length) return <div style={{ textAlign:'center', padding:'10px', color:'#475569', fontSize:'0.8rem' }}>카운터 데이터가 없어요.</div>;

  return (
    <>
      {data.weakness && <div className="counter-weakness">약점: {data.weakness}</div>}
      {data.counters.slice(0, 12).map(c => {
        const spr = c.dex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${c.dex}.png` : '';
        const rc = +c.rank <= 3 ? ' top3' : '';
        return (
          <div key={c.rank} className="counter-row" onClick={() => c.dex && onOpenPokemon(c.dex)}>
            <span className={`counter-rank${rc}`}>#{c.rank}</span>
            {spr ? <img className="counter-sprite" src={spr} alt={c.ko} onError={e => e.target.style.opacity='0.2'} /> : <div className="counter-sprite" />}
            <div className="counter-info">
              <div className="counter-name">{c.ko}</div>
              <div className="counter-move">{c.move}{c.score != null ? <span className="counter-score">{c.score.toFixed(0)}</span> : null}</div>
            </div>
          </div>
        );
      })}
    </>
  );
}

function EvoChain({ dex, onOpenPokemon }) {
  const [chain, setChain] = useState(null);
  useEffect(() => {
    fetch(`/api/evolutions/${dex}`).then(r => r.json()).then(setChain).catch(() => {});
  }, [dex]);
  if (!chain?.length || chain.length <= 1) return null;

  return (
    <div className="move-section">
      <div className="move-section-title">진화 체인</div>
      <div className="evo-chain">
        {chain.map((stage, si) => (
          <div key={si} style={{ display:'flex', alignItems:'flex-start', gap:'3px' }}>
            {si > 0 && <div className="evo-arrow">→</div>}
            <div className="evo-stage">
              {stage.map(pm => (
                <div
                  key={pm.dex}
                  className={`evo-pm${pm.dex === dex ? ' current' : ''}`}
                  onClick={() => pm.dex !== dex && onOpenPokemon(pm.dex)}
                >
                  <img src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pm.dex}.png`} width={46} height={46} alt={pm.ko} />
                  <div className="evo-pm-name">{pm.ko}</div>
                  {pm.condition && <div className="evo-cond">{pm.condition}</div>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PokemonPopup({ dex, slug, isShadow, formDex: initFormDex, onClose, onOpenPokemon }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [shiny, setShiny] = useState(false);
  const [formIdx, setFormIdx] = useState(0);
  const [spriteDex, setSpriteDex] = useState(initFormDex || dex);

  useEffect(() => {
    setLoading(true); setData(null); setShiny(false); setFormIdx(0);
    setSpriteDex(initFormDex || dex);
    fetch(`/api/pokemon/${dex}`).then(r => r.json()).then(p => {
      setData(p); setLoading(false);
    }).catch(() => setLoading(false));
  }, [dex, initFormDex]);

  const switchForm = (fDex, idx) => {
    setFormIdx(idx);
    setSpriteDex(fDex);
    setShiny(false);
  };

  if (loading || !data) {
    return (
      <>
        <div id="popup-overlay" className="open" onClick={onClose} />
        <div id="pokemon-popup" className="open">
          <div className="popup-drag" />
          <div className="popup-close-row"><button className="popup-close" onClick={onClose}>✕</button></div>
          <div className="popup-body" style={{ textAlign:'center', padding:'36px 0', color: loading ? '#64748b' : '#475569' }}>
            {loading ? '불러오는 중...' : '데이터를 불러올 수 없어요.'}
          </div>
        </div>
      </>
    );
  }

  const p = data;
  const forms = p.forms || [];
  const curForm = formIdx > 0 && forms[formIdx - 1] || null;

  const curT1 = curForm?.t1 || p.t1;
  const curT2 = curForm?.t2 || p.t2 || '';
  const curAtk = curForm?.atk ?? p.atk;
  const curDef = curForm?.def ?? p.def;
  const curSta = curForm?.sta ?? p.sta;
  const curCp40 = curForm?.cp40 ?? p.cp40;
  const curWeaknesses = curForm?.weaknesses || p.weaknesses;
  const curFast    = curForm?.fast_moves    || p.fast_moves    || [];
  const curCharged = curForm?.charged_moves || p.charged_moves || [];
  const curEliteFast    = (curForm?.elite_fast    || p.elite_fast    || []).map(m => m.id);
  const curEliteCharged = (curForm?.elite_charged || p.elite_charged || []).map(m => m.id);

  const num = String(p.dex).padStart(4, '0');
  const artUrl   = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${spriteDex}.png`;
  const shinyUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny/${spriteDex}.png`;
  const fbUrl    = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${spriteDex}.png`;
  const counterSlug = slug || toSlug(p.en);

  const boosts = weatherBoostTypes(curT1, curT2);

  const spriteEl = (
    <img
      className="popup-sprite"
      src={shiny ? shinyUrl : artUrl}
      alt={p.ko}
      onError={e => { e.target.src = fbUrl; }}
    />
  );

  return (
    <>
      <div id="popup-overlay" className="open" onClick={onClose} />
      <div id="pokemon-popup" className="open">
        <div className="popup-drag" />
        <div className="popup-close-row">
          <button className="popup-close" onClick={onClose}>✕</button>
        </div>
        <div className="popup-body">
          {isShadow
            ? <div style={{ textAlign:'center' }}><div className="shadow-aura" style={{ display:'inline-flex' }}>{spriteEl}</div></div>
            : spriteEl
          }
          <button
            className={`shiny-toggle-btn${shiny ? ' active' : ''}`}
            onClick={() => setShiny(s => !s)}
          >✦ 색변 보기</button>

          {forms.length > 0 && (
            <>
              <div className="form-switcher">
                <button className={`form-btn${formIdx === 0 ? ' active' : ''}`} onClick={() => switchForm(dex, 0)}>기본</button>
                {forms.map((f, i) => (
                  <button
                    key={i}
                    className={`form-btn${formIdx === i + 1 ? ' active' : ''}`}
                    onClick={() => switchForm(f.form_dex, i + 1)}
                  >{f.label}</button>
                ))}
              </div>
              {curForm?.note && <div className="form-note">{curForm.note}</div>}
            </>
          )}

          <div className="popup-num">#{num}</div>
          <div className="popup-ko">{p.ko}</div>
          <div className="popup-en">{p.en}</div>

          <div className="popup-types">
            <span className="type-badge" style={{ background: TYPE_BG[curT1] || '#71727a' }}>{TYPE_KO[curT1] || curT1}</span>
            {curT2 && <span className="type-badge" style={{ background: TYPE_BG[curT2] || '#71727a' }}>{TYPE_KO[curT2] || curT2}</span>}
          </div>

          {p.flavor_text && <div className="popup-flavor">{p.flavor_text}</div>}

          <WeaknessSection weaknesses={curWeaknesses} />

          {boosts.length > 0 && (
            <div className="weather-boost">날씨 부스트: {boosts.join(' / ')}</div>
          )}

          <div className="stat-grid">
            <div className="stat-item"><div className="stat-label">공격</div><div className="stat-val">{curAtk || '—'}</div></div>
            <div className="stat-item"><div className="stat-label">방어</div><div className="stat-val">{curDef || '—'}</div></div>
            <div className="stat-item"><div className="stat-label">체력</div><div className="stat-val">{curSta || '—'}</div></div>
            <div className="stat-item"><div className="stat-label">Max CP</div><div className="stat-val">{curCp40 ? curCp40.toLocaleString() : '—'}</div></div>
          </div>

          {isShadow && (
            <div className="shadow-info-box">
              <div className="shadow-info-title">⚡ 다크 포켓몬 보정</div>
              <div className="shadow-stat-row"><span className="shadow-stat-label">공격력</span><span className="shadow-atk">× 1.2 &nbsp;↑ 20%</span></div>
              <div className="shadow-stat-row"><span className="shadow-stat-label">방어력</span><span className="shadow-def">× 0.833 &nbsp;↓ 17%</span></div>
              <div className="shadow-note">기본 기술로 <b style={{ color:'#c084fc' }}>답답함 (Frustration)</b> 고정 장착<br />이벤트 기간에만 다른 기술로 교체 가능 · 정화 시 일반 포켓몬으로 전환</div>
            </div>
          )}

          <EvoChain dex={dex} onOpenPokemon={onOpenPokemon} />

          {curFast.length > 0 && (
            <div className="move-section">
              <div className="move-section-title">빠른 기술</div>
              <div className="move-list">
                {curFast.map(m => <MoveChip key={m.id} move={m} isElite={curEliteFast.includes(m.id)} />)}
              </div>
            </div>
          )}
          {curCharged.length > 0 && (
            <div className="move-section">
              <div className="move-section-title">스페셜 기술</div>
              <div className="move-list">
                {curCharged.map(m => <MoveChip key={m.id} move={m} isElite={curEliteCharged.includes(m.id)} />)}
              </div>
            </div>
          )}

          <div className="move-section">
            <div className="move-section-title">🏆 PvP 추천 기술셋</div>
            <PvpMoveset dex={dex} />
          </div>

          <div className="move-section">
            <div className="move-section-title">⚔️ 레이드 카운터</div>
            <Counters slug={counterSlug} onOpenPokemon={onOpenPokemon} />
          </div>

          <button
            className="popup-chat-btn"
            onClick={() => { onClose(); }}
          >💬 채팅에서 더 알아보기</button>
        </div>
      </div>
    </>
  );
}
