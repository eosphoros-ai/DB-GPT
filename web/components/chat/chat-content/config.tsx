import { LinkOutlined, ReadOutlined, SyncOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import { Table, Image, Tag, Tabs, TabsProps, Popover } from 'antd';
import { format } from 'sql-formatter';
import { Reference } from '@/types/chat';
import { AutoChart, BackEndChartType, getChartType } from '@/components/chart';
import { CodePreview } from './code-preview';
import { Datum } from '@antv/ava';
import rehypeRaw from 'rehype-raw';
import { IChunk } from '@/types/knowledge';
import AgentPlans from './agent-plans';
import AgentMessages from './agent-messages';
import VisConvertError from './vis-convert-error';
import VisChart from './vis-chart';
import VisDashboard from './vis-dashboard';
import VisPlugin from './vis-plugin';
import VisCode from './vis-code';

type MarkdownComponent = Parameters<typeof ReactMarkdown>['0']['components'];

const customeTags: (keyof JSX.IntrinsicElements)[] = ['custom-view', 'chart-view', 'references', 'summary'];

function matchCustomeTagValues(context: string) {
  const matchValues = customeTags.reduce<string[]>((acc, tagName) => {
    const tagReg = new RegExp(`<${tagName}[^>]*\/?>`, 'gi');
    context = context.replace(tagReg, (matchVal) => {
      acc.push(matchVal);
      return '';
    });
    return acc;
  }, []);
  return { context, matchValues };
}

const basicComponents: MarkdownComponent = {
  code({ inline, node, className, children, style, ...props }) {
    const content = String(children);
    /**
     * @description
     * In some cases, tags are nested within code syntax,
     * so it is necessary to extract the tags present in the code block and render them separately.
     */
    const { context, matchValues } = matchCustomeTagValues(content);
    const lang = className?.replace('language-', '') || 'javascript';

    if (lang === 'agent-plans') {
      try {
        const data = JSON.parse(content) as Parameters<typeof AgentPlans>[0]['data'];
        return <AgentPlans data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'agent-messages') {
      try {
        const data = JSON.parse(content) as Parameters<typeof AgentMessages>[0]['data'];
        return <AgentMessages data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'vis-convert-error') {
      try {
        const data = JSON.parse(content) as Parameters<typeof VisConvertError>[0]['data'];
        return <VisConvertError data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'vis-dashboard') {
      try {
        const data = JSON.parse(content) as Parameters<typeof VisDashboard>[0]['data'];
        return <VisDashboard data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'vis-chart') {
      try {
        const data = JSON.parse(content) as Parameters<typeof VisChart>[0]['data'];
        return <VisChart data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'vis-plugin') {
      try {
        const data = JSON.parse(content) as Parameters<typeof VisPlugin>[0]['data'];
        return <VisPlugin data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    if (lang === 'vis-code') {
      try {
        const data = JSON.parse(content) as Parameters<typeof VisCode>[0]['data'];
        return <VisCode data={data} />;
      } catch (e) {
        return <CodePreview language={lang} code={content} />;
      }
    }

    return (
      <>
        {!inline ? (
          <CodePreview code={context} language={lang} />
        ) : (
          <code {...props} style={style} className="p-1 mx-1 rounded bg-theme-light dark:bg-theme-dark text-sm">
            {children}
          </code>
        )}
        <ReactMarkdown components={markdownComponents} rehypePlugins={[rehypeRaw]}>
          {matchValues.join('\n')}
        </ReactMarkdown>
      </>
    );
  },
  ul({ children }) {
    return <ul className="py-1">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="py-1">{children}</ol>;
  },
  li({ children, ordered }) {
    return <li className={`text-sm leading-7 ml-5 pl-2 text-gray-600 dark:text-gray-300 ${ordered ? 'list-decimal' : 'list-disc'}`}>{children}</li>;
  },
  table({ children }) {
    return (
      <table className="my-2 rounded-tl-md rounded-tr-md max-w-full bg-white dark:bg-gray-800 text-sm rounded-lg overflow-hidden">{children}</table>
    );
  },
  thead({ children }) {
    return <thead className="bg-[#fafafa] dark:bg-black font-semibold">{children}</thead>;
  },
  th({ children }) {
    return <th className="!text-left p-4">{children}</th>;
  },
  td({ children }) {
    return <td className="p-4 border-t border-[#f0f0f0] dark:border-gray-700">{children}</td>;
  },
  h1({ children }) {
    return <h3 className="text-2xl font-bold my-4 border-b border-slate-300 pb-4">{children}</h3>;
  },
  h2({ children }) {
    return <h3 className="text-xl font-bold my-3">{children}</h3>;
  },
  h3({ children }) {
    return <h3 className="text-lg font-semibold my-2">{children}</h3>;
  },
  h4({ children }) {
    return <h3 className="text-base font-semibold my-1">{children}</h3>;
  },
  a({ children, href }) {
    return (
      <div className="inline-block text-blue-600 dark:text-blue-400">
        <LinkOutlined className="mr-1" />
        <a href={href} target="_blank">
          {children}
        </a>
      </div>
    );
  },
  img({ src, alt }) {
    return (
      <div>
        <Image
          className="min-h-[1rem] max-w-full max-h-full border rounded"
          src={src}
          alt={alt}
          placeholder={
            <Tag icon={<SyncOutlined spin />} color="processing">
              Image Loading...
            </Tag>
          }
          fallback="/images/fallback.png"
        />
      </div>
    );
  },
  blockquote({ children }) {
    return (
      <blockquote className="py-4 px-6 border-l-4 border-blue-600 rounded bg-white my-2 text-gray-500 dark:bg-slate-800 dark:text-gray-200 dark:border-white shadow-sm">
        {children}
      </blockquote>
    );
  },
};

const extraComponents: MarkdownComponent = {
  'chart-view': function ({ content, children }) {
    let data: {
      data: Datum[];
      type: BackEndChartType;
      sql: string;
    };
    try {
      data = JSON.parse(content as string);
    } catch (e) {
      console.log(e, content);
      data = {
        type: 'response_table',
        sql: '',
        data: [],
      };
    }

    const columns = data?.data?.[0]
      ? Object.keys(data?.data?.[0])?.map((item) => {
          return {
            title: item,
            dataIndex: item,
            key: item,
          };
        })
      : [];

    const ChartItem = {
      key: 'chart',
      label: 'Chart',
      children: <AutoChart data={data?.data} chartType={getChartType(data?.type)} />,
    };
    const SqlItem = {
      key: 'sql',
      label: 'SQL',
      children: <CodePreview code={format(data?.sql, { language: 'mysql' }) as string} language={'sql'} />,
    };
    const DataItem = {
      key: 'data',
      label: 'Data',
      children: <Table dataSource={data?.data} columns={columns} />,
    };
    const TabItems: TabsProps['items'] = data?.type === 'response_table' ? [DataItem, SqlItem] : [ChartItem, SqlItem, DataItem];

    return (
      <div>
        <Tabs defaultActiveKey={data?.type === 'response_table' ? 'data' : 'chart'} items={TabItems} size="small" />
        {children}
      </div>
    );
  },
  references: function ({ title, references, children }) {
    let referenceData;
    // Low version compatibility, read data from children
    if (children) {
      try {
        referenceData = JSON.parse(children as string);
        title = referenceData.title;
        references = referenceData.references;
      } catch (error) {
        console.log('parse references failed', error);
        return <p className="text-sm text-red-500">Render Reference Error!</p>;
      }
    } else {
      // new version, read from tag props.
      try {
        references = JSON.parse(references as string);
      } catch (error) {
        console.log('parse references failed', error);
        return <p className="text-sm text-red-500">Render Reference Error!</p>;
      }
    }
    if (!references || references?.length < 1) {
      return null;
    }
    return (
      <div className="border-t-[1px] border-gray-300 mt-3 py-2">
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
          <LinkOutlined className="mr-2" />
          <span className="font-semibold">{title}</span>
        </p>
        {references.map((reference: Reference, index: number) => (
          <div key={`file_${index}`} className="text-sm font-normal block ml-2 h-6 leading-6 overflow-hidden">
            <span className="inline-block w-6">[{index + 1}]</span>
            <span className="mr-2 lg:mr-4 text-blue-400">{reference.name}</span>
            {reference?.chunks?.map((chunk: IChunk | number, index) => (
              <span key={`chunk_${index}`}>
                {typeof chunk === 'object' ? (
                  <Popover
                    content={
                      <div className="max-w-4xl">
                        <p className="mt-2 font-bold mr-2 border-t border-gray-500 pt-2">Content:</p>
                        <p>{chunk?.content || 'No Content'}</p>
                        <p className="mt-2 font-bold mr-2 border-t border-gray-500 pt-2">MetaData:</p>
                        <p>{chunk?.meta_info || 'No MetaData'}</p>
                        <p className="mt-2 font-bold mr-2 border-t border-gray-500 pt-2">Score:</p>
                        <p>{chunk?.recall_score || ''}</p>
                      </div>
                    }
                    title="Chunk Information"
                  >
                    <span className="cursor-pointer text-blue-500 ml-2" key={`chunk_content_${chunk?.id}`}>
                      {chunk?.id}
                    </span>
                  </Popover>
                ) : (
                  <span className="cursor-pointer text-blue-500 ml-2" key={`chunk_id_${chunk}`}>
                    {chunk}
                  </span>
                )}
                {index < reference?.chunks.length - 1 && <span key={`chunk_comma_${index}`}>,</span>}
              </span>
            ))}
          </div>
        ))}
      </div>
    );
  },
  summary: function ({ children }) {
    return (
      <div>
        <p className="mb-2">
          <ReadOutlined className="mr-2" />
          <span className="font-semibold">Document Summary</span>
        </p>
        <div>{children}</div>
      </div>
    );
  },
};

const markdownComponents = {
  ...basicComponents,
  ...extraComponents,
};

export default markdownComponents;
