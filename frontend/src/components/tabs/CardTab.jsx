import { useState, useRef } from 'react';
import { TYPE_BG, TYPE_EN_FROM_KO } from '../../utils/constants';

export default function CardTab() {
  const [preview, setPreview] = useState(null);
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);
  const cameraRef = useRef(null);

  const handleFile = (f) => {
    if (!f) return;
    const url = URL.createObjectURL(f);
    setFile(f); setPreview(url); setResult(null); setError(null);
  };

  const clearScan = () => {
    setFile(null); setPreview(null); setResult(null); setError(null);
    if (fileRef.current) fileRef.current.value = '';
    if (cameraRef.current) cameraRef.current.value = '';
  };

  const doScan = async () => {
    if (!file) return;
    setAnalyzing(true); setResult(null); setError(null);
    const fd = new FormData(); fd.append('file', file);
    try {
      const res = await fetch('/api/card-scan', { method: 'POST', body: fd });
      const card = await res.json();
      if (card.error) { setError(card.error); }
      else { setResult(card); }
    } catch { setError('네트워크 오류가 발생했어요.'); }
    finally { setAnalyzing(false); }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f?.type.startsWith('image/')) handleFile(f);
  };

  return (
    <div className="view" id="view-card">
      <div id="card-inner">
        {!preview && (
          <div
            className={`card-upload-area${dragOver ? ' drag-over' : ''}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <div className="card-upload-icon">🃏</div>
            <div className="card-upload-title">포켓몬 카드 사진을 올려주세요</div>
            <div className="card-upload-sub">탭해서 사진 선택 · 드래그 앤 드롭</div>
          </div>
        )}
        <input ref={fileRef} type="file" accept="image/*" style={{ display:'none' }} onChange={e => handleFile(e.target.files[0])} />
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" style={{ display:'none' }} onChange={e => handleFile(e.target.files[0])} />

        {!preview && (
          <div className="card-btn-row">
            <button className="card-btn primary" onClick={() => cameraRef.current?.click()}>📷 카메라로 촬영</button>
            <button className="card-btn secondary" onClick={() => fileRef.current?.click()}>🖼 갤러리에서 선택</button>
          </div>
        )}

        {preview && !result && !analyzing && (
          <>
            <div className="card-preview-wrap">
              <img className="card-preview-img" src={preview} alt="카드 미리보기" />
              <button className="card-preview-clear" onClick={clearScan}>✕</button>
            </div>
            <div className="card-btn-row">
              <button className="card-btn primary" onClick={doScan}>🔍 카드 분석하기</button>
              <button className="card-btn secondary" onClick={clearScan}>↩ 다시 선택</button>
            </div>
          </>
        )}

        {analyzing && (
          <div className="card-analyzing">
            <div className="dots"><span /><span /><span /></div>
            <div className="card-analyzing-text">Claude가 카드를 분석하는 중...</div>
          </div>
        )}

        {error && <div className="card-error">{error}</div>}

        {result && (
          <>
            <div className="card-result">
              <div className="card-result-header">
                <img className="card-result-thumb" src={preview} alt="카드" />
                <div className="card-result-meta">
                  <div className="card-result-name">{result.name_ko || result.name_en || ''}</div>
                  <div className="card-result-en">{result.name_en || ''}</div>
                  <div className="card-result-badges">
                    {result.rarity && <span className="card-badge badge-rarity">{result.rarity}</span>}
                    {result.variant && result.variant !== '일반' && <span className="card-badge badge-variant">{result.variant}</span>}
                    {result.pokemon_type && (
                      <span className="card-badge badge-type" style={{ background: TYPE_BG[result.pokemon_type] || TYPE_BG[TYPE_EN_FROM_KO[result.pokemon_type]] || '#71727a' }}>
                        {result.pokemon_type}
                      </span>
                    )}
                    {result.hp && <span className="card-badge badge-hp">HP {result.hp}</span>}
                  </div>
                </div>
              </div>
              <div className="card-detail-grid">
                {[['세트', result.set_name], ['카드 번호', result.card_number], ['규정 마크', result.regulation_mark], ['일러스트레이터', result.illustrator]]
                  .filter(([, v]) => v)
                  .map(([l, v]) => (
                    <div key={l} className="card-detail-item">
                      <div className="card-detail-label">{l}</div>
                      <div className="card-detail-val">{String(v)}</div>
                    </div>
                  ))
                }
                {result.description && <div className="card-description">{result.description}</div>}
              </div>
              <div className="card-link-row">
                <a className="card-link-btn kream" href={result.kream_url} target="_blank" rel="noopener">🛒 KREAM 시세</a>
                <a className="card-link-btn google" href={result.google_url} target="_blank" rel="noopener">🔍 구글 시세</a>
              </div>
            </div>
            <div style={{ textAlign:'center' }}>
              <button className="card-btn secondary" style={{ maxWidth:200, margin:'0 auto' }} onClick={clearScan}>↩ 다른 카드 분석</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
