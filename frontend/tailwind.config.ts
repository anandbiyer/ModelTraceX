import type { Config } from "tailwindcss";

/**
 * Tailwind themed with the shared MVA dark tokens (SDD §13.4.0). Colors map to
 * the CSS variables in src/styles/tokens.css so the single source of visual
 * truth stays in one place. Do not hard-code hex values in components.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        elev: "var(--elev)",
        sidebar: "var(--sidebar)",
        border: "var(--border)",
        "border-soft": "var(--border-soft)",
        text: "var(--text)",
        dim: "var(--dim)",
        muted: "var(--muted)",
        accent: { DEFAULT: "var(--accent)", soft: "var(--accent-soft)" },
        green: { DEFAULT: "var(--green)", soft: "var(--green-soft)" },
        amber: { DEFAULT: "var(--amber)", soft: "var(--amber-soft)" },
        red: { DEFAULT: "var(--red)", soft: "var(--red-soft)" },
        purple: { DEFAULT: "var(--purple)", soft: "var(--purple-soft)" },
      },
      fontFamily: {
        // Manrope for all UI; JetBrains Mono for code identifiers/expressions.
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: { DEFAULT: "var(--r)", lg: "var(--r-lg)" },
      boxShadow: { elev: "var(--shadow)" },
    },
  },
  plugins: [],
} satisfies Config;
