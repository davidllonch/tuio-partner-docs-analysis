import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#eef6f8',
          100: '#d5eaef',
          200: '#aad5df',
          300: '#72b8c9',
          400: '#4196ad',
          500: '#2D6B7F',
          600: '#245669',
          700: '#1b4151',
          800: '#122c38',
          900: '#091720',
        },
        accent: {
          50:  '#e6fafa',
          100: '#ccf5f5',
          200: '#99ebeb',
          300: '#66e0e0',
          400: '#33d5d5',
          500: '#00C9C8',
          600: '#00a1a0',
          700: '#007978',
          800: '#005150',
          900: '#002828',
        },
      },
      fontFamily: {
        sans: ['Poppins', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
