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
function LobbyScreen({ nick, onJoin, onChangeNick }) {
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
        <span style={{ fontWeight:600, fontSize:'0.88rem', color:'#e2e8f0' }}>채팅방 목록</span>
        <span id="cm-lobby-nick" style={{ fontSize:'0.78rem', color:'#94a3b8', cursor:'pointer', textDecoration:'underline dotted', marginLeft:8 }} onClick={onChangeNick}>
          👤 {nick}
        </span>
        <button id="cm-create-btn" onClick={createRoom} style={{ marginLeft:'auto' }}>+ 방 만들기</button>
        <button id="cm-lobby-refresh" onClick={loadRooms} title="새로고침">🔄</button>
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
  const [showQuizSetup, setShowQuizSetup] = useState(false);
  const [selectedGens, setSelectedGens] = useState(new Set());
  const wsRef = useRef(null);
  const msgsRef = useRef(null);
  const typingTimers = useRef({});
  const typingDebounce = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectCount = useRef(0);
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
        } else if (msg.type === 'quiz_question') {
          setQuizScores(msg.scores || {});
          const spr = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${msg.dex}.png`;
          setMsgs(prev => [...prev, { type: 'quiz_question', qnum: msg.question_num, spr, hints: [], answered: null }]);
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
    connect(roomId, roomName);
    return () => {
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
    wsRef.current.send(JSON.stringify({ type: 'quiz_start', gens: selectedGens.size ? [...selectedGens] : [] }));
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
            return (
              <div key={i} className="cm-quiz-block">
                <div className="cm-quiz-qnum">❓ Q{m.qnum}</div>
                <img className={`cm-quiz-silhouette${revealed?' revealed':''}`} src={m.spr} alt="?" />
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

export default function CommunityTab({ onOpenPokemon }) {
  const [nick, setNick] = useState(() => localStorage.getItem('cm_nick') || null);
  const [room, setRoom] = useState(null); // { id, name }

  const enterLobby = (n) => { setNick(n); setRoom(null); };
  const joinRoom = (id, name) => setRoom({ id, name });
  const leaveRoom = () => setRoom(null);
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
      {nick && !room && <LobbyScreen nick={nick} onJoin={joinRoom} onChangeNick={changeNick} />}
      {nick && room && (
        <RoomScreen
          nick={nick}
          roomId={room.id}
          roomName={room.name}
          onLeave={leaveRoom}
          onOpenPokemon={onOpenPokemon}
        />
      )}
    </div>
  );
}
