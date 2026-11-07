/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Task 14.3.2.1: Vazirmatn (self-hosted, @font-face in src/index.css) is the default
      // typeface. Tahoma has Persian glyphs on Windows and macOS, so it is the nearest
      // fallback while the file loads (font-display: swap) or if it fails to.
      fontFamily: {
        sans: ['Vazirmatn', 'Tahoma', 'system-ui', 'sans-serif'],
      },
      animation: {
        marquee: 'marquee 15s linear infinite',
        // Same ticker for RTL: use as `animate-marquee rtl:animate-marquee-rtl`.
        'marquee-rtl': 'marquee-rtl 15s linear infinite',
      },
      keyframes: {
        marquee: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(-100%)' },
        },
        // Mirror of `marquee`: text enters from the left and leaves to the right.
        'marquee-rtl': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
}