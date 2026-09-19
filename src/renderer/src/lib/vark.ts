import type { LearningStyleSettings } from '../types/MathTypes';

export type VarkMode = keyof LearningStyleSettings;

export const VARK_MODES: Array<{ id: VarkMode; label: string; short: string; blurb: string }> = [
  { id: 'visual', label: 'Visual', short: 'V', blurb: 'diagrams, graphs, sketches, colour' },
  { id: 'aural', label: 'Aural', short: 'A', blurb: 'hearing it, talking it through' },
  { id: 'readWrite', label: 'Read/write', short: 'R', blurb: 'lists, notes, precise wording' },
  { id: 'kinesthetic', label: 'Kinesthetic', short: 'K', blurb: 'real examples, trying things out' },
];

export const VARK_MAX = 16;

export const isStyleSet = (s: LearningStyleSettings): boolean => VARK_MODES.some((m) => s[m.id] > 0);

/** VARK's stepping distance: how close to the top score a mode must be to count as preferred. */
const stepping = (total: number) => (total <= 16 ? 1 : total <= 22 ? 2 : total <= 26 ? 3 : 4);

export const preferredModes = (s: LearningStyleSettings): VarkMode[] => {
  if (!isStyleSet(s)) return [];
  const total = VARK_MODES.reduce((sum, m) => sum + s[m.id], 0);
  const top = Math.max(...VARK_MODES.map((m) => s[m.id]));
  const step = stepping(total);
  return VARK_MODES.filter((m) => s[m.id] > 0 && s[m.id] >= top - step).map((m) => m.id);
};

export const styleLabel = (s: LearningStyleSettings): string => {
  const prefs = preferredModes(s);
  if (!prefs.length) return 'Not set';
  if (prefs.length === 4) return 'Multimodal (VARK)';
  const names = prefs.map((id) => VARK_MODES.find((m) => m.id === id)!.label);
  return prefs.length > 1 ? `Multimodal (${names.join(', ')})` : names[0];
};

export const prefers = (s: LearningStyleSettings, mode: VarkMode): boolean => preferredModes(s).includes(mode);

/** Payload shape the backend expects. Returns undefined when the profile is not set. */
export const toBackendStyle = (s: LearningStyleSettings) =>
  isStyleSet(s) ? { visual: s.visual, aural: s.aural, read_write: s.readWrite, kinesthetic: s.kinesthetic } : undefined;

/** Browser text-to-speech (no model needed). Returns false when unavailable. */
export const speak = (text: string): boolean => {
  if (typeof window === 'undefined' || !('speechSynthesis' in window) || !text.trim()) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
  return true;
};

export const canSpeak = (): boolean => typeof window !== 'undefined' && 'speechSynthesis' in window;
