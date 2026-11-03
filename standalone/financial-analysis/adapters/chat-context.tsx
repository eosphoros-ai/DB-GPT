import { createContext } from 'react';
export const ChatContext = createContext<{ mode: 'light' | 'dark' }>({ mode: 'light' });
