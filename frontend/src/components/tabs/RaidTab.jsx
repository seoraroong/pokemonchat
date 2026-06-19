import { useState, useEffect } from 'react';
import { TYPE_BG, TYPE_KO, TYPE_EN_FROM_KO, TIER_ORDER, TIER_LABEL, WEATHER_ICON } from '../../utils/constants';
import { fmtRemain, fmtUntil, eventTypeCfg } from '../../utils/helpers';

function weatherIcons(list) {
  return (list || []).map(w => WEATHER_ICON[w] || w).join(' ');
}

function RaidCountdown({ raids }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 60000);
    return () => clearInterval(t);
  }, []);

  const tierEnds = {};
  const collect = (tier, boss) => {
    if (boss.end && !tierEnds[tier]) tierEnds[tier] = new Date(boss.end).getTime();
  };
  if (Array.isArray(raids))       raids.forEach(b => collect(b.tier || '5', b));
  else if (raids?.bosses)          raids.bosses.forEach(b => collect(b.tier || '5', b));
  else if (raids)                  Object.keys(raids).forEach(tier => (raids[tier] || []).forEach(b => collect(tier, b)));

  const entries = TIER_ORDER.filter(t => tierEnds[t]).map(t => {
    const diff = tierEnds[t] - Date.now();
    if (diff <= 0) return null;
    const d = Math.floor(diff / 86400000);
    const h = Math.floor((diff % 86400000) / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const time = d >= 1 ? `${d}일 ${h}시간` : h >= 1 ? `${h}시간 ${m}분` : `${m}분`;
    const urgent = diff < 21600000;   // 6시간 미만
    const warning = diff < 86400000;  // 24시간 미만
    const color = urgent ? '#ef4444' : warning ? '#f59e0b' : '#94a3b8';
    return { tier: t, time, urgent, warning, color };
  }).filter(Boolean);

  if (!entries.length) return null;

  return (
    <div style={{ display:'flex', flexWrap:'wrap', gap:6, padding:'6px 0 10px' }}>
      {entries.map(e => (
        <div key={e.tier} style={{
          background: e.urgent ? '#1c1010' : e.warning ? '#1c160a' : '#1e293b',
          border: `1px solid ${e.urgent ? '#7f1d1d' : e.warning ? '#78350f' : '#334155'}`,
          borderRadius: 8, padding:'4px 10px', display:'flex', alignItems:'center', gap:6,
        }}>
          <span style={{ fontSize:'0.7rem', color:'#64748b', fontWeight:700 }}>{TIER_LABEL[e.tier] || e.tier}</span>
          <span style={{ fontSize:'0.72rem', color: e.color, fontWeight:600 }}>⏱ {e.time}</span>
          {e.urgent && <span style={{ fontSize:'0.65rem', color:'#ef4444' }}>교체 임박!</span>}
        </div>
      ))}
    </div>
  );
}

function EventSheet({ event, onClose, onOpenPokemon }) {
  const [tab, setTab] = useState('spawns');
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (!event?.link) return;
    fetch(`/api/event-detail?url=${encodeURIComponent(event.link)}`)
      .then(r => r.json()).then(setDetail).catch(() => {});
  }, [event?.link]);

  if (!event) return null;
  return (
    <>
      <div id="event-spawn-backdrop" className="open" onClick={onClose} />
      <div id="event-spawn-sheet" className="open">
        <div className="region-sheet-drag" />
        <div className="region-sheet-header">
          <div>
            <div className="region-sheet-title">{event.name}</div>
            <div className="region-sheet-sub" id="event-spawn-sub"></div>
          </div>
          <button className="region-sheet-close" onClick={onClose}>✕</button>
        </div>
        <div id="event-detail-tabs">
          {['spawns','bonuses','raids','research'].map(t => (
            <button key={t} className={`event-detail-tab${tab===t?' active':''}`} onClick={() => setTab(t)}>
              {t==='spawns'?'출몰':t==='bonuses'?'보너스':t==='raids'?'레이드':'리서치'}
            </button>
          ))}
        </div>
        <div id="event-detail-body">
          {!detail && <div style={{ textAlign:'center', padding:'32px', color:'#64748b' }}>불러오는 중...</div>}
          {detail && tab === 'spawns' && (
            <div className="event-pm-grid">
              {(detail.pokemon || []).map(p => (
                <div key={p.dex || p.ko} className="region-pm-card" onClick={() => p.dex && onOpenPokemon(p.dex)}>
                  {p.dex && <img className="region-pm-sprite" src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png`} alt={p.ko} onError={e => e.target.style.opacity='0.2'} />}
                  <div className="region-pm-name">{p.ko}</div>
                  {p.shiny && <div style={{ fontSize:'0.6rem', color:'#f59e0b' }}>✦ 색변</div>}
                </div>
              ))}
              {!(detail.pokemon || []).length && <div style={{ color:'#475569', fontSize:'0.82rem' }}>출몰 데이터 없음</div>}
            </div>
          )}
          {detail && tab === 'bonuses' && (
            <ul className="event-bonus-list">
              {(detail.bonuses || []).map((b, i) => <li key={i} className="event-bonus-item">{b}</li>)}
              {!(detail.bonuses || []).length && <li style={{ color:'#475569' }}>보너스 데이터 없음</li>}
            </ul>
          )}
          {detail && tab === 'raids' && (
            <div className="event-pm-grid">
              {(detail.raid_bosses || []).map(p => (
                <div key={p.dex || p.ko} className="region-pm-card" onClick={() => p.dex && onOpenPokemon(p.dex)}>
                  {p.dex && <img className="region-pm-sprite" src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png`} alt={p.ko} onError={e => e.target.style.opacity='0.2'} />}
                  <div className="region-pm-name">{p.ko}</div>
                  {p.shiny && <div style={{ fontSize:'0.6rem', color:'#f59e0b' }}>✦ 색변</div>}
                </div>
              ))}
            </div>
          )}
          {detail && tab === 'research' && (
            <div>
              {(detail.research || []).map((task, i) => (
                <div key={i} className="event-research-item">
                  <div className="event-research-task">{task.text_ko || task.text_en}</div>
                  <div className="event-research-rewards">
                    {(task.rewards || []).map(p => (
                      <div key={p.dex || p.ko} className="region-pm-card" style={{ width:60 }} onClick={() => p.dex && onOpenPokemon(p.dex)}>
                        {p.dex && <img style={{ width:40, height:40, objectFit:'contain' }} src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png`} alt={p.ko} />}
                        <div style={{ fontSize:'0.6rem', color:'#94a3b8', textAlign:'center' }}>{p.ko}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {!(detail.research || []).length && <div style={{ color:'#475569', padding:'16px', textAlign:'center' }}>리서치 데이터 없음</div>}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function CommunityDays({ onOpenPokemon }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);

  const toggle = async () => {
    setOpen(o => !o);
    if (!data) {
      const res = await fetch('/api/community-days').then(r => r.json()).catch(() => []);
      setData(res);
    }
  };

  return (
    <div className="raid-section" id="cd-section" style={{ marginTop: 6 }}>
      <div className="section-title" style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <span>📅 커뮤니티 데이</span>
        <button onClick={toggle} style={{ background:'none', border:'1px solid #334155', borderRadius:8, color:'#64748b', fontSize:'0.68rem', padding:'3px 10px', cursor:'pointer', fontFamily:'inherit' }}>
          {open ? '접기' : '펼치기'}
        </button>
      </div>
      {open && (
        <div id="cd-list" style={{ marginTop: 8, display:'flex', flexDirection:'column', gap:8 }}>
          {!data && <div style={{ textAlign:'center', padding:'16px', color:'#64748b' }}>불러오는 중...</div>}
          {data && !data.length && <div style={{ textAlign:'center', padding:'16px', color:'#475569' }}>데이터 없음</div>}
          {data && data.map((cd, i) => {
            const dt = new Date(cd.start);
            const dateLabel = `${dt.getFullYear()}.${String(dt.getMonth()+1).padStart(2,'0')}`;
            const pmNames = (cd.pokemon || []).map(p => p.ko).join(', ');
            return (
              <div key={i} className="cd-card" onClick={() => cd.link && window.open(cd.link, '_blank')}>
                <div className="cd-date">{dateLabel}</div>
                <div className="cd-sprites">
                  {(cd.pokemon || []).slice(0, 2).map(p => p.dex && (
                    <img key={p.dex} src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${p.dex}.png`} onError={e => e.target.style.display='none'} alt={p.ko} />
                  ))}
                </div>
                <div className="cd-info">
                  <div className="cd-name">{cd.name}</div>
                  {pmNames && <div className="cd-pm-names">{pmNames}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function RaidTab({ onOpenPokemon }) {
  const [events, setEvents] = useState(null);
  const [raids, setRaids] = useState(null);
  const [status, setStatus] = useState('데이터 상태 확인 중...');
  const [statusColor, setStatusColor] = useState('#475569');
  const [activeEvent, setActiveEvent] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = () => {
    Promise.all([
      fetch('/api/events').then(r => r.json()),
      fetch('/api/raids').then(r => r.json()),
    ]).then(([evData, raidData]) => {
      setEvents(evData);
      setRaids(raidData);
    }).catch(() => {});
    fetch('/api/status').then(r => r.json()).then(s => {
      const age = s.raids?.live_age_s;
      if (age != null) {
        const label = age < 60 ? '방금 전' : age < 3600 ? `${Math.floor(age/60)}분 전` : `${Math.floor(age/3600)}시간 전`;
        setStatus(`실시간 데이터 · ${label} 캐시`);
        setStatusColor(age > 3600 ? '#f59e0b' : '#22c55e');
      }
    }).catch(() => {});
  };

  const triggerRefresh = async () => {
    setStatus('갱신 요청 중...'); setStatusColor('#f59e0b');
    try {
      await fetch('/api/admin/refresh', { method: 'POST' });
      setStatus('⏳ 갱신 중... (수 분 소요)');
      setTimeout(loadAll, 12000);
    } catch {
      setStatus('요청 실패'); setStatusColor('#ef4444');
    }
  };

  const renderRaids = () => {
    if (!raids) return <p className="raid-empty">불러오는 중...</p>;
    const byTier = {};
    if (Array.isArray(raids)) {
      for (const boss of raids) {
        const tier = boss.tier || '5';
        if (!byTier[tier]) byTier[tier] = [];
        byTier[tier].push(boss);
      }
    } else if (raids.bosses) {
      for (const boss of raids.bosses) {
        const tier = boss.tier || '5';
        if (!byTier[tier]) byTier[tier] = [];
        byTier[tier].push(boss);
      }
    } else {
      // { "1": [...], "3": [...], "5": [...], "mega": [...] } 형태
      for (const tier of Object.keys(raids)) {
        if (Array.isArray(raids[tier])) byTier[tier] = raids[tier];
      }
    }
    if (!Object.values(byTier).some(a => a?.length)) return <p className="raid-empty">레이드 데이터가 없어요.</p>;
    return TIER_ORDER.filter(t => byTier[t]?.length).map(tier => {
      const label = TIER_LABEL[tier] || `${tier}성`;
      const bosses = byTier[tier];
      return (
        <div key={tier} className="tier-section">
          <div className="tier-label">{label} ({bosses.length})</div>
          <div className="raid-grid">
            {bosses.map((boss, i) => {
              const isShadow = (boss.en_name || '').toLowerCase().startsWith('shadow');
              const spriteDex = boss.form_dex || boss.dex;
              const artUrl = spriteDex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${spriteDex}.png` : '';
              const fbUrl = spriteDex ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${spriteDex}.png` : '';
              const typeKos = boss.types_ko ? boss.types_ko.split(' / ') : [];
              const spriteEl = <img className="raid-sprite" src={artUrl || fbUrl} alt={boss.ko_name} onError={e => { if (fbUrl) e.target.src = fbUrl; }} />;
              return (
                <div key={i} className="raid-card" onClick={() => boss.dex && onOpenPokemon(boss.dex, boss.slug, isShadow, boss.form_dex)}>
                  {isShadow ? <div className="shadow-aura">{spriteEl}</div> : spriteEl}
                  <div className="raid-name">{boss.ko_name}</div>
                  {boss.is_shiny && <div className="raid-shiny">✦ 색변</div>}
                  <div className="raid-types">
                    {typeKos.map(t => {
                      const en = TYPE_EN_FROM_KO[t] || '';
                      return <span key={t} className="type-badge" style={{ background: TYPE_BG[en] || '#71727a', fontSize:'0.56rem', padding:'1px 5px' }}>{t}</span>;
                    })}
                  </div>
                  {boss.cp_min && boss.cp_max && <div className="raid-cp">{boss.cp_min.toLocaleString()}–{boss.cp_max.toLocaleString()}</div>}
                  {boss.weather?.length > 0 && <div className="raid-weather">{weatherIcons(boss.weather)}</div>}
                </div>
              );
            })}
          </div>
        </div>
      );
    });
  };

  const renderEvents = () => {
    if (!events) return <p className="raid-empty">불러오는 중...</p>;
    const allEvents = [...(events.active || []), ...(events.upcoming || [])];
    if (!allEvents.length) return <p className="raid-empty">현재 이벤트 정보가 없어요.</p>;
    return (
      <>
        {events.active?.length > 0 && (
          <>
            <div style={{ fontSize:'0.72rem', color:'#22c55e', fontWeight:600, marginBottom:8, paddingLeft:2 }}>● 진행 중</div>
            {events.active.map((e, i) => {
              const cfg = eventTypeCfg(e.type);
              return (
                <div key={i} className={`event-card${e.link?' clickable':''}`} onClick={() => e.link && setActiveEvent(e)}>
                  <div className="event-active-dot" />
                  <div className="event-info">
                    <div className="event-name">{e.name}</div>
                    <div className="event-time">{fmtRemain(e.end)}</div>
                    {e.link && <div className="event-spawn-hint">👆 이벤트 정보 보기</div>}
                  </div>
                  <span className="event-type-badge" style={{ background: cfg.bg }}>{cfg.text}</span>
                </div>
              );
            })}
          </>
        )}
        {events.upcoming?.length > 0 && (
          <>
            <div style={{ fontSize:'0.72rem', color:'#64748b', fontWeight:600, margin:`${events.active?.length?'12px':'0'}px 0 8px 2px` }}>◎ 7일 내 예정</div>
            {events.upcoming.map((e, i) => {
              const cfg = eventTypeCfg(e.type);
              return (
                <div key={i} className={`event-card${e.link?' clickable':''}`} onClick={() => e.link && setActiveEvent(e)}>
                  <div className="event-info">
                    <div className="event-name">{e.name}</div>
                    <div className="event-time">{fmtUntil(e.start)}</div>
                    {e.link && <div className="event-spawn-hint">👆 이벤트 정보 보기</div>}
                  </div>
                  <span className="event-type-badge" style={{ background: cfg.bg }}>{cfg.text}</span>
                </div>
              );
            })}
          </>
        )}
      </>
    );
  };

  return (
    <div className="view" id="view-raid" style={{ position: 'relative' }}>
      <div id="raid-inner">
        <div className="raid-section">
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'2px 2px 10px', gap:8 }}>
            <span style={{ fontSize:'0.68rem', color: statusColor }}>{status}</span>
            <button onClick={triggerRefresh} style={{ background:'#1e293b', border:'1px solid #334155', borderRadius:8, color:'#94a3b8', fontSize:'0.68rem', padding:'4px 10px', cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' }}>🔄 갱신</button>
          </div>
          <div className="section-title">🗓️ 이벤트</div>
          <div id="events-container">{renderEvents()}</div>
        </div>
        <div className="raid-section" style={{ marginTop: 6 }}>
          <div className="section-title">⚔️ 현재 레이드 보스</div>
          {raids && <RaidCountdown raids={raids} />}
          <div id="raids-container">{renderRaids()}</div>
        </div>
        <CommunityDays onOpenPokemon={onOpenPokemon} />
        <div style={{ height: 20 }} />
      </div>
      {activeEvent && (
        <EventSheet event={activeEvent} onClose={() => setActiveEvent(null)} onOpenPokemon={onOpenPokemon} />
      )}
    </div>
  );
}
