import { Alert, Input } from 'antd';
import { useEffect, useState } from 'react';

interface JsonTextAreaProps {
  label: string;
  value: unknown;
  rows?: number;
  onCommit: (value: unknown) => void;
}

const format = (value: unknown) => JSON.stringify(value ?? null, null, 2);

export default function JsonTextArea({ label, value, rows = 4, onCommit }: JsonTextAreaProps) {
  const [draft, setDraft] = useState(() => format(value));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Keep this local editing buffer synchronized with its controlled value.
    setDraft(format(value));
  }, [value]);

  const commit = () => {
    try {
      onCommit(JSON.parse(draft));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'JSON 格式不正确');
    }
  };

  return (
    <label className='block text-xs text-gray-500'>
      {label}
      <Input.TextArea
        className='font-mono text-xs'
        rows={rows}
        value={draft}
        onChange={event => setDraft(event.target.value)}
        onBlur={commit}
      />
      {error && <Alert className='mt-1' type='error' showIcon message={error} />}
    </label>
  );
}
