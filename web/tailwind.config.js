const defaultTheme = require('tailwindcss/defaultTheme');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./pages/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}', './app/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Josefin Sans"', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        theme: {
          primary: '#0069fe',
          light: '#f7f7f7',
          dark: '#151622',
          'dark-container': '#232734',
        },
      },
    },
  },
  important: true,
  darkMode: 'class',
  /**
   * @see https://www.tailwindcss-animated.com/configurator.html
   */
  plugins: [require('tailwindcss-animated')],
};
