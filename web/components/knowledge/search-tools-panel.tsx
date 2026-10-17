import { apiInterceptors, kbCat, kbGlob, kbGrep, kbLsJson, kbSemanticSearch } from '@/client/api';
import CatResultViewer from '@/components/knowledge/cat-result-viewer';
import { ISpace, KbFileEntry } from '@/types/knowledge';
import {
  CodeOutlined,
  FileSearchOutlined,
  FolderOpenOutlined,
  ReadOutlined,
  SearchOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { Button, Input, InputNumber, Spin, Tooltip, message } from 'antd';
import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

type ToolType = 'ls' | 'glob' | 'grep' | 'cat' | 'semantic';

type IProps = {
  space: ISpace;
};

interface ToolConfig {
  key: ToolType;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  descKey: string;
  showQuery: boolean;
  showPath: boolean;
  showFilePattern: boolean;
  showLineRange: boolean;
  showTopK: boolean;
  showLimit: boolean;
}

const TOOLS: ToolConfig[] = [
  {
    key: 'grep',
    icon: <SearchOutlined />,
    color: '#FA8C16',
    bgColor: '#FFF7E6',
    descKey: 'kb_grep_desc',
    showQuery: true,
    showPath: true,
    showFilePattern: true,
    showLineRange: false,
    showTopK: false,
    showLimit: true,
  },
  {
    key: 'semantic',
    icon: <CodeOutlined />,
    color: '#52C41A',
    bgColor: '#F6FFED',
    descKey: 'kb_semantic_desc',
    showQuery: true,
    showPath: false,
    showFilePattern: false,
    showLineRange: false,
    showTopK: true,
    showLimit: false,
  },
  {
    key: 'ls',
    icon: <FolderOpenOutlined />,
    color: '#1677FF',
    bgColor: '#E6F4FF',
    descKey: 'kb_ls_desc',
    showQuery: false,
    showPath: true,
    showFilePattern: false,
    showLineRange: false,
    showTopK: false,
    showLimit: true,
  },
  {
    key: 'glob',
    icon: <FileSearchOutlined />,
    color: '#722ED1',
    bgColor: '#F9F0FF',
    descKey: 'kb_glob_desc',
    showQuery: true,
    showPath: false,
    showFilePattern: false,
    showLineRange: false,
    showTopK: false,
    showLimit: true,
  },
  {
    key: 'cat',
    icon: <ReadOutlined />,
    color: '#13C2C2',
    bgColor: '#E6FFFB',
    descKey: 'kb_cat_desc',
    showQuery: false,
    showPath: true,
    showFilePattern: false,
    showLineRange: true,
    showTopK: false,
    showLimit: false,
  },
];

const TOOL_MAP = Object.fromEntries(TOOLS.map(t => [t.key, t]));

/**
 * Search Tools Panel — redesigned with card-style tool selector and rich result display.
 * ls/glob file entries are clickable and will auto-switch to cat mode.
 */
export default function SearchToolsPanel(props: IProps) {
  const { space } = props;
  const { t: tt } = useTranslation();
  const [tool, setTool] = useState<ToolType>('grep');
  const [query, setQuery] = useState('');
  const [path, setPath] = useState('');
  const [filePattern, setFilePattern] = useState('');
  const [startLine, setStartLine] = useState(1);
  const [endLine, setEndLine] = useState(0);
  const [topK, setTopK] = useState(5);
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [limit, setLimit] = useState(20);
  const [result, setResult] = useState('');
  const [lsEntries, setLsEntries] = useState<KbFileEntry[] | null>(null);
  const [lsPath, setLsPath] = useState('');
  const [loading, setLoading] = useState(false);

  const cfg = TOOL_MAP[tool];

  /** Switch to cat tool and read a specific file */
  const openFile = useCallback(
    (filePath: string) => {
      setTool('cat');
      setPath(filePath);
      setStartLine(1);
      setEndLine(0);
      // Trigger the cat search immediately
      doCatSearch(filePath);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [space.id],
  );

  /** Execute cat search with a given path (used by openFile) */
  const doCatSearch = async (filePath: string) => {
    setLoading(true);
    setResult('');
    setLsEntries(null);
    const spaceId = space.id;
    try {
      const [err, data] = await apiInterceptors(kbCat(spaceId, { path: filePath, start_line: 1, end_line: 0 }));
      if (err) {
        message.error((err as Error).message);
        setResult(`Error: ${(err as Error).message}`);
      } else {
        setResult(data || tt('No_Results'));
      }
    } catch (e: any) {
      message.error(e.message);
      setResult(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    setResult('');
    setLsEntries(null);
    const spaceId = space.id;
    let err: any;
    let data: any;
    try {
      if (tool === 'ls') {
        [err, data] = await apiInterceptors(kbLsJson(spaceId, { path, limit }));
        if (!err && data) {
          setLsEntries(data.entries || []);
          setLsPath(data.path || path);
        }
      } else if (tool === 'glob') {
        [err, data] = await apiInterceptors(kbGlob(spaceId, { query, limit }));
      } else if (tool === 'grep') {
        [err, data] = await apiInterceptors(kbGrep(spaceId, { query, path, file_pattern: filePattern, limit }));
      } else if (tool === 'cat') {
        [err, data] = await apiInterceptors(kbCat(spaceId, { path, start_line: startLine, end_line: endLine }));
      } else if (tool === 'semantic') {
        [err, data] = await apiInterceptors(
          kbSemanticSearch(spaceId, { query, top_k: topK, score_threshold: scoreThreshold }),
        );
      }
      if (err) {
        message.error((err as Error).message);
        setResult(`Error: ${(err as Error).message}`);
      } else {
        setResult(data || tt('No_Results'));
      }
    } catch (e: any) {
      message.error(e.message);
      setResult(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  /** Parse the plain-text result into structured lines for rendering */
  const renderResult = () => {
    if (!result) {
      return (
        <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
          <SearchOutlined style={{ fontSize: 36, marginBottom: 12 }} />
          <p className='text-sm m-0'>{tt('Search_Tools_Empty')}</p>
        </div>
      );
    }

    // For ls results — render from structured JSON entries
    if (tool === 'ls') {
      const entries = lsEntries;
      if (!entries || entries.length === 0) {
        return (
          <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
            <FolderOpenOutlined style={{ fontSize: 36, marginBottom: 12 }} />
            <p className='text-sm m-0'>{tt('No_Results')}</p>
          </div>
        );
      }
      // Sort: directories first, then files, alphabetically
      const sorted = [...entries].sort((a, b) => {
        if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return (
        <div className='font-mono text-[13px] leading-relaxed'>
          {lsPath && (
            <div className='flex items-center gap-2 text-gray-500 dark:text-gray-400 font-semibold text-xs uppercase tracking-wider py-1.5 border-b border-gray-200 dark:border-gray-700 mb-1'>
              <FolderOpenOutlined style={{ fontSize: 12 }} />
              {lsPath}/
            </div>
          )}
          {sorted.map((entry, i) => {
            if (entry.is_dir) {
              return (
                <div
                  key={i}
                  className='flex items-center gap-2 py-1 px-2 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors cursor-pointer group'
                  onClick={() => {
                    setPath(entry.path);
                    setTool('ls');
                    // Trigger ls search on the new directory
                    setTimeout(() => handleSearch(), 0);
                  }}
                >
                  <FolderOpenOutlined style={{ color: '#1677FF', fontSize: 14 }} />
                  <span className='text-blue-600 dark:text-blue-400 font-medium group-hover:underline'>
                    {entry.name}/
                  </span>
                  {entry.child_count != null && (
                    <span className='text-gray-400 text-xs ml-auto'>{entry.child_count} items</span>
                  )}
                </div>
              );
            }
            return (
              <div
                key={i}
                className='flex items-center gap-2 py-1 px-2 rounded hover:bg-teal-50 dark:hover:bg-teal-900/10 transition-colors cursor-pointer group'
                onClick={() => openFile(entry.path)}
                title={tt('kb_cat_desc' as any) || `Read ${entry.name}`}
              >
                <ReadOutlined style={{ color: '#13C2C2', fontSize: 13 }} />
                <span className='text-gray-800 dark:text-gray-200 group-hover:text-teal-600 dark:group-hover:text-teal-400 group-hover:underline'>
                  {entry.name}
                </span>
                {entry.language && (
                  <span className='ml-auto text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'>
                    {entry.language}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    // For glob results — render as a file listing with icons; files are clickable
    if (tool === 'glob') {
      const lines = result.split('\n').filter(Boolean);
      return (
        <div className='font-mono text-[13px] leading-relaxed'>
          {lines.map((line, i) => {
            const isDir = line.trim().endsWith('/');
            const isHeader = line.startsWith('Directory:') || line.startsWith('Matching');
            if (isHeader) {
              return (
                <div
                  key={i}
                  className='text-gray-500 dark:text-gray-400 font-semibold text-xs uppercase tracking-wider py-1.5 border-b border-gray-200 dark:border-gray-700 mb-1'
                >
                  {line.trim()}
                </div>
              );
            }
            if (isDir) {
              const parts = line.trim().split('\t');
              const dirName = parts[0]?.replace(/\/$/, '') || '';
              const dirPath = dirName; // For ls, the directory name IS the path for sub-navigation
              return (
                <div
                  key={i}
                  className='flex items-center gap-2 py-1 px-2 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors cursor-pointer group'
                  onClick={() => {
                    // Navigate into directory: set path and re-run ls
                    setPath(dirPath);
                    setTool('ls');
                    setTimeout(() => handleSearch(), 0);
                  }}
                >
                  <FolderOpenOutlined style={{ color: '#1677FF', fontSize: 14 }} />
                  <span className='text-blue-600 dark:text-blue-400 font-medium group-hover:underline'>{dirName}/</span>
                  {parts[1] && <span className='text-gray-400 text-xs ml-auto'>{parts[1]}</span>}
                </div>
              );
            }
            // File entry — split name and language tag
            const parts = line.trim().split('\t');
            const fileName = parts[0]?.replace(/^\s+/, '') || '';
            const lang = parts[1] || '';
            return (
              <div
                key={i}
                className='flex items-center gap-2 py-1 px-2 rounded hover:bg-teal-50 dark:hover:bg-teal-900/10 transition-colors cursor-pointer group'
                onClick={() => openFile(fileName)}
                title={tt('kb_cat_desc' as any) || `Read ${fileName}`}
              >
                <ReadOutlined style={{ color: '#13C2C2', fontSize: 13 }} />
                <span className='text-gray-800 dark:text-gray-200 group-hover:text-teal-600 dark:group-hover:text-teal-400 group-hover:underline'>
                  {fileName}
                </span>
                {lang && (
                  <span className='ml-auto text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'>
                    {lang}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    // For grep results — render with file path headers and highlighted line numbers
    if (tool === 'grep') {
      const lines = result.split('\n').filter(Boolean);
      return (
        <div className='font-mono text-[13px] leading-relaxed'>
          {lines.map((line, i) => {
            const isHeader = line.startsWith("'") && line.includes('matched');
            if (isHeader) {
              return (
                <div
                  key={i}
                  className='flex items-center gap-2 text-amber-700 dark:text-amber-400 font-semibold text-xs py-2 border-b border-gray-200 dark:border-gray-700 mb-1'
                >
                  <SearchOutlined style={{ fontSize: 12 }} />
                  {line.trim()}
                </div>
              );
            }
            // File path header (ends with ":" and not indented)
            if (line.trim().endsWith(':') && !line.trim().startsWith(' ')) {
              const filePath = line.trim().replace(/:$/, '');
              return (
                <div
                  key={i}
                  className='flex items-center gap-1.5 text-blue-600 dark:text-blue-400 font-semibold mt-3 mb-1 px-1 text-[12px] cursor-pointer hover:underline'
                  onClick={() => openFile(filePath)}
                  title={tt('kb_cat_desc' as any) || `Read ${filePath}`}
                >
                  <ReadOutlined style={{ fontSize: 12 }} />
                  {filePath}
                </div>
              );
            }
            // Matched line with line number (format: "  123 | code" or "  123: code")
            const match = line.match(/^\s*(\d+)[|:]\s*(.*)/);
            if (match) {
              return (
                <div key={i} className='flex hover:bg-amber-50/50 dark:hover:bg-amber-900/10 transition-colors rounded'>
                  <span className='w-10 text-right pr-2 text-amber-500 dark:text-amber-400 select-none flex-shrink-0 text-[12px]'>
                    {match[1]}
                  </span>
                  <span className='text-gray-800 dark:text-gray-200 whitespace-pre flex-1 min-w-0'>{match[2]}</span>
                </div>
              );
            }
            return (
              <div key={i} className='text-gray-700 dark:text-gray-300 whitespace-pre px-1'>
                {line}
              </div>
            );
          })}
        </div>
      );
    }

    // For cat results — render using the shared CatResultViewer component
    if (tool === 'cat') {
      return <CatResultViewer content={result} />;
    }

    // For semantic search results — render as markdown-like chunks
    if (tool === 'semantic') {
      const sections = result.split(/---\n/);
      return (
        <div className='space-y-3'>
          {sections.map((section, i) => {
            const lines = section.trim().split('\n');
            if (lines.length === 0) return null;
            // First line might be the header
            const headerMatch = lines[0].match(/^###\s+(.+)/);
            const header = headerMatch ? headerMatch[1] : null;
            const contentStart = headerMatch ? 1 : 0;
            const content = lines.slice(contentStart).join('\n').trim();
            return (
              <div
                key={i}
                className='rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/50 p-3'
              >
                {header && (
                  <div className='text-xs font-semibold text-green-600 dark:text-green-400 mb-2 flex items-center gap-1.5'>
                    <CodeOutlined />
                    {header}
                  </div>
                )}
                {content && (
                  <pre className='text-[13px] text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono m-0 leading-relaxed'>
                    {content}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    // Fallback: plain text
    return (
      <pre className='text-[13px] text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono m-0 leading-relaxed'>
        {result}
      </pre>
    );
  };

  return (
    <div className='flex flex-col h-full'>
      {/* Tool selector — card-style tabs */}
      <div className='flex gap-2 mb-4 flex-wrap'>
        {TOOLS.map(t => {
          const active = tool === t.key;
          return (
            <Tooltip key={t.key} title={tt(t.descKey as any) || t.key}>
              <button
                onClick={() => {
                  setTool(t.key);
                  setLsEntries(null);
                  setResult('');
                }}
                className={`
                  flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all border
                  ${
                    active
                      ? 'border-transparent shadow-sm text-white'
                      : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-500'
                  }
                `}
                style={active ? { backgroundColor: t.color } : undefined}
              >
                <span className='text-base'>{t.icon}</span>
                <span>{tt(t.key as any) || t.key}</span>
              </button>
            </Tooltip>
          );
        })}
      </div>

      {/* Search inputs */}
      <div className='flex flex-wrap gap-3 mb-4 items-end'>
        {cfg.showQuery && (
          <div className='flex flex-col'>
            <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('Search_Query')}</span>
            <Input
              className='w-[300px]'
              placeholder={tool === 'semantic' ? 'natural language query...' : 'keyword or pattern...'}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </div>
        )}
        {cfg.showPath && (
          <div className='flex flex-col'>
            <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('File_Path')}</span>
            <Input
              className='w-[240px]'
              placeholder='src/auth/login.py or dir/'
              value={path}
              onChange={e => setPath(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </div>
        )}
        {cfg.showFilePattern && (
          <div className='flex flex-col'>
            <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('File_Pattern')}</span>
            <Input
              className='w-[160px]'
              placeholder='*.py'
              value={filePattern}
              onChange={e => setFilePattern(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </div>
        )}
        {cfg.showLineRange && (
          <>
            <div className='flex flex-col'>
              <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('Start_Line')}</span>
              <InputNumber className='w-[100px]' min={1} value={startLine} onChange={v => setStartLine(v || 1)} />
            </div>
            <div className='flex flex-col'>
              <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('End_Line')}</span>
              <InputNumber className='w-[100px]' min={0} value={endLine} onChange={v => setEndLine(v || 0)} />
            </div>
          </>
        )}
        {cfg.showTopK && (
          <>
            <div className='flex flex-col'>
              <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('Top_K')}</span>
              <InputNumber className='w-[100px]' min={1} max={50} value={topK} onChange={v => setTopK(v || 5)} />
            </div>
            <div className='flex flex-col'>
              <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>{tt('Score_Threshold')}</span>
              <InputNumber
                className='w-[120px]'
                min={0}
                max={1}
                step={0.1}
                value={scoreThreshold}
                onChange={v => setScoreThreshold(v || 0)}
              />
            </div>
          </>
        )}
        {cfg.showLimit && (
          <div className='flex flex-col'>
            <span className='text-xs text-gray-500 dark:text-gray-400 mb-1'>Limit</span>
            <InputNumber className='w-[100px]' min={1} max={500} value={limit} onChange={v => setLimit(v || 20)} />
          </div>
        )}
        <Button
          type='primary'
          loading={loading}
          onClick={handleSearch}
          size='large'
          icon={<SendOutlined />}
          style={cfg ? { backgroundColor: cfg.color, borderColor: cfg.color } : undefined}
        >
          {tt('Search')}
        </Button>
      </div>

      {/* Results */}
      <div className='flex-1 overflow-auto rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-[#1a1d2e]'>
        <Spin spinning={loading}>
          <div className='p-4 min-h-[200px] max-h-[500px] overflow-auto'>{renderResult()}</div>
        </Spin>
      </div>
    </div>
  );
}
