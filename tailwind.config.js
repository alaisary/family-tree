/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './tree/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#16181d',
        // legacy alias so existing mint-* utility usages stay valid
        mint: {
          50: '#faf6ec', 100: '#f3e9cf', 200: '#e9d6a3', 300: '#e0b352',
          400: '#d6a23c', 500: '#16181d', 600: '#0f1115', 700: '#0c0e12',
          800: '#0a0b0e', 900: '#08090b',
        },
      },
      fontFamily: {
        sans: ['Tajawal', '"IBM Plex Sans Arabic"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
