import { useState, useRef, useEffect } from 'react';
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
