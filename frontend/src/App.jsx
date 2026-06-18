import { useState, useCallback } from 'react';
import Header from './components/Header';
import TabBar from './components/TabBar';
import PokemonPopup from './components/PokemonPopup';
import ChatTab from './components/tabs/ChatTab';
import DexTab from './components/tabs/DexTab';
import RaidTab from './components/tabs/RaidTab';
import EggTab from './components/tabs/EggTab';
import PvpTab from './components/tabs/PvpTab';
import CardTab from './components/tabs/CardTab';
import CommunityTab from './components/tabs/CommunityTab';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [popup, setPopup] = useState(null);

  const openPokemon = useCallback((dex, slug = null, isShadow = false, formDex = null) => {
    if (!dex) return;
    setPopup({ dex, slug, isShadow, formDex });
  }, []);

  const closePopup = useCallback(() => setPopup(null), []);

  return (
    <>
      <Header activeTab={activeTab} />
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
        {activeTab === 'chat'      && <ChatTab      onOpenPokemon={openPokemon} />}
        {activeTab === 'dex'       && <DexTab        onOpenPokemon={openPokemon} />}
        {activeTab === 'raid'      && <RaidTab       onOpenPokemon={openPokemon} />}
        {activeTab === 'egg'       && <EggTab        onOpenPokemon={openPokemon} />}
        {activeTab === 'pvp'       && <PvpTab        onOpenPokemon={openPokemon} />}
        {activeTab === 'card'      && <CardTab />}
        {activeTab === 'community' && <CommunityTab  onOpenPokemon={openPokemon} />}

        {popup && (
          <PokemonPopup
            dex={popup.dex}
            slug={popup.slug}
            isShadow={popup.isShadow}
            formDex={popup.formDex}
            onClose={closePopup}
            onOpenPokemon={openPokemon}
          />
        )}
      </div>
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
    </>
  );
}
