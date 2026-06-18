export const TYPE_KO = {
  normal:'노말', fire:'불꽃', water:'물', electric:'전기', grass:'풀', ice:'얼음',
  fighting:'격투', poison:'독', ground:'땅', flying:'비행', psychic:'에스퍼',
  bug:'벌레', rock:'바위', ghost:'고스트', dragon:'드래곤', dark:'악',
  steel:'강철', fairy:'페어리',
};

export const TYPE_BG = {
  normal:'#71727a', fire:'#e8621a', water:'#2980ef', electric:'#f2c100',
  grass:'#38b14a', ice:'#3dcef3', fighting:'#ce4265', poison:'#ab5aca',
  ground:'#d97a28', flying:'#81b9f0', psychic:'#f85888', bug:'#91c12f',
  rock:'#c7b78b', ghost:'#5269ad', dragon:'#0b6dc3', dark:'#595761',
  steel:'#5a8fa3', fairy:'#ef70ef',
};

export const TYPE_EN_FROM_KO = Object.fromEntries(
  Object.entries(TYPE_KO).map(([en, ko]) => [ko, en])
);

export const TYPE_LIST = [
  'normal','fire','water','electric','grass','ice','fighting','poison',
  'ground','flying','psychic','bug','rock','ghost','dragon','dark','steel','fairy',
];

export const WEATHER_BOOST = {
  fire:'맑음☀️', grass:'맑음☀️', ground:'맑음☀️',
  normal:'부분흐림⛅', rock:'부분흐림⛅',
  water:'비🌧️', electric:'비🌧️', bug:'비🌧️',
  ice:'눈❄️', steel:'눈❄️',
  fighting:'흐림☁️', poison:'흐림☁️', fairy:'흐림☁️',
  flying:'바람🌬️', dragon:'바람🌬️', psychic:'바람🌬️',
  dark:'안개🌫️', ghost:'안개🌫️',
};

export const WMO_TO_POGO = {
  0:'sunny', 1:'sunny', 2:'partly-cloudy', 3:'cloudy',
  45:'fog', 48:'fog',
  51:'rain', 53:'rain', 55:'rain', 56:'rain', 57:'rain',
  61:'rain', 63:'rain', 65:'rain', 66:'rain', 67:'rain',
  71:'snow', 73:'snow', 75:'snow', 77:'snow', 85:'snow', 86:'snow',
  80:'rain', 81:'rain', 82:'rain',
  95:'windy', 96:'windy', 99:'windy',
};

export const POGO_WEATHER = {
  'sunny':         { emoji:'☀️', name:'맑음',      types:['fire','grass','ground'] },
  'partly-cloudy': { emoji:'⛅', name:'구름 조금', types:['normal','rock'] },
  'cloudy':        { emoji:'☁️', name:'흐림',      types:['fairy','fighting','poison'] },
  'fog':           { emoji:'🌫️', name:'안개',      types:['ghost','dark'] },
  'rain':          { emoji:'🌧️', name:'비',        types:['water','electric','bug'] },
  'snow':          { emoji:'❄️', name:'눈',        types:['ice','steel'] },
  'windy':         { emoji:'🌬️', name:'바람',      types:['dragon','flying','psychic'] },
};

export const EVENT_TYPE_CONFIG = {
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

export const WEATHER_ICON = {
  'sunny':'☀️', 'clear':'☀️', 'partly cloudy':'⛅', 'cloudy':'☁️',
  'windy':'🌬️', 'rainy':'🌧️', 'snowy':'❄️', 'foggy':'🌫️',
};

export const TIER_LABEL = { '1':'1성', '3':'3성', '5':'5성', 'mega':'메가', 'elite':'엘리트' };
export const TIER_ORDER = ['mega','5','elite','3','1'];
