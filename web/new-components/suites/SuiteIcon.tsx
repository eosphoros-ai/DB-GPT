import type { SuiteItem } from '@/types/suite';
import { useId } from 'react';

const artwork = {
  'db-analysis': {
    colors: ['#457ff5', '#2550ce'],
    shape: (
      <>
        <rect x='13' y='31' width='8' height='15' rx='2' fill='#a8c8ff' />
        <rect x='26' y='23' width='8' height='23' rx='2' fill='#e0ecff' />
        <rect x='39' y='13' width='8' height='33' rx='2' fill='white' />
        <path d='m12 25 13-10 9 3 12-10' stroke='white' strokeOpacity='.55' strokeWidth='2' fill='none' />
      </>
    ),
  },
  'db-query': {
    colors: ['#42c6aa', '#138c85'],
    shape: (
      <>
        <ellipse cx='25' cy='18' rx='12' ry='5' fill='white' />
        <path d='M13 18v18c0 7 24 7 24 0V18M13 26c0 7 24 7 24 0' stroke='white' strokeWidth='2.6' fill='none' />
        <circle cx='38' cy='36' r='8' fill='#1da092' stroke='white' strokeWidth='3' />
        <path d='m44 42 6 6' stroke='white' strokeWidth='4' strokeLinecap='round' />
      </>
    ),
  },
  'financial-analysis': {
    colors: ['#ffb877', '#ef7851'],
    shape: (
      <>
        <rect x='17' y='12' width='29' height='37' rx='4' fill='white' fillOpacity='.32' transform='rotate(9 30 30)' />
        <rect x='13' y='10' width='29' height='38' rx='4' fill='white' />
        <path d='M20 18h15M20 23h10' stroke='#ee9273' strokeWidth='2' strokeLinecap='round' />
        <rect x='20' y='35' width='4' height='7' rx='1' fill='#f9bd9e' />
        <rect x='27' y='29' width='4' height='13' rx='1' fill='#f6a080' />
        <rect x='34' y='25' width='4' height='17' rx='1' fill='#f08261' />
      </>
    ),
  },
  'metadata-architecture-expert': {
    colors: ['#7398e8', '#4a63b5'],
    shape: (
      <>
        <path d='M30 18v11M17 40V30h26v10' stroke='white' strokeOpacity='.8' strokeWidth='2.4' fill='none' />
        <rect x='22' y='10' width='16' height='13' rx='3' fill='white' />
        <rect x='9' y='35' width='16' height='13' rx='3' fill='#dce8ff' />
        <rect x='35' y='35' width='16' height='13' rx='3' fill='white' />
      </>
    ),
  },
  'sql-optimization-expert': {
    colors: ['#f4c85c', '#dc9a24'],
    shape: (
      <>
        <path d='M14 40a19 19 0 1 1 32 0' stroke='white' strokeWidth='4' strokeLinecap='round' fill='none' />
        <path d='m30 31 10-10' stroke='white' strokeWidth='4' strokeLinecap='round' />
        <circle cx='30' cy='31' r='4' fill='white' />
        <path d='M15 41h30' stroke='white' strokeOpacity='.45' strokeWidth='2' strokeLinecap='round' />
      </>
    ),
  },
};

/** Owned artwork for built-ins; untrusted package icons are rendered as text, never markup. */
export default function SuiteIcon({ suite, size = 60 }: { suite: SuiteItem; size?: number }) {
  const gradientId = useId();
  const art = suite.source === 'official' ? artwork[suite.name as keyof typeof artwork] : undefined;
  const icon = suite.icon || suite.manifest_snapshot?.icon;
  const fallback =
    icon && Array.from(icon).length <= 8 ? icon : Array.from(suite.display || suite.name)[0]?.toUpperCase();

  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        display: 'grid',
        placeItems: 'center',
        borderRadius: size * 0.27,
        overflow: 'hidden',
        background: art ? undefined : 'var(--suite-icon-bg, #eef2f8)',
        color: 'var(--suite-muted, #657181)',
        fontSize: size * 0.4,
        boxShadow: '0 3px 10px #18274b0a',
      }}
    >
      {art ? (
        <svg width={size} height={size} viewBox='0 0 60 60' focusable='false'>
          <defs>
            <linearGradient id={gradientId} x1='0' y1='0' x2='1' y2='1'>
              <stop stopColor={art.colors[0]} />
              <stop offset='1' stopColor={art.colors[1]} />
            </linearGradient>
          </defs>
          <rect width='60' height='60' rx='16' fill={`url(#${gradientId})`} />
          <circle cx='47' cy='8' r='28' fill='white' fillOpacity='.06' />
          {art.shape}
        </svg>
      ) : (
        fallback || 'P'
      )}
    </span>
  );
}
