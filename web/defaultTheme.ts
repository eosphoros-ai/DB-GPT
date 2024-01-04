import { extendTheme } from '@mui/joy/styles';
import colors from '@mui/joy/colors';

export const joyTheme = extendTheme({
  colorSchemes: {
    light: {
      palette: {
        mode: 'dark',
        primary: {
          ...colors.grey,
          solidBg: '#e6f4ff',
          solidColor: '#1677ff',
          solidHoverBg: '#e6f4ff',
        },
        neutral: {
          plainColor: '#4d4d4d',
          plainHoverColor: '#131318',
          plainHoverBg: '#EBEBEF',
          plainActiveBg: '#D8D8DF',
          plainDisabledColor: '#B9B9C6',
        },
        background: {
          body: '#F7F7F7',
          surface: '#fff',
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
          solidBg: '#51525beb',
          solidHoverBg: '#51525beb',
        },
        neutral: {
          plainColor: '#D8D8DF',
          plainHoverColor: '#F7F7F8',
          plainHoverBg: '#353539',
          plainActiveBg: '#434356',
          plainDisabledColor: '#434356',
          outlinedBorder: '#353539',
          outlinedHoverBorder: '#454651',
        },
        text: {
          primary: '#FDFDFC',
        },
        background: {
          body: '#151622',
          surface: '#51525beb',
        },
      },
    },
  },
  fontFamily: {
    body: 'Josefin Sans, sans-serif',
    display: 'Josefin Sans, sans-serif',
  },
  zIndex: {
    modal: 1001,
  },
});
