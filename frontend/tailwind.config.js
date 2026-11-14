/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fff8eb",
          100: "#ffedc6",
          200: "#ffd988",
          300: "#ffbf4a",
          400: "#ffa51f",
          500: "#f98307",
          600: "#dd5e02",
          700: "#b74106",
          800: "#94330c",
          900: "#7a2b0d"
        },
        ink: {
          50: "#f6f6f5",
          100: "#e7e7e4",
          200: "#d0d0ca",
          300: "#aeaea6",
          400: "#85857c",
          500: "#6a6a61",
          600: "#54544d",
          700: "#44443f",
          800: "#393936",
          900: "#1f1f1d"
        }
      },
      fontFamily: {
        sans: ["Inter", "Cairo", "Segoe UI", "Tahoma", "sans-serif"],
        display: ["Cairo", "Inter", "Segoe UI", "sans-serif"]
      },
      boxShadow: {
        card: "0 1px 2px rgba(31,31,29,.05), 0 8px 24px -12px rgba(31,31,29,.18)"
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        },
        pulseDot: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: ".35" }
        }
      },
      animation: {
        "fade-up": "fade-up .35s ease-out both",
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite"
      }
    }
  },
  plugins: []
};
