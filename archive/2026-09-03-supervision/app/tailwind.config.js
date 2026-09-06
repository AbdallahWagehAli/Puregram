/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Resolve from CSS variables so dark/light themes flip without recompiling.
        brand: {
          red: 'var(--red)',
          deep: 'var(--red-deep)',
          gold: 'var(--gold)',
        },
        bg: {
          DEFAULT: 'var(--bg)',
          2: 'var(--bg-2)',
        },
        surface: 'var(--surface)',
        ink: 'var(--ink)',
        line: 'var(--line)',
        'line-2': 'var(--line-2)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        dim: 'var(--dim)',
      },
      fontFamily: {
        ar: ['Tajawal', 'system-ui', 'sans-serif'],
        en: ['Inter', 'system-ui', 'sans-serif'],
        cairo: ['Cairo', 'Tajawal', 'sans-serif'],
      },
      borderRadius: {
        brand: '16px',
        'brand-lg': '22px',
      },
      boxShadow: {
        brand: 'var(--shadow)',
        glow: '0 14px 34px -14px rgba(46,158,79,.55)',
      },
      backgroundImage: {
        grad: 'var(--grad)',
        'grad-gold': 'var(--grad-gold)',
      },
      transitionTimingFunction: {
        brand: 'cubic-bezier(.22,.61,.36,1)',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'none' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'toast-in': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-in': 'fade-in .35s cubic-bezier(.22,.61,.36,1) both',
        'toast-in': 'toast-in .28s cubic-bezier(.22,.61,.36,1) both',
      },
    },
  },
  plugins: [],
};
