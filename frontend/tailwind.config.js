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
        // Liquid Canvas Brand Colors
        liquid: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1', // Primary Indigo
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        purple: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: '#7e22ce',
          800: '#6b21a8',
          900: '#581c87',
        },
        pink: {
          50: '#fdf2f8',
          100: '#fce7f3',
          200: '#fbcfe8',
          300: '#f9a8d4',
          400: '#f472b6',
          500: '#ec4899',
          600: '#db2777',
          700: '#be185d',
          800: '#9f1239',
          900: '#831843',
        },
        // Keep olive for backward compatibility
        olive: {
          50: '#f5f7f0',
          100: '#e8ede0',
          200: '#d3dcc2',
          300: '#b4c49a',
          400: '#95a875',
          500: '#7a8d5a',
          600: '#5f7047',
          700: '#4d5a3a',
          800: '#404a32',
          900: '#373f2c',
        },
      },
      backgroundImage: {
        'liquid-gradient': 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%)',
        'liquid-gradient-soft': 'linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 50%, rgba(236, 72, 153, 0.1) 100%)',
      },
      boxShadow: {
        'liquid': '0 10px 40px rgba(99, 102, 241, 0.2)',
        'liquid-lg': '0 20px 60px rgba(99, 102, 241, 0.3)',
        'glow': '0 0 20px rgba(99, 102, 241, 0.4)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
        'shimmer': 'shimmer 2s infinite',
        'blob': 'blob 7s infinite',
        'float': 'float 20s infinite linear',
        'gradient': 'gradient 3s ease infinite',
      },
      boxShadow: {
        'liquid': '0 10px 40px rgba(99, 102, 241, 0.2)',
        'liquid-lg': '0 20px 60px rgba(99, 102, 241, 0.3)',
        'glow': '0 0 20px rgba(99, 102, 241, 0.4)',
        'olive-500/50': '0 0 30px rgba(95, 112, 71, 0.5)',
      },
    },
  },
  plugins: [],
}

