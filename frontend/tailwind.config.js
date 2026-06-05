/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: 0, transform: "translateY(10px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: 0.55 },
          "50%": { opacity: 1 },
        },
        "gradient-x": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        blink: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0 },
        },
      },
      animation: {
        "fade-up": "fade-up 0.45s cubic-bezier(0.22,1,0.36,1) both",
        "glow-pulse": "glow-pulse 2.4s ease-in-out infinite",
        "gradient-x": "gradient-x 8s ease infinite",
        blink: "blink 1s steps(2) infinite",
      },
      boxShadow: {
        glow: "0 0 24px -4px rgba(99,102,241,0.55)",
        "glow-cyan": "0 0 24px -4px rgba(34,211,238,0.5)",
        "glow-rose": "0 0 24px -4px rgba(244,63,94,0.5)",
      },
      backgroundSize: { "200": "200% 200%" },
    },
  },
  plugins: [],
};
