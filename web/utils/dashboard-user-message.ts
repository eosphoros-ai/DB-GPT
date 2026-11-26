/** Display a dashboard control request without exposing its transport marker. */
export function dashboardUserDisplayText(text: string, labels: { confirm: string; revise: string }): string {
  const match = text.match(
    /^(?:\[Database:[^\]]+\]\s*)?\[\[(confirm|revise)-dashboard(?:-plan)?:[^\]]+\]\]\s*([\s\S]*)$/,
  );
  if (!match) return text;
  if (match[1] === 'confirm') return labels.confirm;
  const detail = match[2].replace(/^Revise this dashboard plan at expected revision \d+ as follows:\s*/i, '').trim();
  return detail ? `${labels.revise}：${detail}` : labels.revise;
}
