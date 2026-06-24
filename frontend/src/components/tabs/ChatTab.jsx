import { useState, useRef, useEffect, useCallback } from 'react';
import { renderMd } from '../../utils/helpers';
import { TYPE_KO } from '../../utils/constants';

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

const QUIZ_HINTS = (pm) => [
  `타입: ${TYPE_KO[pm.t1] || pm.t1}${pm.t2 ? ' / ' + (TYPE_KO[pm.t2] || pm.t2) : ''}`,
  `세대: ${pm.gen}세대`,
  `이름: ${pm.ko.length}글자`,
];

function QuizMessage({ msg, onNext }) {
  const { pokemon: pm, hints, revealed, correct } = msg;
  const sprUrl = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${pm.dex}.png`;
  const fbUrl  = `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pm.dex}.png`;
  return (
    <div className="msg bot">
      <div style={{ marginBottom: 4 }}><strong>🎮 포켓몬 퀴즈!</strong> 이 포켓몬은 누구일까요?</div>
      <img
        className={`quiz-sprite${revealed ? ' revealed' : ''}`}
        src={sprUrl}
        onError={e => { e.target.src = fbUrl; }}
        alt="?"
      />
      {hints.length > 0 && (
        <div className="quiz-hints-area">
          {hints.map((h, i) => <div key={i} className="quiz-hint-line">힌트 {i + 1}: {h}</div>)}
        </div>
      )}
      {!revealed && (
        <div className="quiz-hint-line" style={{ color: '#64748b', marginTop: 6 }}>
          💬 채팅창에 답을 입력하세요! (모르면 &quot;포기&quot; 입력)
        </div>
      )}
      {revealed && (
        <div style={{ marginTop: 8 }}>
          {correct
            ? <div className="quiz-correct">🎉 정답! <strong>{pm.ko}</strong> ({pm.en})</div>
            : <div>정답은 <strong>{pm.ko}</strong> ({pm.en})이었어요!</div>
          }
          <button className="quiz-btn" onClick={onNext}>다음 문제 ▶</button>
        </div>
      )}
    </div>
  );
}

function ChatMessage({ msg, onQuizNext }) {
  if (msg.type === 'quiz') return <QuizMessage msg={msg} onNext={onQuizNext} />;
  if (msg.isStreaming) {
    return <div className={`msg ${msg.role}`}><div className="dots"><span /><span /><span /></div></div>;
  }
  return <div className={`msg ${msg.role}${msg.isError ? ' error' : ''}`} dangerouslySetInnerHTML={{ __html: msg.html }} />;
}

export default function ChatTab({ onOpenPokemon }) {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('pm-chat');
      if (saved) {
        const msgs = JSON.parse(saved);
        if (Array.isArray(msgs) && msgs.length)
          return msgs.map(m => ({ role: m.role === 'user' ? 'user' : 'bot', html: renderMd(m.content), raw: m.content }));
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
  const [quizState, setQuizState] = useState(null); // { msgIdx, hintIdx }
  const chatRef    = useRef(null);
  const messagesRef = useRef(messages);
  const quizStateRef = useRef(null);
  const dexRef     = useRef(null);

  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => { quizStateRef.current = quizState; }, [quizState]);

  const scrollBottom = () => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  };
  useEffect(scrollBottom, [messages]);

  const clearChat = () => {
    setMessages([]); setHistory([]); setShowPrev(false); setQuizState(null);
    localStorage.removeItem('pm-chat');
  };

  const startQuiz = useCallback(async () => {
    if (!dexRef.current) {
      const data = await fetch('/api/pokedex').then(r => r.json());
      dexRef.current = data;
    }
    const pool = dexRef.current;
    const pm = pool[Math.floor(Math.random() * pool.length)];
    const quizMsg = { role: 'bot', type: 'quiz', pokemon: pm, hints: [], revealed: false, correct: false };
    const newIdx = messagesRef.current.length;
    setMessages(prev => [...prev, quizMsg]);
    setQuizState({ msgIdx: newIdx, hintIdx: 0 });
    setShowPrev(false);
  }, []);

  const handleQuizAnswer = useCallback((text) => {
    const qs = quizStateRef.current;
    if (!qs) return;
    const { msgIdx, hintIdx } = qs;
    const qMsg = messagesRef.current[msgIdx];
    if (!qMsg || qMsg.type !== 'quiz') return;
    const pm = qMsg.pokemon;
    const trimmed = text.trim();

    if (trimmed === '포기') {
      setQuizState(null);
      setMessages(prev => prev.map((m, i) => i === msgIdx ? { ...m, revealed: true, correct: false } : m));
      return;
    }

    if (trimmed.toLowerCase() === pm.ko.toLowerCase() || trimmed.toLowerCase() === pm.en.toLowerCase()) {
      setQuizState(null);
      setMessages(prev => prev.map((m, i) => i === msgIdx ? { ...m, revealed: true, correct: true } : m));
      return;
    }

    const allHints = QUIZ_HINTS(pm);
    if (hintIdx < allHints.length) {
      setQuizState({ msgIdx, hintIdx: hintIdx + 1 });
      setMessages(prev => {
        const updated = prev.map((m, i) => i === msgIdx ? { ...m, hints: [...m.hints, allHints[hintIdx]] } : m);
        return [...updated, { role: 'bot', html: '<span style="color:#ef4444">❌ 틀렸어요!</span> 힌트를 확인하세요.' }];
      });
    } else {
      setQuizState(null);
      setMessages(prev => prev.map((m, i) => i === msgIdx ? { ...m, revealed: true, correct: false } : m));
    }
  }, []);

  const sendMessage = async (text) => {
    const msg = (text || input).trim();
    if (!msg) return;
    setInput('');
    setShowPrev(false);

    // 퀴즈 진행 중 — 채팅창 입력을 답변으로 처리
    if (quizStateRef.current) {
      setMessages(prev => [...prev, { role: 'user', html: renderMd(msg) }]);
      handleQuizAnswer(msg);
      return;
    }

    if (streaming) return;

    // 퀴즈 시작 키워드
    const lower = msg.toLowerCase().replace(/\s/g, '');
    if (lower === '퀴즈' || lower === '실루엣퀴즈' || lower === '퀴즈시작') {
      setMessages(prev => [...prev, { role: 'user', html: renderMd(msg) }]);
      await startQuiz();
      return;
    }

    // 일반 LLM 채팅
    const userMsg = { role: 'user', html: renderMd(msg) };
    setMessages(prev => [...prev, userMsg]);
    setStreaming(true);
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
              spriteHtml = `<img class="pokemon-sprite" src="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${p.pokemon_id}.png" alt="pokemon-${p.pokemon_id}">`;
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
              <div className="chip quiz-chip" onClick={startQuiz}>🎮 실루엣 퀴즈</div>
            </div>
          </div>
        )}
        {hasMessages && showPrev && (
          <div className="session-sep">─── 이전 대화 ───</div>
        )}
        {messages.map((m, i) => (
          <ChatMessage key={i} msg={m} onQuizNext={startQuiz} />
        ))}
      </div>
      <div id="input-bar">
        {hasMessages && (
          <button id="clear-btn" onClick={clearChat} title="대화 초기화">↺</button>
        )}
        <input
          id="msg-input"
          type="text"
          placeholder={quizState ? '포켓몬 이름 입력... (모르면 "포기")' : '포켓몬 GO 질문을 입력하세요...'}
          autoComplete="off"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
        />
        <button id="send-btn" onClick={() => sendMessage()} disabled={streaming && !quizState}>↑</button>
      </div>
    </div>
  );
}
