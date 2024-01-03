import { format } from 'sql-formatter';
import { CodePreview } from './code-preview';

interface Props {
  data: {
    display_type: string;
    sql: string;
    thought: string;
  };
}

function VisConvertError({ data }: Props) {
  return (
    <div className="rounded overflow-hidden">
      <div className="p-3 text-white bg-red-500 whitespace-normal">{data.display_type}</div>
      <div className="p-3 bg-red-50">
        <div className="mb-2 whitespace-normal">{data.thought}</div>
        <CodePreview code={format(data.sql)} language="sql" />
      </div>
    </div>
  );
}

export default VisConvertError;
