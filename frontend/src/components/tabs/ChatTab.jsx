import { useState, useRef, useEffect, useCallback } from 'react';
import { renderMd } from '../../utils/helpers';

const CHIPS = [
  '지금 레이드 보스 뭐야?',
  '커뮤니티 데이 포켓몬?',
  '슈퍼리그 최강은?',
  '뮤츠 레이드 카운터',
  '불꽃 그런트 공략',
  '10km 알 부화 목록',
  '날씨 부스트 타입',
  '이번 주 이벤트',
];

const GENS = [1,2,3,4,5,6,7,8,9];

function SoloQuiz({ onExit }) {
  const [dexList, setDexList] = useState([]);
  const [filterGen, setFilterGen] = useState(0);
  const [current, setCurrent] = useState(null);
  const [revealed, setRevealed] = useState(false);
  const [score, setScore] = useState(0);
  const [total, setTotal] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [hints, setHints] = useState([]);
  const [wrongFlash, setWrongFlash] = useState(false);
  const inputRef = useRef(null);
  const dexListRef = useRef([]);
  const filterGenRef = useRef(0);

  useEffect(() => {
    fetch('/api/pokedex').then(r => r.json()).then(data => {
      setDexList(data);
      dexListRef.current = data;
      pickNext(data, 0);
    });
  }, []);

  const pickNext = useCallback((list, gen) => {
    const pool = (list ?? dexListRef.current).filter(p => gen === 0 || p.gen === gen);
    if (!pool.length) return;
    const pm = pool[Math.floor(Math.random() * pool.length)];
    setCurrent(pm);
    setRevealed(false);
    setAnswer('');
    setResult(null);
    setHints([]);
    setTimeout(() => inputRef.current?.focus(), 80);
  }, []);

  const changeGen = (gen) => {
    setFilterGen(gen);
    filterGenRef.current = gen;
    pickNext(dexListRef.current, gen);
  };

  const handleAnswer = (e) => {
    if (e.key !== 'Enter' || !current || revealed) return;
    const val = answer.trim().toLowerCase();
    if (!val) return;
    const ko = current.ko.toLowerCase();
    const en = current.en.toLowerCase();
    if (val === ko || val === en) {
      setRevealed(true);
      setScore(s => s + 1);
      setTotal(t => t + 1);
      setResult('correct');
      setTimeout(() => pickNext(null, filterGenRef.current), 1600);
    } else {
      setWrongFlash(true);
      setTimeout(() => setWrongFlash(false), 400);
      if (hints.length === 0) {
        setHints([`글자수: ${current.ko.length}자`]);
      } else if (hints.length === 1) {
        setHints(h => [...h, `첫 글자: ${current.ko[0]}`]);
      }
    }
  };

  const handleSkip = () => {
    if (revealed) return;
    setRevealed(true);
    setTotal(t => t + 1);
    setResult('skip');
    setTimeout(() => pickNext(null, filterGenRef.current), 2000);
  };

  if (!current) return (
    <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>불러오는 중...</div>
  );

  const sprUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${current.dex}.png`;

  return (
    <div id="solo-quiz">
      <div id="solo-quiz-top">
        <div id="solo-quiz-gen-row">
          <button className={`sq-gen-btn${filterGen===0?' active':''}`} onClick={() => changeGen(0)}>전체</button>
          {GENS.map(g => (
            <button key={g} className={`sq-gen-btn${filterGen===g?' active':''}`} onClick={() => changeGen(g)}>{g}세대</button>
          ))}
        </div>
        <div id="solo-quiz-score-row">
          <span id="solo-quiz-score">{score} / {total}</span>
          <button id="solo-quiz-exit" onClick={onExit}>종료</button>
        </div>
      </div>

      <div id="solo-quiz-body">
        <img
          className={`solo-quiz-sprite${revealed ? ' revealed' : ''}${wrongFlash ? ' wrong' : ''}`}
          src={sprUrl}
          alt="?"
        />
        {result === 'correct' && (
          <div className="sq-result correct">✓ 정답! {current.ko}</div>
        )}
        {result === 'skip' && (
          <div className="sq-result skip">정답: {current.ko}</div>
        )}
        {!result && hints.map((h, i) => (
          <div key={i} className="sq-hint">{h}</div>
        ))}
      </div>

      <div id="solo-quiz-input-row">
        <input
          ref={inputRef}
          id="sq-input"
          type="text"
          placeholder="포켓몬 이름 입력 후 Enter..."
          autoComplete="off"
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          onKeyDown={handleAnswer}
          disabled={revealed}
        />
        <button id="sq-skip-btn" onClick={handleSkip} disabled={revealed}>스킵</button>
      </div>
    </div>
  );
}

function ChatMessage({ role, html, isStreaming }) {
  if (isStreaming) {
    return (
      <div className={`msg ${role}`}>
        <div className="dots"><span /><span /><span /></div>
      </div>
    );
  }
  return <div className={`msg ${role}`} dangerouslySetInnerHTML={{ __html: html }} />;
}

export default function ChatTab({ onOpenPokemon }) {
  const [quizMode, setQuizMode] = useState(false);
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('pm-chat');
      if (saved) {
        const msgs = JSON.parse(saved);
        if (Array.isArray(msgs) && msgs.length) return msgs.map(m => ({ role: m.role === 'user' ? 'user' : 'bot', html: renderMd(m.content), raw: m.content }));
      }
    } catch (_) {}
    return [];
  });
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('pm-chat');
      if (saved) { const msgs = JSON.parse(saved); if (Array.isArray(msgs)) return msgs; }
    } catch (_) {}
    return [];
  });
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [showPrev, setShowPrev] = useState(messages.length > 0);
  const chatRef = useRef(null);

  const scrollBottom = () => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  };
  useEffect(scrollBottom, [messages]);

  const clearChat = () => {
    setMessages([]); setHistory([]); setShowPrev(false);
    localStorage.removeItem('pm-chat');
  };

  const sendMessage = async (text) => {
    const msg = (text || input).trim();
    if (!msg || streaming) return;
    setInput('');
    setShowPrev(false);

    const userMsg = { role: 'user', html: renderMd(msg) };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);

    const botIdx = messages.length + 1;
    setMessages(prev => [...prev, { role: 'bot', html: '', isStreaming: true }]);

    let full = '', spriteHtml = '';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n'); buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6); if (raw === '[DONE]') continue;
          try {
            const p = JSON.parse(raw);
            if (p.error) { setMessages(prev => { const a=[...prev]; a[a.length-1]={role:'bot',html:p.error,isError:true}; return a; }); full=''; break; }
            if (p.type === 'meta' && p.pokemon_id) {
              const id = p.pokemon_id;
              spriteHtml = `<img class="pokemon-sprite" src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${id}.png" alt="pokemon-${id}">`;
            }
            if (p.text) {
              full += p.text;
              setMessages(prev => { const a=[...prev]; a[a.length-1]={role:'bot',html:spriteHtml+renderMd(full)}; return a; });
            }
          } catch (_) {}
        }
      }
      if (full) {
        const newHistory = [...history, { role:'user', content: msg }, { role:'assistant', content: full }].slice(-20);
        setHistory(newHistory);
        try { localStorage.setItem('pm-chat', JSON.stringify(newHistory)); } catch (_) {}
      }
    } catch (err) {
      setMessages(prev => { const a=[...prev]; a[a.length-1]={role:'bot',html:'네트워크 오류가 발생했어요.',isError:true}; return a; });
    } finally {
      setStreaming(false);
    }
  };

  if (quizMode) {
    return (
      <div className="view" id="view-chat">
        <SoloQuiz onExit={() => setQuizMode(false)} />
      </div>
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="view" id="view-chat">
      <div id="chat" ref={chatRef}>
        {!hasMessages && (
          <div id="welcome">
            <h2>뭐든지 물어보세요!</h2>
            <p>포켓몬 스탯 · 레이드 카운터 · PvP 랭킹 · 이벤트 · 로켓단 · 알 부화</p>
            <div className="chips">
              {CHIPS.map(c => (
                <div key={c} className="chip" onClick={() => sendMessage(c)}>{c}</div>
              ))}
              <div className="chip quiz-chip" onClick={() => setQuizMode(true)}>🖼️ 실루엣 퀴즈</div>
            </div>
          </div>
        )}
        {hasMessages && showPrev && (
          <div className="session-sep">─── 이전 대화 ───</div>
        )}
        {messages.map((m, i) => (
          <ChatMessage key={i} role={m.isError ? 'bot error' : m.role} html={m.html} isStreaming={m.isStreaming} />
        ))}
      </div>
      <div id="input-bar">
        {hasMessages && (
          <button id="clear-btn" onClick={clearChat} title="대화 초기화">↺</button>
        )}
        <input
          id="msg-input"
          type="text"
          placeholder="포켓몬 GO 질문을 입력하세요..."
          autoComplete="off"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
        />
        <button id="send-btn" onClick={() => sendMessage()} disabled={streaming}>↑</button>
      </div>
    </div>
  );
}
