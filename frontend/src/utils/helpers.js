import { TYPE_KO, TYPE_BG, WEATHER_BOOST, WEATHER_ICON } from './constants';

export function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;');
}

export function toSlug(en) {
  return en.toLowerCase()
    .replace(/'/g,'').replace(/\./g,'')
    .replace(/\s+/g,'-').replace(/[^a-z0-9-]/g,'');
}

export function fmtRemain(endIso) {
  const diff = new Date(endIso) - Date.now();
  if (diff <= 0) return '종료됨';
  const h = Math.floor(diff / 3600000), d = Math.floor(h / 24);
  return d >= 2 ? `${d}일 후 종료` : h >= 1 ? `${h}시간 후 종료` : `${Math.floor(diff/60000)}분 후 종료`;
}

export function fmtUntil(startIso) {
  const diff = new Date(startIso) - Date.now();
  if (diff <= 0) return '진행 중';
  const h = Math.floor(diff / 3600000), d = Math.floor(h / 24);
  return d >= 1 ? `${d}일 후 시작` : h >= 1 ? `${h}시간 후 시작` : `${Math.floor(diff/60000)}분 후 시작`;
}

export function weatherBoostTypes(t1, t2) {
  return [...new Set([t1, t2].filter(Boolean).map(t => WEATHER_BOOST[t]).filter(Boolean))];
}

export function weatherIcons(list) {
  return (list || []).map(w => WEATHER_ICON[w] || w).join(' ');
}

export function typeBadge(type) {
  return { label: TYPE_KO[type] || type, bg: TYPE_BG[type] || '#71727a' };
}

function inline(s) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function buildTable(rows) {
  const parsed = rows.map(r => r.trim().replace(/^\||\|$/g,'').split('|').map(c => c.trim()));
  const data = parsed.filter(r => !r.every(c => /^[-: ]+$/.test(c)));
  if (!data.length) return '';
  const [head, ...body] = data;
  return `<table><thead><tr>${head.map(c=>`<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${body.map(r=>'<tr>'+r.map(c=>`<td>${inline(c)}</td>`).join('')+'</tr>').join('')}</tbody></table>`;
}

export function renderMd(raw) {
  const lines = raw.split('\n'), out = []; let i = 0;
  while (i < lines.length) {
    const line = lines[i], t = line.trim();
    const hm = t.match(/^(#{1,3})\s+(.+)/);
    if (hm) { out.push(`<h${hm[1].length}>${inline(hm[2])}</h${hm[1].length}>`); i++; continue; }
    if (t.startsWith('|')) {
      const tbl = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { tbl.push(lines[i]); i++; }
      out.push(buildTable(tbl)); continue;
    }
    if (/^[-*]\s/.test(t)) {
      const items = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/,'')); i++;
      }
      out.push('<ul>' + items.map(it=>`<li>${inline(it)}</li>`).join('') + '</ul>'); continue;
    }
    if (t === '') { if (out.length && out[out.length-1] !== '<br>') out.push('<br>'); i++; continue; }
    out.push(inline(line) + '<br>'); i++;
  }
  while (out.length && out[out.length-1] === '<br>') out.pop();
  return out.join('');
}

export function eventTypeCfg(type) {
  const map = {
    'event':           { bg:'#1e40af', text:'이벤트' },
    'community-day':   { bg:'#15803d', text:'커뮤니티 데이' },
    'raid-battles':    { bg:'#7c3aed', text:'레이드 배틀' },
    'raid-hour':       { bg:'#6d28d9', text:'레이드 아워' },
    'raid-day':        { bg:'#5b21b6', text:'레이드 데이' },
    'go-battle-league':{ bg:'#b45309', text:'GO 배틀리그' },
    'pokemon-go-fest': { bg:'#be185d', text:'GO 페스트' },
    'max-mondays':     { bg:'#0e7490', text:'맥스 먼데이' },
    'season':          { bg:'#374151', text:'시즌' },
    'twitch-drops':    { bg:'#7c2d12', text:'트위치 드롭' },
    'go-pass':         { bg:'#1e3a5f', text:'GO 패스' },
  };
  return map[type] || { bg:'#374151', text: type || '이벤트' };
}
