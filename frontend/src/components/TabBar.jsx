const TABS = [
  { id: 'chat',      icon: '💬', label: '채팅' },
  { id: 'dex',       icon: '📖', label: '도감' },
  { id: 'raid',      icon: '🗓️', label: '레이드' },
  { id: 'egg',       icon: '🥚', label: '알' },
  { id: 'pvp',       icon: '🏆', label: 'PvP' },
  { id: 'card',      icon: '🃏', label: '카드' },
  { id: 'community', icon: '👥', label: '소통' },
];

export default function TabBar({ activeTab, onTabChange }) {
  return (
    <nav id="tab-bar">
      {TABS.map(tab => (
        <button
          key={tab.id}
          className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="tab-icon">{tab.icon}</span>
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
