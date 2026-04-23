/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        joule: {
          bg: '#f8f5ef',
          panel: '#fffdf8',
          ink: '#1e2a2f',
          muted: '#5d6a70',
          accent: '#186a7b',
          border: '#d9d2c3',
          ok: '#2b7a0b',
          bad: '#8d1c13',
          running: '#8a5b00',
          chip: '#f2eadf',
        },
      },
      fontFamily: {
        serif: ['Georgia', 'Iowan Old Style', 'serif'],
        mono: ['IBM Plex Mono', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
