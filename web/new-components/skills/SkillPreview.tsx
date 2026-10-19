import { getSkillPresentation } from './skill-catalog';
import SpaTemplatePreview from './SpaTemplatePreview';

/** Original vector examples. Values illustrate a design, never a source query. */
export default function SkillPreview({ name, description }: { name: string; description?: string }) {
  const p = getSkillPresentation({ name, description });
  if (p.variant === 'spa') return <SpaTemplatePreview />;
  const soft = p.variant === 'pet' || p.variant === 'learning';
  const poster = p.variant === 'poster';
  const stroke = soft || poster ? p.ink : '#dedfe9';
  const radius = poster ? 0 : soft ? 14 : 9;
  const box = (x: number, y: number, w: number, h: number, fill = '#fff') => (
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={radius}
      fill={fill}
      stroke={stroke}
      strokeWidth={soft || poster ? 2 : 1}
    />
  );
  const label = (x: number, y: number, value: string, size = 12, color = p.ink, weight = 500) => (
    <text x={x} y={y} fontSize={size} fill={color} fontWeight={weight}>
      {value}
    </text>
  );
  const line = (x: number, y: number, width: number, height: number, color = p.accent) => {
    const samples = [0.18, 0.34, 0.27, 0.43, 0.39, 0.63, 0.51, 0.67, 0.62, 0.88, 0.8, 0.95];
    const points = samples.map((v, i) => `${x + (i * width) / 11},${y + height * (1 - v)}`).join(' ');
    return (
      <g>
        <polygon points={`${x},${y + height} ${points} ${x + width},${y + height}`} fill={color} opacity='.09' />
        <polyline points={points} fill='none' stroke={color} strokeWidth='3' strokeLinejoin='round' />
      </g>
    );
  };
  const bars = (x: number, y: number, width: number, height: number) => (
    <g>
      {[0.4, 0.65, 0.52, 0.75, 0.62, 0.88, 0.7, 0.95].map((v, i) => (
        <rect
          key={i}
          x={x + (i * width) / 8}
          y={y + height * (1 - v)}
          width={width / 12}
          height={height * v}
          rx={poster ? 0 : 3}
          fill={p.accent}
          opacity={i % 3 === 0 ? 1 : 0.55}
        />
      ))}
    </g>
  );
  const heading =
    p.variant === 'charts'
      ? 'CHART EXPLORER'
      : p.variant === 'growth'
        ? 'GROWTH OVERVIEW'
        : p.variant === 'workspace'
          ? 'AGENT WORKSPACE'
          : p.variant === 'learning'
            ? 'LEARNING JOURNEY'
            : p.variant === 'pet'
              ? 'PAW & CARE'
              : p.variant === 'spa'
                ? 'SERENITY STUDIO'
                : 'CAMPAIGN / 01';
  return (
    <svg
      viewBox='0 0 640 360'
      width='100%'
      role='img'
      aria-label={`${p.title}风格示意，非业务数据`}
      style={{ display: 'block', background: p.background, fontFamily: 'inherit' }}
    >
      <rect width='640' height='360' fill={p.background} />
      <circle cx='35' cy='31' r='9' fill={p.accent} />
      <circle cx='35' cy='31' r='3' fill='white' />
      {label(55, 36, heading, 13, p.ink, 700)}
      <rect x='511' y='21' width='103' height='22' rx='11' fill={p.accent} opacity='.1' />
      {label(526, 36, 'DESIGN SAMPLE', 8, p.ink)}
      {p.variant === 'charts' ? (
        <>
          {box(24, 60, 288, 126)}
          {box(326, 60, 290, 126)}
          {box(24, 200, 288, 134)}
          {box(326, 200, 290, 134)}
          {label(40, 81, '趋势 · 时间序列', 11)}
          {line(42, 95, 245, 65)}
          {label(343, 81, '比较 · 分类构成', 11)}
          {bars(349, 95, 235, 69)}
          {label(40, 224, '构成 · 比例', 11)}
          <circle cx='105' cy='276' r='36' fill='none' stroke='#e3e5f2' strokeWidth='15' />
          <circle
            cx='105'
            cy='276'
            r='36'
            fill='none'
            stroke={p.accent}
            strokeWidth='15'
            strokeDasharray='142 84'
            transform='rotate(-90 105 276)'
          />
          {[0, 1, 2].map(i => (
            <g key={i}>
              <rect x='167' y={246 + i * 22} width='8' height='8' rx='2' fill={p.accent} opacity={1 - i * 0.25} />
              <rect x='184' y={247 + i * 22} width={75 - i * 12} height='5' rx='2' fill='#c6cad9' />
            </g>
          ))}
          {label(343, 224, '分布 · 相关性', 11)}
          {Array.from({ length: 25 }, (_, i) => (
            <circle
              key={i}
              cx={352 + ((i * 43) % 234)}
              cy={244 + ((i * 17) % 66)}
              r={3 + (i % 4)}
              fill={p.accent}
              opacity='.55'
            />
          ))}
        </>
      ) : p.variant === 'workspace' ? (
        <>
          {box(24, 60, 212, 274)}
          {label(42, 86, '任务队列', 15, p.ink, 700)}
          {['数据同步', '报表生成', '质量校验', '消息汇总'].map((s, i) => (
            <g key={s}>
              <rect x='38' y={101 + i * 52} width='184' height='42' rx='7' fill={i === 1 ? '#e9e7fa' : '#f6f7fa'} />
              <circle cx='52' cy={122 + i * 52} r='4' fill={i === 1 ? p.accent : '#6c9f8c'} />
              {label(66, 119 + i * 52, s, 11)}
              {label(66, 133 + i * 52, i === 1 ? '运行中' : '已完成', 8, '#6c7484')}
            </g>
          ))}
          {box(250, 60, 366, 133)}
          {label(268, 86, '自动化工作流', 14, p.ink, 700)}
          <path d='M 314 134 H 562' stroke='#bab8d9' strokeWidth='2' />
          {['读取', '分析', '交付'].map((s, i) => (
            <g key={s}>
              {box(270 + i * 110, 110, 94, 49, i === 1 ? '#efedfc' : '#fff')}
              {label(299 + i * 110, 139, s, 11)}
            </g>
          ))}
          {box(250, 207, 366, 127)}
          {label(268, 232, '任务吞吐', 11)}
          {line(273, 247, 315, 66)}
        </>
      ) : poster ? (
        <>
          {box(24, 62, 350, 272, '#efce53')}
          {label(43, 108, '让每次', 36, p.ink, 900)}
          {label(43, 154, '投入有数。', 44, p.ink, 900)}
          <path d='M 48 185 H 348' stroke={p.ink} strokeWidth='3' />
          {label(44, 219, 'CAMPAIGN REACH', 11, p.ink, 700)}
          {label(44, 293, '28.6K', 60, p.ink, 900)}
          {box(388, 62, 228, 127, '#e45b4e')}
          {label(407, 90, '活动表现', 14, '#fff', 700)}
          {label(407, 155, '+24.8%', 37, '#fff', 800)}
          {box(388, 204, 228, 130)}
          {bars(409, 231, 184, 81)}
        </>
      ) : p.variant === 'learning' ? (
        <>
          {box(24, 60, 592, 78, '#f5dfc7')}
          {label(43, 92, '每一步，都看得见', 21, p.ink, 700)}
          {label(43, 116, '课程进度与学习表现', 11)}
          {box(24, 153, 350, 181)}
          {label(42, 180, '课程进度', 14, p.ink, 700)}
          {['数据基础', '可视化设计', '实践项目'].map((s, i) => (
            <g key={s}>
              {label(43, 208 + i * 46, s, 11)}
              <rect x='128' y={196 + i * 46} width='220' height='14' rx='7' fill='#e9ece4' />
              <rect
                x='128'
                y={196 + i * 46}
                width={193 - i * 38}
                height='14'
                rx='7'
                fill={i === 1 ? '#86b4d2' : p.accent}
              />
            </g>
          ))}
          {box(390, 153, 226, 181, '#e4edf4')}
          {label(410, 181, '本期完成', 12)}
          {label(410, 232, '86%', 40, p.ink, 700)}
          {line(410, 251, 180, 58)}
        </>
      ) : p.variant === 'pet' ? (
        <>
          {[
            ['本周预约', '128'],
            ['到店率', '92%'],
            ['服务收入', '¥18.6K'],
          ].map((v, i) => (
            <g key={v[0]}>
              {box(24 + i * 201, 60, 190, 83, i === 0 ? (p.variant === 'pet' ? '#ffdec0' : '#eee5d8') : '#fff')}
              {label(41 + i * 201, 84, v[0], 11)}
              {label(41 + i * 201, 120, v[1], 26, p.ink, 650)}
            </g>
          ))}
          {box(24, 159, 348, 175)}
          {label(42, 185, p.variant === 'pet' ? '今日服务安排' : '预约与房间安排', 14, p.ink, 700)}
          {['09:30', '10:00', '11:30'].map((s, i) => (
            <g key={s}>
              <line x1='42' y1={197 + i * 41} x2='353' y2={197 + i * 41} stroke='#e7e0d8' />
              {label(42, 221 + i * 41, s, 11)}
              {label(
                106,
                221 + i * 41,
                p.variant === 'pet' ? ['基础洗护', '造型护理', '洗护套餐'][i] : ['舒缓护理', '会员预约', '精油护理'][i],
                11,
              )}
              <rect x='274' y={208 + i * 41} width='64' height='19' rx='9' fill={i === 1 ? '#f5e3d2' : '#e0eee8'} />
              {label(286, 221 + i * 41, i === 1 ? '待到店' : '已确认', 9)}
            </g>
          ))}
          {box(388, 159, 228, 175)}
          {label(406, 185, '服务结构', 12)}
          {bars(409, 203, 187, 105)}
        </>
      ) : (
        <>
          {[
            ['本期客户', '12.8K'],
            ['转化率', '24.6%'],
            ['留存率', '68.2%'],
          ].map((v, i) => (
            <g key={v[0]}>
              {box(24 + i * 201, 60, 190, 81)}
              {label(41 + i * 201, 84, v[0], 11)}
              {label(41 + i * 201, 117, v[1], 27, p.ink, 650)}
            </g>
          ))}
          {box(24, 155, 369, 179)}
          {label(42, 181, '增长趋势', 12)}
          {line(45, 204, 324, 103)}
          {box(407, 155, 209, 179)}
          {label(425, 181, '转化路径', 12)}
          {[0, 1, 2, 3].map(i => (
            <g key={i}>
              <rect
                x={429 + i * 13}
                y={197 + i * 30}
                width={164 - i * 26}
                height='23'
                rx='3'
                fill={p.accent}
                opacity={1 - i * 0.16}
              />
              {label(487, 213 + i * 30, ['访问', '注册', '激活', '付费'][i], 9, '#fff')}
            </g>
          ))}
        </>
      )}
    </svg>
  );
}
