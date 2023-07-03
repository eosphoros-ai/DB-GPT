import { extendTheme } from '@mui/joy/styles';
import colors from '@mui/joy/colors';

export const joyTheme = extendTheme({
  colorSchemes: {
    light: {
      palette: {
        mode: 'dark',
        primary: {
          ...colors.grey,
          solidBg: '#9a9a9a91',
          solidColor: '#4e4e4e',
          solidHoverBg: '#d5d5d5',
          outlinedColor: '#4e4e59'
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
          primary: '#505050',
        },
      },
    },
    dark: {
      palette: {
        mode: 'light',
        primary: {
          ...colors.grey,
          softBg: '#353539',
          softHoverBg: '#35353978',
          softDisabledBg: '#353539',
          solidBg: '#434356',
          solidHoverBg: '#5a5a72',
        },
        neutral: {
          plainColor: '#D8D8DF',
          plainHoverColor: '#F7F7F8',
          plainHoverBg: '#353539',
          plainActiveBg: '#434356',
          plainDisabledColor: '#434356',
          outlinedBorder: '#353539',
          outlinedHoverBorder: '#454651'
        },
        text: {
          primary: '#EBEBEF'
        },
        background: {
          body: '#212121',
          surface: '#525262',
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