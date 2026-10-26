import { ChatContext } from '@/app/chat-context';
import { interfaceThemeTokens, interfaceThemeVariables } from '@/lib/interface-tokens';
import type { ReactNode } from 'react';
import { useContext } from 'react';

/** Scope Dashboard tokens to its routes; the existing site theme is untouched. */
export default function DashboardRouteFrame({ children }: { children: ReactNode }) {
  const { mode } = useContext(ChatContext);
  return (
    <div
      className='flex h-full min-h-0 w-full min-w-0 flex-col'
      style={interfaceThemeVariables(interfaceThemeTokens('clarity', mode))}
    >
      {children}
    </div>
  );
}
