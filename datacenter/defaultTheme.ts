import { extendTheme } from '@mui/joy/styles';
import colors from '@mui/joy/colors';

export const joyTheme = extendTheme({
  colorSchemes: {
    light: {
      palette: {
        mode: 'dark',
        primary: {
          ...colors.purple,
        },
        neutral: {
          plainColor: '#4d4d4d',
          plainHoverColor: '#131318',
          plainHoverBg: '#EBEBEF',
          plainActiveBg: '#D8D8DF',
          plainDisabledColor: '#B9B9C6'
        },
        background: {
          body: '#fff',
          surface: '#fff'
        },
        text: {
          primary: '#25252D'
        },
      },
    },
    dark: {
      palette: {
        mode: 'light',
        primary: {
          ...colors.purple,
        },
        neutral: {
          plainColor: '#D8D8DF',
          plainHoverColor: '#F7F7F8',
          plainHoverBg: '#25252D',
          plainActiveBg: '#434356',
          plainDisabledColor: '#434356'
        },
        text: {
          primary: '#EBEBEF'
        },
        background: {
          body: '#0f172a',
          surface: '#1e293b40'
        }
      },
    },
  },
  fontFamily: {
    body: 'Josefin Sans, sans-serif',
    display: 'Josefin Sans, sans-serif',
  },
  typography: {
    display1: {
      background:
        'linear-gradient(-30deg, var(--joy-palette-primary-900), var(--joy-palette-primary-400))',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
    },
  },
});