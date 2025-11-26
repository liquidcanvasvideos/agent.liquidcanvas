/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f5f7f0',
          100: '#e8ede0',
          200: '#d1dbc1',
          300: '#b4c39a',
          400: '#9aab7a',
          500: '#808000', // Olive green base
          600: '#6b6d00',
          700: '#565800',
          800: '#424300',
          900: '#2e2f00',
        },
        olive: {
          50: '#f5f7f0',
          100: '#e8ede0',
          200: '#d1dbc1',
          300: '#b4c39a',
          400: '#9aab7a',
          500: '#808000',
          600: '#6b6d00',
          700: '#565800',
          800: '#424300',
          900: '#2e2f00',
        },
      },
    },
  },
  plugins: [],
}

