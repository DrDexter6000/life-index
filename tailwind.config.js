/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./web/templates/**/*.html",
    "./web/static/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        'display': ['Newsreader', 'serif'],
        'sans': ['Manrope', 'sans-serif'],
      },
      colors: {
        // Celestial theme colors (CSS variables are primary)
        'celestial-primary': 'var(--color-primary)',
        'celestial-secondary': 'var(--color-secondary)',
        'celestial-tertiary': 'var(--color-tertiary)',
      },
    },
  },
  plugins: [],
}