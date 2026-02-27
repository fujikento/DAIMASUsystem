export interface DayTheme {
  key: string;
  dayJa: string;
  nameJa: string;
  nameEn: string;
  color: string;
  bgGradient: string;
  icon: string;
}

export const DAY_THEMES: Record<string, DayTheme> = {
  monday: {
    key: "monday",
    dayJa: "月曜日",
    nameJa: "和 〜 Japanese Zen",
    nameEn: "Japanese Zen",
    color: "#8B7355",
    bgGradient: "from-amber-950 to-stone-900",
    icon: "🎍",
  },
  tuesday: {
    key: "tuesday",
    dayJa: "火曜日",
    nameJa: "火 〜 Fire & Passion",
    nameEn: "Fire & Passion",
    color: "#FF4500",
    bgGradient: "from-red-950 to-orange-950",
    icon: "🔥",
  },
  wednesday: {
    key: "wednesday",
    dayJa: "水曜日",
    nameJa: "海 〜 Ocean Deep",
    nameEn: "Ocean Deep",
    color: "#006994",
    bgGradient: "from-cyan-950 to-blue-950",
    icon: "🌊",
  },
  thursday: {
    key: "thursday",
    dayJa: "木曜日",
    nameJa: "森 〜 Forest Spirit",
    nameEn: "Forest Spirit",
    color: "#228B22",
    bgGradient: "from-green-950 to-emerald-950",
    icon: "🌲",
  },
  friday: {
    key: "friday",
    dayJa: "金曜日",
    nameJa: "宝 〜 Golden Luxury",
    nameEn: "Golden Luxury",
    color: "#FFD700",
    bgGradient: "from-yellow-950 to-amber-950",
    icon: "✨",
  },
  saturday: {
    key: "saturday",
    dayJa: "土曜日",
    nameJa: "宇宙 〜 Space Odyssey",
    nameEn: "Space Odyssey",
    color: "#4B0082",
    bgGradient: "from-indigo-950 to-purple-950",
    icon: "🚀",
  },
  sunday: {
    key: "sunday",
    dayJa: "日曜日",
    nameJa: "物語 〜 Fairy Tale",
    nameEn: "Fairy Tale",
    color: "#FF69B4",
    bgGradient: "from-pink-950 to-rose-950",
    icon: "📖",
  },
};

const DAY_NAMES = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

export function getTodayTheme(): DayTheme {
  const dayIndex = new Date().getDay();
  const dayName = DAY_NAMES[dayIndex];
  return DAY_THEMES[dayName];
}

export function getDayTheme(dayOfWeek: string): DayTheme {
  return DAY_THEMES[dayOfWeek] || DAY_THEMES["monday"];
}

export const DAY_LABELS: Record<string, string> = {
  monday: "月曜日",
  tuesday: "火曜日",
  wednesday: "水曜日",
  thursday: "木曜日",
  friday: "金曜日",
  saturday: "土曜日",
  sunday: "日曜日",
};
