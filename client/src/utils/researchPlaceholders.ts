export const isMeaninglessPlaceholder = (text: string): boolean => {
  if (!text || typeof text !== 'string') return true;
  const trimmed = text.trim();
  return /^(opportunity|threat|gap|market opening or tailwind|market risk or competitor reaction|core differentiator|unmet customer need)\s*\d*$/i.test(trimmed);
};
