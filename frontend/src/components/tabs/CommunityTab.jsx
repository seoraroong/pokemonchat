import { useState, useEffect, useRef, useCallback } from 'react';

function fmtAge(ts) {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60)   return '방금 개설';
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전 개설`;
  return `${Math.floor(diff / 3600)}시간 전 개설`;
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── 닉네임 입력 ──────────────────────────────────────────────────────
function NickScreen({ onEnter }) {
  const [nick, setNick] = useState(() => localStorage.getItem('cm_nick') || '');
  const enter = () => {
    const n = nick.trim().slice(0, 15);
    if (!n) return;
    localStorage.setItem('cm_nick', n);
    onEnter(n);
  };
  return (
    <div id="cm-nick-screen" className="cm-screen">
      <div className="cm-nick-logo" />
      <div className="cm-nick-title">PokeMORE 소통방</div>
      <div className="cm-nick-sub">닉네임을 설정하고<br />다른 트레이너들과 이야기해보세요!</div>
      <input
        id="cm-nick-input" className="cm-screen" style={{ width:'100%', background:'#1e293b', border:'1px solid #334155', borderRadius:14, padding:'12px 16px', color:'#e2e8f0', fontSize:'1rem', outline:'none', textAlign:'center', fontFamily:'inherit' }}
        placeholder="닉네임 입력 (최대 15자)"
        value={nick}
        onChange={e => setNick(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && enter()}
        maxLength={15}
      />
      <button className="cm-enter-btn" onClick={enter}>입장하기 →</button>
    </div>
  );
}

// ── 로비 ─────────────────────────────────────────────────────────────
function LobbyScreen({ nick, onJoin, onChangeNick, onCatchmind, onBattle }) {
  const [rooms, setRooms] = useState([]);
  const [epoch, setEpoch] = useState(null);
  const [showRestart, setShowRestart] = useState(false);
  const timerRef = useRef(null);

  const loadRooms = useCallback(async () => {
    try {
      const data = await fetch('/api/rooms').then(r => r.json());
      if (epoch !== null && data.epoch !== epoch) setShowRestart(true);
      setEpoch(data.epoch);
      setRooms(data.rooms || []);
    } catch {}
  }, [epoch]);

  useEffect(() => {
    loadRooms();
    timerRef.current = setInterval(loadRooms, 8000);
    return () => clearInterval(timerRef.current);
  }, [loadRooms]);

  const createRoom = async () => {
    const name = prompt('채팅방 이름을 입력하세요 (최대 30자):');
    if (!name?.trim()) return;
    try {
      const r = await fetch('/api/rooms', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim().slice(0, 30) }),
      }).then(res => res.json());
      if (r.error) { alert(r.error); return; }
      clearInterval(timerRef.current);
      onJoin(r.id, r.name);
    } catch { alert('방 만들기에 실패했어요.'); }
  };

  return (
    <div id="cm-lobby-screen" className="cm-screen" style={{ display:'flex', flexDirection:'column' }}>
      <div id="cm-lobby-header">
        <span id="cm-lobby-nick" style={{ fontSize:'0.82rem', color:'#94a3b8', cursor:'pointer', textDecoration:'underline dotted' }} onClick={onChangeNick}>
          👤 {nick}
        </span>
        <div style={{ display:'flex', gap:6, alignItems:'center', marginLeft:'auto' }}>
          <button onClick={loadRooms} title="새로고침" style={{ background:'none', border:'none', color:'#64748b', fontSize:'1rem', cursor:'pointer', padding:'4px 6px', lineHeight:1 }}>🔄</button>
          <button onClick={onCatchmind} style={{ background:'#92400e', border:'none', borderRadius:8, padding:'6px 12px', color:'#fef3c7', fontSize:'0.78rem', fontWeight:600, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' }}>🎨 캐치마인드</button>
          <button onClick={onBattle} style={{ background:'#7c3aed', border:'none', borderRadius:8, padding:'6px 12px', color:'#ede9fe', fontSize:'0.78rem', fontWeight:600, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' }}>⚔️ 배틀</button>
          <button onClick={createRoom} style={{ background:'#1d4ed8', border:'none', borderRadius:8, padding:'6px 12px', color:'#fff', fontSize:'0.78rem', fontWeight:600, cursor:'pointer', fontFamily:'inherit', whiteSpace:'nowrap' }}>+ 채팅방 만들기</button>
        </div>
      </div>
      {showRestart && (
        <div style={{ background:'#78350f', border:'1px solid #d97706', borderRadius:10, padding:'9px 12px', fontSize:'0.75rem', color:'#fde68a', margin:'0 12px 8px', display:'flex', alignItems:'center', justifyContent:'space-between', gap:8, flexShrink:0 }}>
          <span>⚠️ 서버가 재시작되어 채팅방 목록이 초기화됐습니다.</span>
          <button onClick={() => setShowRestart(false)} style={{ background:'none', border:'none', color:'#fde68a', cursor:'pointer', fontSize:'1rem' }}>✕</button>
        </div>
      )}
      <div id="cm-room-list">
        {!rooms.length
          ? <div className="cm-empty-rooms">채팅방이 없어요!<br />첫 번째 방을 만들어보세요 👆</div>
          : rooms.map(r => {
              const full = r.count >= r.max;
              const badgeCls = full ? 'full' : r.count > 0 ? 'active' : '';
              const meta = full ? '🔒 정원 초과' : (r.created_at ? fmtAge(r.created_at) : '입장 가능');
              return (
                <div key={r.id} className={`cm-room-item${full?' full':''}`} onClick={() => !full && (clearInterval(timerRef.current), onJoin(r.id, r.name))}>
                  <div>
                    <div className="cm-room-name">{r.name}</div>
                    <div className="cm-room-meta">{meta}</div>
                  </div>
                  <div className={`cm-room-badge${badgeCls?' '+badgeCls:''}`}>{r.count}/{r.max}</div>
                </div>
              );
            })
        }
      </div>
    </div>
  );
}

// ── 채팅방 ────────────────────────────────────────────────────────────
function RoomScreen({ nick, roomId, roomName, onLeave, onOpenPokemon }) {
  const [msgs, setMsgs] = useState([]);
  const [count, setCount] = useState(0);
  const [sendDisabled, setSendDisabled] = useState(false);
  const [typingText, setTypingText] = useState('');
  const [input, setInput] = useState('');
  const [quizActive, setQuizActive] = useState(false);
  const [quizScores, setQuizScores] = useState({});
  const [quizType, setQuizType] = useState('silhouette');
  const [showQuizSetup, setShowQuizSetup] = useState(false);
  const [selectedGens, setSelectedGens] = useState(new Set());
  const [pendingQuizType, setPendingQuizType] = useState('silhouette');
  const wsRef = useRef(null);
  const msgsRef = useRef(null);
  const typingTimers = useRef({});
  const typingDebounce = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectCount = useRef(0);
  const closingRef = useRef(false);
  const [mentionMap, setMentionMap] = useState(null);

  useEffect(() => {
    fetch('/api/pokedex').then(r => r.json()).then(data => {
      const map = {};
      for (const p of data) { map[p.ko] = p.dex; map[p.en.toLowerCase()] = p.dex; }
      setMentionMap(map);
    }).catch(() => {});
  }, []);

  const parseText = useCallback((text) => {
    if (!mentionMap) return esc(text);
    return text.split(/(@[가-힣a-zA-Z0-9]+)/g).map(part => {
      if (part.startsWith('@')) {
        const name = part.slice(1);
        const dex = mentionMap[name] ?? mentionMap[name.toLowerCase()];
        if (dex) {
          const spr = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${dex}.png`;
          return `<span class="pm-mention" data-dex="${dex}"><img src="${spr}" onerror="this.style.display='none'">${esc(name)}</span>`;
        }
      }
      return esc(part);
    }).join('');
  }, [mentionMap]);

  const scrollBottom = () => { if (msgsRef.current) msgsRef.current.scrollTop = msgsRef.current.scrollHeight; };

  const addMsg = useCallback((msg) => {
    const isMe = msg.nick === nick;
    setMsgs(prev => [...prev, { type: 'msg', isMe, nick: msg.nick, html: '', text: msg.text, ts: msg.ts }]);
  }, [nick]);

  const addNotice = useCallback((text) => {
    setMsgs(prev => [...prev, { type: 'notice', text }]);
  }, []);

  const connect = useCallback((rId, rName) => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/room/${rId}?nick=${encodeURIComponent(nick)}`);
    wsRef.current = ws;

    ws.onopen = () => { reconnectCount.current = 0; setSendDisabled(false); };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'init') {
          for (const m of (msg.messages || [])) addMsg(m);
          setCount(msg.count || 0);
          setTimeout(scrollBottom, 50);
        } else if (msg.type === 'message') {
          addMsg(msg); setTimeout(scrollBottom, 30);
        } else if (msg.type === 'notice') {
          addNotice(msg.text);
          if (msg.count !== undefined) setCount(msg.count);
          setTimeout(scrollBottom, 30);
        } else if (msg.type === 'typing') {
          clearTimeout(typingTimers.current[msg.nick]);
          if (msg.is_typing) {
            typingTimers.current[msg.nick] = setTimeout(() => {
              delete typingTimers.current[msg.nick];
              setTypingText(Object.keys(typingTimers.current).map(n => `${n}님 입력 중`).join(', '));
            }, 3000);
          } else {
            delete typingTimers.current[msg.nick];
          }
          setTypingText(Object.keys(typingTimers.current).map(n => `${n}님 입력 중`).join(', '));
        } else if (msg.type === 'quiz_started') {
          setQuizActive(true);
          setShowQuizSetup(false);
          setQuizScores({});
          setQuizType(msg.quiz_type || 'silhouette');
        } else if (msg.type === 'quiz_question') {
          setQuizScores(msg.scores || {});
          const spr = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${msg.dex}.png`;
          setMsgs(prev => [...prev, {
            type: 'quiz_question', qnum: msg.question_num, spr, hints: [], answered: null,
            quizType: msg.quiz_type || 'silhouette',
            chosung: msg.chosung,
            nameKo: msg.name_ko,
            nameEn: msg.name_en,
          }]);
          setTimeout(scrollBottom, 30);
        } else if (msg.type === 'quiz_hint') {
          setMsgs(prev => {
            const a = [...prev];
            const last = a.findLast(m => m.type === 'quiz_question');
            if (last) last.hints = [...last.hints, `💡 힌트 ${msg.hint_num}: ${msg.hint}`];
            return a;
          });
          setTimeout(scrollBottom, 30);
        } else if (msg.type === 'quiz_correct') {
          setQuizScores(msg.scores || {});
          setMsgs(prev => {
            const a = [...prev];
            const last = a.findLast(m => m.type === 'quiz_question');
            if (last) last.answered = { correct: true, nick: msg.nick, answer: msg.answer };
            return a;
          });
          setTimeout(scrollBottom, 30);
        } else if (msg.type === 'quiz_skip') {
          setQuizScores(msg.scores || {});
          setMsgs(prev => {
            const a = [...prev];
            const last = a.findLast(m => m.type === 'quiz_question');
            if (last) last.answered = { correct: false, answer: msg.answer };
            return a;
          });
          setTimeout(scrollBottom, 30);
        } else if (msg.type === 'quiz_end') {
          setQuizActive(false);
          setQuizScores(msg.scores || {});
          const winText = msg.winner ? `🏆 우승자: ${msg.winner}` : '무승부';
          addNotice(`퀴즈 종료! ${winText}`);
          setTimeout(() => setQuizScores({}), 8000);
          setTimeout(scrollBottom, 30);
        }
      } catch (_) {}
    };
    ws.onclose = (ev) => {
      setSendDisabled(true);
      if (ev.code === 4003) addNotice('🔒 정원이 초과된 방입니다.');
      else if (ev.code === 4004) addNotice('방이 더 이상 존재하지 않습니다.');
      else if (closingRef.current) return;
      else {
        if (reconnectCount.current >= 5) { addNotice('재연결에 실패했습니다.'); setTimeout(onLeave, 2500); return; }
        reconnectCount.current++;
        const delay = Math.min(2000 * reconnectCount.current, 10000);
        addNotice(`⏳ 연결이 끊겼습니다. 재연결 중... (${reconnectCount.current}/5)`);
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(() => connect(rId, rName), delay);
      }
    };
    ws.onerror = () => ws.close();
  }, [nick, addMsg, addNotice, onLeave]);

  useEffect(() => {
    closingRef.current = false;
    connect(roomId, roomName);
    return () => {
      closingRef.current = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [roomId, roomName, connect]);

  const sendMsg = () => {
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== 1) return;
    clearTimeout(typingDebounce.current);
    wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: false }));
    wsRef.current.send(JSON.stringify({ type: 'message', text }));
    setInput('');
  };

  const onInputChange = (val) => {
    setInput(val);
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: true }));
      clearTimeout(typingDebounce.current);
      typingDebounce.current = setTimeout(() => wsRef.current?.readyState === 1 && wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: false })), 2500);
    }
  };

  const toggleQuiz = () => {
    if (!wsRef.current || wsRef.current.readyState !== 1) return;
    if (quizActive) {
      wsRef.current.send(JSON.stringify({ type: 'quiz_stop' }));
    } else {
      setShowQuizSetup(v => !v);
    }
  };

  const startQuiz = () => {
    if (!wsRef.current || wsRef.current.readyState !== 1) return;
    wsRef.current.send(JSON.stringify({ type: 'quiz_start', gens: selectedGens.size ? [...selectedGens] : [], quiz_type: pendingQuizType }));
    setShowQuizSetup(false);
  };

  const toggleGen = (g) => setSelectedGens(prev => {
    const n = new Set(prev);
    n.has(g) ? n.delete(g) : n.add(g);
    return n;
  });

  const handleMsgClick = (e) => {
    const dex = e.target.closest('[data-dex]')?.dataset.dex;
    if (dex) onOpenPokemon(+dex);
  };

  return (
    <div id="cm-room-screen" className="cm-screen" style={{ display:'flex', flexDirection:'column' }}>
      <div id="cm-room-header">
        <button id="cm-back-btn" onClick={onLeave}>←</button>
        <div id="cm-room-title">{roomName}</div>
        <div id="cm-room-count-badge">{count}/10명</div>
        <button
          id="cm-quiz-btn"
          className={quizActive ? 'active' : ''}
          onClick={toggleQuiz}
        >🎮 퀴즈{quizActive ? ' 중지' : ''}</button>
      </div>

      {Object.keys(quizScores).length > 0 && (
        <div id="cm-quiz-bar" className="visible">
          {Object.entries(quizScores).sort((a,b) => b[1]-a[1]).map(([n, s]) => (
            <span key={n} className={`cm-quiz-score${s >= 10 ? ' leader' : ''}`}>{n}: {s}</span>
          ))}
        </div>
      )}

      {showQuizSetup && (
        <div id="cm-quiz-setup" style={{ display:'flex' }}>
          <div style={{ fontSize:'0.78rem', color:'#94a3b8', fontWeight:600 }}>퀴즈 종류</div>
          <div className="cm-quiz-type-row">
            {[
              { id:'silhouette', label:'🖼️ 실루엣', desc:'이미지 보고 이름 맞추기' },
              { id:'chosung',    label:'🔤 초성',   desc:'초성 보고 이름 맞추기' },
              { id:'type',       label:'⚡ 타입',   desc:'포켓몬 보고 타입 맞추기' },
            ].map(({ id, label, desc }) => (
              <button
                key={id}
                className={`cm-quiz-type-btn${pendingQuizType === id ? ' selected' : ''}`}
                onClick={() => setPendingQuizType(id)}
              >{label}<br/><span style={{ fontSize:'0.65rem', opacity:0.75, fontWeight:400 }}>{desc}</span></button>
            ))}
          </div>
          <div style={{ fontSize:'0.78rem', color:'#64748b' }}>세대 선택 (선택 안 하면 전체)</div>
          <div className="cm-quiz-gen-row">
            {[1,2,3,4,5,6,7,8,9].map(g => (
              <button key={g} className={`cm-gen-btn${selectedGens.has(g)?' selected':''}`} onClick={() => toggleGen(g)}>{g}세대</button>
            ))}
          </div>
          <button id="cm-quiz-start-confirm" onClick={startQuiz}>퀴즈 시작!</button>
        </div>
      )}

      <div id="cm-msgs" ref={msgsRef} onClick={handleMsgClick}>
        {msgs.map((m, i) => {
          if (m.type === 'notice') return <div key={i} className="cm-notice">{m.text}</div>;
          if (m.type === 'quiz_question') {
            const revealed = !!m.answered;
            const qt = m.quizType || 'silhouette';
            return (
              <div key={i} className="cm-quiz-block">
                <div className="cm-quiz-qnum">❓ Q{m.qnum}</div>
                {qt === 'silhouette' && (
                  <img className={`cm-quiz-silhouette${revealed ? ' revealed' : ''}`} src={m.spr} alt="?" />
                )}
                {qt === 'chosung' && (
                  <div className={`cm-quiz-chosung${revealed ? ' revealed' : ''}`}>{m.chosung}</div>
                )}
                {qt === 'type' && (
                  <div className="cm-quiz-type-block">
                    <div className="cm-quiz-type-name">{m.nameKo} <span style={{ color:'#64748b', fontSize:'0.8em' }}>({m.nameEn})</span></div>
                    <img className="cm-quiz-type-sprite" src={m.spr} alt={m.nameKo} />
                    <div className="cm-quiz-type-label">⚡ 이 포켓몬의 타입은?</div>
                  </div>
                )}
                <div className="cm-quiz-hints-area">
                  {m.hints.map((h, hi) => <div key={hi} className="cm-quiz-hint-item">{h}</div>)}
                  {m.answered && (
                    m.answered.correct
                      ? <div className="cm-quiz-answer correct">🎉 <strong>{m.answered.nick}</strong>님 정답! <strong>{m.answered.answer}</strong> (+1점)</div>
                      : <div className="cm-quiz-answer" style={{ background:'#1c1010', border:'1px solid #7f1d1d', color:'#f87171', borderRadius:8, padding:'4px 8px', marginTop:4 }}>😅 아무도 못 맞췄어요! 정답: <strong>{m.answered.answer}</strong></div>
                  )}
                </div>
              </div>
            );
          }
          return (
            <div key={i} className={`cm-msg ${m.isMe ? 'mine' : 'other'}`}>
              {!m.isMe && <div className="cm-nick">{m.nick}</div>}
              <div className="cm-bubble" dangerouslySetInnerHTML={{ __html: parseText(m.text) }} />
              <div className="cm-time">{m.ts || ''}</div>
            </div>
          );
        })}
      </div>

      <div id="cm-typing-bar">{typingText}</div>
      <div id="cm-input-bar">
        <input
          id="cm-input"
          placeholder="메시지 입력..."
          value={input}
          onChange={e => onInputChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMsg()}
        />
        <button id="cm-send" onClick={sendMsg} disabled={sendDisabled}>↑</button>
      </div>
    </div>
  );
}

// ── 캐치마인드 로비 ──────────────────────────────────────────────────
const DIFF_LABEL = { easy: '🌱 쉬움', normal: '⚔️ 보통', hard: '🔥 어려움' };

function CatchmindLobbyScreen({ nick, onJoin, onBack }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDiff, setShowDiff] = useState(false);

  const loadRooms = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetch('/api/catchmind/rooms').then(r => r.json());
      setRooms(data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadRooms(); }, [loadRooms]);

  const createRoom = async (difficulty) => {
    setShowDiff(false);
    try {
      const r = await fetch('/api/catchmind/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nick, difficulty }),
      }).then(res => res.json());
      onJoin(r.room_id);
    } catch { alert('방 만들기 실패'); }
  };

  return (
    <div id="cm-cm-lobby" className="cm-screen" style={{ display:'flex', flexDirection:'column' }}>
      <div id="cm-cm-lobby-header">
        <button onClick={onBack}>← 채팅</button>
        <span>🎨 캐치마인드</span>
        <button onClick={loadRooms} title="새로고침">🔄</button>
        <button className="cm-create-btn2" onClick={() => setShowDiff(v => !v)}>+ 방 만들기</button>
      </div>
      {showDiff && (
        <div id="cm-diff-picker" style={{ display:'flex', flexDirection:'column' }}>
          <div className="diff-title">난이도를 선택하세요</div>
          <div className="diff-row">
            <button className="diff-btn easy" onClick={() => createRoom('easy')}>🌱 쉬움<br/><small>1세대 (151마리)</small></button>
            <button className="diff-btn normal" onClick={() => createRoom('normal')}>⚔️ 보통<br/><small>1~4세대 (493마리)</small></button>
            <button className="diff-btn hard" onClick={() => createRoom('hard')}>🔥 어려움<br/><small>전체 (1000마리+)</small></button>
          </div>
        </div>
      )}
      <div id="cm-cm-room-list">
        {loading && <div style={{ textAlign:'center', padding:'30px', color:'#64748b', fontSize:'0.82rem' }}>불러오는 중...</div>}
        {!loading && !rooms.length && (
          <div style={{ textAlign:'center', padding:'40px 20px', color:'#64748b', fontSize:'0.82rem' }}>
            진행 중인 방이 없어요<br/>방을 만들어보세요!
          </div>
        )}
        {rooms.map(r => (
          <div key={r.room_id} className="cm-cm-room-card" onClick={() => onJoin(r.room_id)}>
            <div className="cm-cm-room-info">
              <div className="cm-cm-room-creator">
                {r.creator}의 방 <span className={`diff-badge ${r.difficulty || 'normal'}`}>{DIFF_LABEL[r.difficulty] || '⚔️ 보통'}</span>
              </div>
              <div className="cm-cm-room-meta">{r.players}명 참가 중</div>
            </div>
            <span className={`cm-cm-room-badge ${r.status === 'waiting' ? 'cm-cm-badge-wait' : 'cm-cm-badge-play'}`}>
              {r.status === 'waiting' ? '대기 중' : '게임 중'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 캐치마인드 게임 ──────────────────────────────────────────────────
const CM_COLORS = ['#000000','#ef4444','#f97316','#eab308','#22c55e','#3b82f6','#8b5cf6','#ffffff'];
const CM_SIZES  = [4, 10, 22];

function CatchmindGameScreen({ nick, roomId, onLeave }) {
  const canvasRef  = useRef(null);
  const wsRef      = useRef(null);
  const chatRef    = useRef(null);
  const drawingRef = useRef(false);
  const lastPos    = useRef({ x:0, y:0 });
  const isDrawer   = useRef(false);
  const colorRef   = useRef('#000000');
  const sizeRef    = useRef(4);
  const eraserRef  = useRef(false);

  const [players, setPlayers]       = useState([]);
  const [timer, setTimer]           = useState('—');
  const [timerUrgent, setTimerUrgent] = useState(false);
  const [showTools, setShowTools]   = useState(false);
  const [wordBox, setWordBox]       = useState(null);
  const [chatMsgs, setChatMsgs]     = useState([]);
  const [guessInput, setGuessInput] = useState('');
  const [guessDisabled, setGuessDisabled] = useState(false);
  const [overlay, setOverlay]       = useState(null);
  const [color, setColor]           = useState('#000000');
  const [brushSize, setBrushSize]   = useState(4);
  const [eraser, setEraser]         = useState(false);

  // 상태 → ref 동기화 (캔버스 이벤트 핸들러에서 사용)
  useEffect(() => { colorRef.current  = color;      }, [color]);
  useEffect(() => { sizeRef.current   = brushSize;  }, [brushSize]);
  useEffect(() => { eraserRef.current = eraser;     }, [eraser]);

  const clearLocal = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    if (!c.width || c.width < 10) { const s = c.offsetWidth || 200; c.width = s; c.height = s; }
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, c.width, c.height);
  }, []);

  const renderStroke = useCallback((c, d) => {
    const ctx = c.getContext('2d');
    const w = c.width, h = c.height;
    ctx.beginPath();
    ctx.lineWidth = d.s;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = d.c;
    if (d.lx != null) {
      ctx.moveTo(d.lx * w, d.ly * h);
      ctx.lineTo(d.x  * w, d.y  * h);
      ctx.stroke();
    } else {
      ctx.arc(d.x * w, d.y * h, d.s / 2, 0, Math.PI * 2);
      ctx.fillStyle = d.c;
      ctx.fill();
    }
  }, []);

  const addChat = useCallback((type, a, b) => {
    setChatMsgs(prev => [...prev, { type, a, b }]);
    setTimeout(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, 30);
  }, []);

  const handleMsg = useCallback((msg) => {
    if (msg.type === 'joined') {
      setPlayers((msg.players || []).map(p => ({ ...p, isDrawer: false })));
      if (msg.status === 'waiting')
        setOverlay({ title:'⏳ 상대방 기다리는 중...', sub:'1분 내 참여자가 없으면 방이 닫혀요', scores:null, btn:null });
    } else if (msg.type === 'player_join') {
      addChat('notice', `${msg.name}님이 입장했어요 (${msg.count}명)`);
      setOverlay(null);
    } else if (msg.type === 'player_leave') {
      addChat('notice', `${msg.name}님이 퇴장했어요 (${msg.count}명)`);
    } else if (msg.type === 'round_start') {
      isDrawer.current = !!msg.word;
      setOverlay(null);
      setShowTools(!!msg.word);
      setWordBox(msg.word ? `✏️ 그릴 포켓몬: ${msg.word}` : null);
      setGuessDisabled(!!msg.word);
      clearLocal();
      setPlayers(prev => prev.map(p => ({ ...p, isDrawer: p.name === msg.drawer })));
      addChat('notice', `✏️ ${msg.drawer}님이 그림을 그립니다!`);
    } else if (msg.type === 'draw') {
      const c = canvasRef.current;
      if (c) renderStroke(c, msg.d);
    } else if (msg.type === 'clear') {
      clearLocal();
    } else if (msg.type === 'timer') {
      setTimer(msg.t + 's');
      setTimerUrgent(msg.t <= 10);
    } else if (msg.type === 'guess') {
      if (msg.correct) addChat('correct', `🎉 ${msg.name} 정답! (${msg.text})`);
      else             addChat('msg', msg.name, msg.text);
    } else if (msg.type === 'round_end') {
      const winText = msg.winner ? `정답자: ${msg.winner}` : '시간 초과!';
      setOverlay({ title:'🏁 라운드 종료', sub:`정답: ${msg.word}\n${winText}`, scores:msg.scores, btn:null });
      setPlayers(prev => prev.map(p => ({ ...p, score: msg.scores?.[p.name] ?? p.score })));
    } else if (msg.type === 'game_over') {
      setOverlay({ title:'🏆 게임 종료!', sub:`🥇 ${msg.winner} 승리!\n정답: ${msg.word}`, scores:msg.scores, btn:'다시 하기' });
      setPlayers(prev => prev.map(p => ({ ...p, score: msg.scores?.[p.name] ?? p.score })));
    } else if (msg.type === 'room_closed') {
      setOverlay({ title:'방이 닫혔어요', sub:'1분 내 참여자가 없어 방이 닫혔습니다', scores:null, btn:'나가기' });
    }
  }, [addChat, clearLocal, renderStroke]);

  // WebSocket 연결
  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/catchmind/${roomId}?nick=${encodeURIComponent(nick)}`);
    wsRef.current = ws;
    ws.onopen = () => {
      const c = canvasRef.current;
      if (c) requestAnimationFrame(() => {
        const s = c.offsetWidth || 200;
        c.width = s; c.height = s;
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, s, s);
      });
    };
    ws.onmessage = (e) => { try { handleMsg(JSON.parse(e.data)); } catch {} };
    ws.onclose = (e) => {
      if      (e.code === 4004) { addChat('notice','방을 찾을 수 없어요.'); setTimeout(onLeave, 1500); }
      else if (e.code === 4003) { addChat('notice','방이 꽉 찼어요.');      setTimeout(onLeave, 1500); }
      else                      { addChat('notice','연결이 끊어졌어요.'); }
    };
    ws.onerror = () => ws.close();
    return () => ws.close();
  }, [roomId, nick, handleMsg, addChat, onLeave]);

  // 캔버스 드로잉 이벤트
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const getPos = (e) => {
      const r = c.getBoundingClientRect();
      const src = e.touches ? e.touches[0] : e;
      return [(src.clientX - r.left) / r.width, (src.clientY - r.top) / r.height];
    };
    const emitDraw = (x, y, lx, ly) => {
      const d = { x, y, lx, ly, c: eraserRef.current ? '#ffffff' : colorRef.current, s: eraserRef.current ? sizeRef.current * 2.5 : sizeRef.current };
      renderStroke(c, d);
      if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify({ type:'draw', d }));
    };
    const start = (e) => {
      if (!isDrawer.current) return;
      e.preventDefault();
      drawingRef.current = true;
      const [x, y] = getPos(e);
      lastPos.current = { x, y };
      emitDraw(x, y, null, null);
    };
    const move = (e) => {
      if (!drawingRef.current || !isDrawer.current) return;
      e.preventDefault();
      const [x, y] = getPos(e);
      emitDraw(x, y, lastPos.current.x, lastPos.current.y);
      lastPos.current = { x, y };
    };
    const end = () => { drawingRef.current = false; };
    c.addEventListener('mousedown', start);
    c.addEventListener('mousemove', move);
    c.addEventListener('mouseup', end);
    c.addEventListener('mouseleave', end);
    c.addEventListener('touchstart', start, { passive:false });
    c.addEventListener('touchmove',  move,  { passive:false });
    c.addEventListener('touchend',   end);
    return () => {
      c.removeEventListener('mousedown', start);
      c.removeEventListener('mousemove', move);
      c.removeEventListener('mouseup', end);
      c.removeEventListener('mouseleave', end);
      c.removeEventListener('touchstart', start);
      c.removeEventListener('touchmove', move);
      c.removeEventListener('touchend', end);
    };
  }, [renderStroke]);

  const sendClear = () => {
    clearLocal();
    if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify({ type:'clear' }));
  };

  const sendGuess = () => {
    const text = guessInput.trim();
    if (!text || wsRef.current?.readyState !== 1) return;
    wsRef.current.send(JSON.stringify({ type:'guess', text }));
    setGuessInput('');
  };

  const handleOverlayBtn = (btn) => {
    if (btn === '나가기') { onLeave(); }
    else {
      if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify({ type:'restart' }));
      setOverlay(null);
    }
  };

  const pickColor = (c) => { setColor(c); setEraser(false); };
  const pickSize  = (s) => { setBrushSize(s); setEraser(false); };

  return (
    <div id="cm-cm-game" className="cm-screen" style={{ display:'flex', flexDirection:'column' }}>
      <div id="cm-game-header">
        <button className="cm-back" onClick={onLeave}>←</button>
        <div id="cm-players-bar">
          {players.map((p, i) => (
            <div key={i} className={`cm-player-chip${p.isDrawer ? ' drawer' : ''}`}>
              {p.name} <span className="score">{p.score ?? 0}</span>
            </div>
          ))}
        </div>
        <div id="cm-timer" className={timerUrgent ? 'urgent' : ''}>{timer}</div>
      </div>

      <div id="cm-canvas-wrap" style={{ position:'relative' }}>
        <canvas id="cm-canvas" ref={canvasRef} />
        {overlay && (
          <div className="cm-overlay" style={{ display:'flex' }}>
            <div className="cm-overlay-title">{overlay.title}</div>
            <div className="cm-overlay-sub" style={{ whiteSpace:'pre-line' }}>{overlay.sub}</div>
            {overlay.scores && (
              <div className="cm-overlay-scores">
                {Object.entries(overlay.scores).sort((a,b) => b[1]-a[1]).map(([name, score]) => (
                  <div key={name} className="cm-score-row">
                    <span>{name}</span>
                    <span className="score" style={{ color:'#60a5fa', fontWeight:700 }}>{score}점</span>
                  </div>
                ))}
              </div>
            )}
            {overlay.btn && <button className="cm-overlay-btn" onClick={() => handleOverlayBtn(overlay.btn)}>{overlay.btn}</button>}
          </div>
        )}
      </div>

      {showTools && (
        <div id="cm-tools" className="visible">
          {CM_COLORS.map((c) => (
            <div
              key={c}
              className={`cm-color-btn${color === c && !eraser ? ' active' : ''}`}
              style={{ background:c, ...(c==='#ffffff' ? { border:'2px solid #334155' } : {}) }}
              onClick={() => pickColor(c)}
            />
          ))}
          <span style={{ width:1, background:'#334155', alignSelf:'stretch', margin:'0 2px' }} />
          {CM_SIZES.map((s, i) => (
            <button key={s} className={`cm-size-btn${brushSize===s && !eraser ? ' active' : ''}`} onClick={() => pickSize(s)}>
              {['S','M','L'][i]}
            </button>
          ))}
          <button id="cm-eraser-btn" className={eraser ? 'active' : ''} onClick={() => setEraser(v => !v)}>지우개</button>
          <button id="cm-clear-btn" onClick={sendClear}>전체 지우기</button>
        </div>
      )}

      {wordBox && <div id="cm-word-box" className="visible">{wordBox}</div>}

      <div id="cm-chat" ref={chatRef}>
        {chatMsgs.map((m, i) => {
          if (m.type === 'notice')  return <div key={i} className="cm-chat-msg notice">{m.a}</div>;
          if (m.type === 'correct') return <div key={i} className="cm-chat-msg correct">{m.a}</div>;
          return <div key={i} className="cm-chat-msg"><span className="nm">{m.a}</span> {m.b}</div>;
        })}
      </div>

      <div id="cm-guess-bar">
        <input
          id="cm-guess-input"
          placeholder={guessDisabled ? '그림을 그려주세요!' : '포켓몬 이름 맞춰보세요...'}
          value={guessInput}
          onChange={e => setGuessInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendGuess()}
          disabled={guessDisabled}
        />
        <button id="cm-guess-send" onClick={sendGuess} disabled={guessDisabled}>↑</button>
      </div>
    </div>
  );
}

// ── 배틀 로비 ─────────────────────────────────────────────────────────
function BattleLobbyScreen({ nick, onJoin, onBack }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadRooms = useCallback(async () => {
    try {
      const data = await fetch('/api/battle/rooms').then(r => r.json());
      setRooms(data);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    loadRooms();
    const t = setInterval(loadRooms, 5000);
    return () => clearInterval(t);
  }, [loadRooms]);

  return (
    <div className="cm-screen" style={{ display:'flex', flexDirection:'column' }}>
      <div id="cm-cm-lobby-header">
        <button onClick={onBack}>← 채팅</button>
        <span>⚔️ 포켓몬 배틀</span>
        <button onClick={loadRooms} title="새로고침">🔄</button>
        <button className="cm-create-btn2" onClick={() => onJoin('new')}>+ 방 만들기</button>
      </div>
      <div style={{ padding:'10px 14px', background:'#0d1a2d', borderBottom:'1px solid #1e293b', fontSize:'0.74rem', color:'#64748b', flexShrink:0 }}>
        랜덤 포켓몬 3마리로 턴제 배틀! 방 만들고 친구에게 링크를 공유하세요.
      </div>
      <div id="cm-cm-room-list">
        {loading && <div style={{ textAlign:'center', padding:'30px', color:'#64748b', fontSize:'0.82rem' }}>불러오는 중...</div>}
        {!loading && !rooms.length && (
          <div style={{ textAlign:'center', padding:'40px 20px', color:'#64748b', fontSize:'0.82rem' }}>
            대기 중인 배틀이 없어요<br/>방을 만들어 도전자를 기다리세요! ⚔️
          </div>
        )}
        {rooms.map(r => (
          <div key={r.id} className="cm-cm-room-card" onClick={() => onJoin(r.id)}>
            <div className="cm-cm-room-info">
              <div className="cm-cm-room-creator">⚔️ {r.players[0] || '???'}의 배틀</div>
              <div className="cm-cm-room-meta">도전자 대기 중</div>
            </div>
            <span className="cm-cm-room-badge cm-cm-badge-wait">도전하기</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 배틀 게임 ─────────────────────────────────────────────────────────
const TYPE_COLOR = {
  normal:'#a8a878',fire:'#f08030',water:'#6890f0',electric:'#f8d030',
  grass:'#78c850',ice:'#98d8d8',fighting:'#c03028',poison:'#a040a0',
  ground:'#e0c068',flying:'#a890f0',psychic:'#f85888',bug:'#a8b820',
  rock:'#b8a038',ghost:'#705898',dragon:'#7038f8',dark:'#705848',
  steel:'#b8b8d0',fairy:'#ee99ac',
};

function BattleScreen({ nick, roomId, onLeave }) {
  const [phase, setPhase] = useState('connecting');
  const [battleId, setBattleId] = useState(null);
  const [me,  setMe]  = useState(null);
  const [opp, setOpp] = useState(null);
  const [log, setLog] = useState([]);
  const [myDone, setMyDone] = useState(false);
  const [oppReady, setOppReady] = useState(false);
  const [winner, setWinner] = useState(null);
  const [myHit, setMyHit] = useState(false);
  const [oppHit, setOppHit] = useState(false);
  const wsRef  = useRef(null);
  const logRef = useRef(null);
  const phaseRef = useRef('connecting');

  useEffect(() => { phaseRef.current = phase; }, [phase]);

  const addLog = useCallback((lines) => {
    setLog(prev => [...prev, ...(Array.isArray(lines) ? lines : [lines])]);
    setTimeout(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, 30);
  }, []);

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/battle/${roomId}?nick=${encodeURIComponent(nick)}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'joined') {
          setBattleId(msg.battle_id);
        } else if (msg.type === 'waiting') {
          setPhase('waiting');
        } else if (msg.type === 'battle_start') {
          setMe({ ...msg.me });
          setOpp({ ...msg.opp });
          setPhase('battling');
          setMyDone(false); setOppReady(false);
          addLog(`⚔️ ${msg.opp.nick}님과 배틀 시작! 기술을 선택하세요.`);
        } else if (msg.type === 'opp_ready') {
          setOppReady(true);
        } else if (msg.type === 'turn_result') {
          const totalHp = team => team.reduce((s, p) => s + p.hp, 0);
          setMe(prev => {
            if (prev && totalHp(msg.me.team) < totalHp(prev.team)) {
              setMyHit(true); setTimeout(() => setMyHit(false), 380);
            }
            return { ...msg.me };
          });
          setOpp(prev => {
            if (prev && totalHp(msg.opp.team) < totalHp(prev.team)) {
              setOppHit(true); setTimeout(() => setOppHit(false), 380);
            }
            return { ...msg.opp };
          });
          addLog(msg.log || []);
          setMyDone(false); setOppReady(false);
        } else if (msg.type === 'battle_end') {
          setWinner(msg.winner);
          setPhase('ended');
          addLog(msg.disconnected ? '상대방이 도망쳤어요!' : `🏆 ${msg.winner}님의 승리!`);
        } else if (msg.type === 'error') {
          addLog(`❌ ${msg.msg}`);
          setPhase('ended');
        }
      } catch {}
    };
    ws.onclose = () => {
      if (phaseRef.current !== 'ended') {
        setPhase('ended');
        addLog('연결이 끊어졌어요.');
      }
    };
    return () => ws.close();
  }, [roomId, nick, addLog]);

  const sendMove = (idx) => {
    if (myDone || !wsRef.current || wsRef.current.readyState !== 1) return;
    wsRef.current.send(JSON.stringify({ type: 'move', idx }));
    setMyDone(true);
  };

  const handleLeave = () => {
    if (wsRef.current && wsRef.current.readyState === 1) {
      wsRef.current.send(JSON.stringify({ type: 'forfeit' }));
    }
    onLeave();
  };

  const hpPct = (hp, max) => Math.max(0, Math.min(100, (hp / max) * 100));
  const hpColor = (hp, max) => {
    const p = hp / max;
    return p > 0.5 ? '#22c55e' : p > 0.25 ? '#f59e0b' : '#ef4444';
  };

  const myPm  = me?.team?.[me?.active];
  const oppPm = opp?.team?.[opp?.active];

  return (
    <div className="cm-screen" style={{ display:'flex', flexDirection:'column', background:'#070c14' }}>
      {/* 헤더 */}
      <div id="cm-game-header" style={{ borderBottom:'1px solid #1e293b' }}>
        <button className="cm-back" onClick={handleLeave}>← 도망</button>
        <div style={{ flex:1, textAlign:'center', fontSize:'0.78rem', color:'#64748b' }}>
          {phase === 'waiting'   ? '⏳ 도전자 대기 중...' :
           phase === 'battling'  ? `⚔️ ${opp?.nick} 님과 배틀 중` :
           phase === 'ended'     ? '🏁 배틀 종료' : '연결 중...'}
        </div>
      </div>

      {/* 대기 화면 */}
      {phase === 'waiting' && (
        <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:14, padding:24, textAlign:'center' }}>
          <div style={{ fontSize:'3rem' }}>⚔️</div>
          <div style={{ color:'#e2e8f0', fontWeight:700 }}>배틀방 개설 완료!</div>
          <div style={{ color:'#64748b', fontSize:'0.8rem', lineHeight:1.6 }}>
            친구가 배틀 로비에서<br/>이 방을 찾아 입장하면<br/>자동으로 시작돼요
          </div>
          {battleId && <div style={{ background:'#1e293b', borderRadius:10, padding:'8px 16px', color:'#60a5fa', fontSize:'0.85rem', letterSpacing:'0.1em', fontWeight:700 }}>방 ID: {battleId}</div>}
        </div>
      )}

      {/* 배틀 + 종료 화면 */}
      {(phase === 'battling' || phase === 'ended') && me && opp && (<>

        {/* 상대 팀 HP 도트 */}
        <div className="bt-team-bar">
          <span className="bt-team-name">{opp.nick}</span>
          {opp.team.map((p, i) => (
            <div key={i} className={`bt-team-dot${i === opp.active ? ' active' : ''}${p.hp <= 0 ? ' fainted' : ''}`} />
          ))}
        </div>

        {/* 배틀 필드 */}
        <div className="bt-field">
          {/* 상대 포켓몬 */}
          <div className="bt-opp-side">
            <div className={oppHit ? 'bt-hit-wrap bt-shake' : 'bt-hit-wrap'}>
              <img className="bt-sprite"
                src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${oppPm?.dex}.png`}
                alt={oppPm?.ko} onError={e => e.target.style.opacity='0.2'} />
            </div>
            <div className="bt-info-wrap">
              <div className="bt-pm-name">{oppPm?.ko}</div>
              <div style={{ display:'flex', gap:4, marginBottom:3 }}>
                {[oppPm?.t1, oppPm?.t2].filter(Boolean).map(t => (
                  <span key={t} style={{ background: TYPE_COLOR[t]||'#555', borderRadius:4, padding:'1px 6px', fontSize:'0.6rem', color:'#fff', fontWeight:700 }}>{t}</span>
                ))}
              </div>
              <div className="bt-hp-bar-outer">
                <div className="bt-hp-bar-inner" style={{ width:`${hpPct(oppPm?.hp||0, oppPm?.max_hp||1)}%`, background:hpColor(oppPm?.hp||0, oppPm?.max_hp||1) }} />
              </div>
              <span className="bt-hp-text">{oppPm?.hp} / {oppPm?.max_hp}</span>
            </div>
          </div>

          {/* 내 포켓몬 */}
          <div className="bt-my-side">
            <div className={myHit ? 'bt-hit-wrap bt-shake' : 'bt-hit-wrap'}>
              <img className="bt-sprite bt-back"
                src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/${myPm?.dex}.png`}
                alt={myPm?.ko} onError={e => { e.target.src=`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${myPm?.dex}.png`; }} />
            </div>
            <div className="bt-info-wrap">
              <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                <span className="bt-my-badge">나</span>
                <span className="bt-pm-name">{myPm?.ko}</span>
              </div>
              <div style={{ display:'flex', gap:4, marginBottom:3 }}>
                {[myPm?.t1, myPm?.t2].filter(Boolean).map(t => (
                  <span key={t} style={{ background: TYPE_COLOR[t]||'#555', borderRadius:4, padding:'1px 6px', fontSize:'0.6rem', color:'#fff', fontWeight:700 }}>{t}</span>
                ))}
              </div>
              <div className="bt-hp-bar-outer">
                <div className="bt-hp-bar-inner" style={{ width:`${hpPct(myPm?.hp||0, myPm?.max_hp||1)}%`, background:hpColor(myPm?.hp||0, myPm?.max_hp||1) }} />
              </div>
              <span className="bt-hp-text">{myPm?.hp} / {myPm?.max_hp}</span>
              <div className="bt-energy-row">
                <span style={{ fontSize:'0.6rem', color:'#f59e0b' }}>⚡</span>
                <div className="bt-energy-outer"><div className="bt-energy-inner" style={{ width:`${myPm?.energy||0}%` }} /></div>
                <span style={{ fontSize:'0.6rem', color:'#94a3b8' }}>{myPm?.energy||0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* 내 팀 HP 도트 */}
        <div className="bt-team-bar" style={{ borderTop:'1px solid #1e293b', justifyContent:'flex-end' }}>
          {me.team.map((p, i) => (
            <div key={i} className={`bt-team-dot${i === me.active ? ' active' : ''}${p.hp <= 0 ? ' fainted' : ''}`} />
          ))}
          <span className="bt-team-name">{nick}</span>
        </div>

        {/* 기술 선택 */}
        {phase === 'battling' && (
          <div className="bt-moves">
            {myDone ? (
              <div className="bt-waiting-msg">
                {oppReady ? '⚡ 결과 계산 중...' : '✅ 기술 선택 완료! 상대방 대기 중...'}
              </div>
            ) : (
              <div className="bt-move-grid">
                {(myPm?.moves || []).map((m, i) => {
                  const canUse = m.fast || (myPm?.energy || 0) >= m.cost;
                  return (
                    <button key={i}
                      className={`bt-move-btn${m.fast ? ' fast' : ' charged'}${!canUse ? ' disabled' : ''}`}
                      onClick={() => canUse && sendMove(i)}
                    >
                      <span className="bt-move-name">{m.ko}</span>
                      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                        <span style={{ fontSize:'0.62rem', color: TYPE_COLOR[m.type]||'#94a3b8' }}>●{m.type}</span>
                        <span className="bt-move-power">💥{m.power}</span>
                        {!m.fast && <span className="bt-move-cost">⚡{m.cost}</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* 게임 종료 */}
        {phase === 'ended' && (
          <div className="bt-ended">
            <div style={{ fontSize:'2rem' }}>{winner === nick ? '🏆' : '💀'}</div>
            <div className="bt-ended-title">{winner === nick ? '승리!' : '패배...'}</div>
            <div className="bt-ended-sub">{winner}님의 승리</div>
            <button className="bt-ended-btn" onClick={onLeave}>로비로 돌아가기</button>
          </div>
        )}

        {/* 배틀 로그 */}
        <div className="bt-log" ref={logRef}>
          {log.map((l, i) => {
            const cls = l.includes('굉장했다') ? ' super' : l.includes('급소') ? ' crit' : l.includes('없었다') ? ' immune' : l.includes('별로') ? ' weak' : '';
            return <div key={i} className={`bt-log-line${cls}`}>{l}</div>;
          })}
        </div>
      </>)}
    </div>
  );
}

// ── 메인 ─────────────────────────────────────────────────────────────
export default function CommunityTab({ onOpenPokemon }) {
  const [nick,   setNick]   = useState(() => localStorage.getItem('cm_nick') || null);
  const [screen, setScreen] = useState('lobby');
  const [room,   setRoom]   = useState(null);
  const [cmRoom, setCmRoom] = useState(null);
  const [btRoom, setBtRoom] = useState(null);

  const enterLobby  = (n) => { setNick(n); setScreen('lobby'); };
  const joinRoom    = (id, name) => { setRoom({ id, name }); setScreen('room'); };
  const leaveRoom   = () => { setRoom(null); setScreen('lobby'); };
  const goCatchmind = () => setScreen('cm-lobby');
  const joinCmRoom  = (id) => { setCmRoom({ id }); setScreen('cm-game'); };
  const leaveCmRoom = () => { setCmRoom(null); setScreen('cm-lobby'); };
  const goBattle    = () => setScreen('bt-lobby');
  const joinBattle  = (id) => { setBtRoom({ id }); setScreen('bt-game'); };
  const leaveBattle = () => { setBtRoom(null); setScreen('bt-lobby'); };

  const changeNick = () => {
    const n = prompt('새 닉네임을 입력하세요 (최대 15자)', nick || '');
    if (!n?.trim()) return;
    const trimmed = n.trim().slice(0, 15);
    setNick(trimmed);
    localStorage.setItem('cm_nick', trimmed);
  };

  return (
    <div className="view" id="view-community">
      {!nick && <NickScreen onEnter={enterLobby} />}
      {nick && screen === 'lobby' && (
        <LobbyScreen nick={nick} onJoin={joinRoom} onChangeNick={changeNick} onCatchmind={goCatchmind} onBattle={goBattle} />
      )}
      {nick && screen === 'room' && room && (
        <RoomScreen nick={nick} roomId={room.id} roomName={room.name} onLeave={leaveRoom} onOpenPokemon={onOpenPokemon} />
      )}
      {nick && screen === 'cm-lobby' && (
        <CatchmindLobbyScreen nick={nick} onJoin={joinCmRoom} onBack={() => setScreen('lobby')} />
      )}
      {nick && screen === 'cm-game' && cmRoom && (
        <CatchmindGameScreen nick={nick} roomId={cmRoom.id} onLeave={leaveCmRoom} />
      )}
      {nick && screen === 'bt-lobby' && (
        <BattleLobbyScreen nick={nick} onJoin={joinBattle} onBack={() => setScreen('lobby')} />
      )}
      {nick && screen === 'bt-game' && btRoom && (
        <BattleScreen nick={nick} roomId={btRoom.id} onLeave={leaveBattle} />
      )}
    </div>
  );
}
