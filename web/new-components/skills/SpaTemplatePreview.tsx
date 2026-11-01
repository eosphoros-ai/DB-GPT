import styles from './TemplateMotion.module.css';

/** Illustrative schedule, never presented as a queried business result. */
export default function SpaTemplatePreview() {
  return (
    <svg
      viewBox='0 0 640 360'
      role='img'
      aria-label='美业预约管理风格示意：梅色导航、周历与房间安排'
      className={styles.spa}
    >
      <rect width='640' height='360' fill='#f8f2ee' />
      <path d='M0 0H126V360H0Z' fill='#533d50' />
      <circle cx='38' cy='40' r='14' fill='none' stroke='#dcb991' />
      <path d='M28 42Q38 23 48 42Q38 50 28 42M38 30V48' fill='none' stroke='#dcb991' />
      <text x='22' y='83' fill='#fcf3e9' fontSize='22' fontFamily='Georgia, SimSun, serif'>
        Serenity
      </text>
      <text x='22' y='104' fill='#d6c6d1' fontSize='10'>
        预约 · 服务 · 会员
      </text>
      <rect x='12' y='138' width='102' height='34' rx='8' fill='#795e71' />
      {['预约日历', '房间安排', '会员经营', '服务分析'].map((s, i) => (
        <g key={s}>
          <circle cx='26' cy={155 + i * 39} r='3' fill={i === 0 ? '#e8c497' : '#a48c9b'} />
          <text x='38' y={159 + i * 39} fill={i === 0 ? '#fff4e9' : '#d4c3cf'} fontSize='11'>
            {s}
          </text>
        </g>
      ))}
      <path
        d='M23 325C48 292 56 355 103 313M23 332C52 299 63 355 104 324'
        fill='none'
        stroke='#aa899c'
        strokeWidth='1'
      />
      <text x='148' y='37' fill='#533d50' fontSize='23' fontFamily='Georgia, SimSun, serif'>
        从容安排每一天
      </text>
      <text x='148' y='57' fill='#8f7e87' fontSize='10'>
        服务有序，让每一份关注恰到好处
      </text>
      <rect x='537' y='22' width='80' height='27' rx='13' fill='#533d50' />
      <text x='552' y='40' fill='#fff8f2' fontSize='10'>
        ＋ 新建预约
      </text>
      <rect x='148' y='76' width='320' height='192' rx='12' fill='#fffdfb' />
      <text x='164' y='101' fill='#4c3d45' fontSize='13' fontWeight='600'>
        本周预约
      </text>
      <text x='360' y='101' fill='#9a8892' fontSize='10'>
        9 月 21 — 27 日
      </text>
      {[
        ['一', '21'],
        ['二', '22'],
        ['三', '23'],
        ['四', '24'],
        ['五', '25'],
        ['六', '26'],
        ['日', '27'],
      ].map(([day, date], i) => (
        <g key={day}>
          <rect x={160 + i * 42} y='114' width='36' height='44' rx='10' fill={i === 1 ? '#f0dfe5' : '#fbf7f3'} />
          <text x={178 + i * 42} y='130' textAnchor='middle' fontSize='9' fill='#907b85'>
            {day}
          </text>
          <text
            x={178 + i * 42}
            y='147'
            textAnchor='middle'
            fontSize='12'
            fill='#593b4d'
            fontWeight={i === 1 ? '700' : '400'}
          >
            {date}
          </text>
        </g>
      ))}
      {['舒缓护理', '会员预约', '芳香护理'].map((s, i) => (
        <g key={s}>
          <text x='164' y={188 + i * 29} fontSize='10' fill='#a08d92'>
            {['09:30', '10:00', '11:30'][i]}
          </text>
          <rect x='205' y={174 + i * 29} width='248' height='23' rx='6' fill={i === 1 ? '#eef3ed' : '#f8edf0'} />
          <rect x='205' y={178 + i * 29} width='3' height='15' rx='1' fill={i === 1 ? '#789482' : '#b88b9a'} />
          <text x='216' y={189 + i * 29} fontSize='10' fill='#67525d'>
            {s}
          </text>
          <text x='394' y={189 + i * 29} fontSize='9' fill='#85948a'>
            {i === 1 ? '待到店' : '已确认'}
          </text>
        </g>
      ))}
      <rect x='480' y='76' width='137' height='192' rx='12' fill='#e9eee7' />
      <text x='494' y='101' fill='#516152' fontSize='12' fontWeight='600'>
        房间负载
      </text>
      <circle cx='548' cy='151' r='31' fill='none' stroke='#d3ded1' strokeWidth='8' />
      <circle
        className={styles.arc}
        cx='548'
        cy='151'
        r='31'
        fill='none'
        stroke='#799681'
        strokeWidth='8'
        strokeLinecap='round'
        strokeDasharray='144 195'
        transform='rotate(-90 548 151)'
      />
      <text x='548' y='157' textAnchor='middle' fill='#506553' fontSize='22' fontFamily='Georgia, serif'>
        74%
      </text>
      <text x='496' y='210' fill='#738275' fontSize='9'>
        房间可用时段
      </text>
      {[0, 1, 2, 3, 4, 5, 6].map(i => (
        <rect
          key={i}
          className={styles.slot}
          x={496 + i * 15}
          y='221'
          width='10'
          height='20'
          rx='3'
          fill={i < 5 ? '#94a992' : '#cfd9cc'}
        />
      ))}
      <rect x='148' y='280' width='469' height='58' rx='12' fill='#fffdfb' />
      {[
        ['本周预约', '128'],
        ['到店率', '92%'],
        ['服务收入', '¥18.6K'],
      ].map(([label, value], i) => (
        <g key={label}>
          {i > 0 && <path d={`M${148 + i * 156} 293V325`} stroke='#ebe1dc' />}
          <text x={164 + i * 156} y='301' fill='#a08a92' fontSize='9'>
            {label}
          </text>
          <text x={164 + i * 156} y='325' fill='#68475b' fontSize='23' fontFamily='Georgia, serif'>
            {value}
          </text>
        </g>
      ))}
    </svg>
  );
}
