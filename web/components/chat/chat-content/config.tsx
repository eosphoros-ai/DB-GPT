import { AutoChart, BackEndChartType, getChartType } from '@/components/chart';
import { formatSql } from '@/utils';
import { LinkOutlined, ReadOutlined, SyncOutlined } from '@ant-design/icons';
import { Datum } from '@antv/ava';
import { GPTVis, withDefaultChartCode } from '@antv/gpt-vis';
import { Image, Table, Tabs, TabsProps, Tag } from 'antd';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import ReferencesContent from './ReferencesContent';
import VisAppLink from './VisAppLink';
import VisChatLink from './VisChatLink';
import VisResponse from './VisResponse';
import AgentMessages from './agent-messages';
import AgentPlans from './agent-plans';
import { CodePreview } from './code-preview';
import VisChart from './vis-chart';
import VisCode from './vis-code';
import VisConvertError from './vis-convert-error';
import VisDashboard from './vis-dashboard';
import VisPlugin from './vis-plugin';

type MarkdownComponent = Parameters<typeof GPTVis>['0']['components'];

const customeTags: (keyof JSX.IntrinsicElements)[] = ['custom-view', 'chart-view', 'references', 'summary'];

function matchCustomeTagValues(context: string) {
  const matchValues = customeTags.reduce<string[]>((acc, tagName) => {
    // eslint-disable-next-line no-useless-escape
    const tagReg = new RegExp(`<${tagName}[^>]*\/?>`, 'gi');
    context = context.replace(tagReg, matchVal => {
      acc.push(matchVal);
      return '';
    });
    return acc;
  }, []);
  return { context, matchValues };
}

const codeComponents = {
  /**
   * @description
   * Custom code block rendering, which can be used to render custom components in the code block.
   * Is it defined in gpt-vis, and the default rendering contains `vis-chart`.
   */
  code: withDefaultChartCode({
    languageRenderers: {
      'agent-plans': ({ className, children }) => {
        const content = String(children);
        /**
         * @description
         * In some cases, tags are nested within code syntax,
         * so it is necessary to extract the tags present in the code block and render them separately.
         */
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof AgentPlans>[0]['data'];
          return <AgentPlans data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'agent-messages': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof AgentMessages>[0]['data'];
          return <AgentMessages data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-convert-error': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisConvertError>[0]['data'];
          return <VisConvertError data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-dashboard': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisDashboard>[0]['data'];
          return <VisDashboard data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-chart': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisChart>[0]['data'];
          return <VisChart data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-plugin': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisPlugin>[0]['data'];
          return <VisPlugin data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-code': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';

        try {
          const data = JSON.parse(content) as Parameters<typeof VisCode>[0]['data'];
          return <VisCode data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-app-link': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisAppLink>[0]['data'];
          return <VisAppLink data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
      'vis-api-response': ({ className, children }) => {
        const content = String(children);
        const lang = className?.replace('language-', '') || 'javascript';
        try {
          const data = JSON.parse(content) as Parameters<typeof VisResponse>[0]['data'];
          return <VisResponse data={data} />;
        } catch {
          return <CodePreview language={lang} code={content} />;
        }
      },
    },
    defaultRenderer({ node, className, children, style, ...props }) {
      const content = String(children);
      const lang = className?.replace('language-', '') || '';
      const { context, matchValues } = matchCustomeTagValues(content);

      return (
        <>
          {lang ? (
            <CodePreview code={context} language={lang || 'javascript'} />
          ) : (
            <code {...props} style={style} className='p-1 mx-1 rounded bg-theme-light dark:bg-theme-dark text-sm'>
              {children}
            </code>
          )}
          <GPTVis components={markdownComponents} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]}>
            {matchValues.join('\n')}
          </GPTVis>
        </>
      );
    },
  }),
};

const basicComponents: MarkdownComponent = {
  ...codeComponents,
  ul({ children }) {
    return <ul className='py-1'>{children}</ul>;
  },
  ol({ children }) {
    return <ol className='py-1'>{children}</ol>;
  },
  li({ children, ordered }) {
    return (
      <li
        className={`text-sm leading-7 ml-5 pl-2 text-gray-600 dark:text-gray-300 ${
          ordered ? 'list-decimal' : 'list-disc'
        }`}
      >
        {children}
      </li>
    );
  },
  table({ children }) {
    return (
      <table className='my-2 rounded-tl-md rounded-tr-md  bg-white dark:bg-gray-800 text-sm rounded-lg overflow-hidden'>
        {children}
      </table>
    );
  },
  thead({ children }) {
    return <thead className='bg-[#fafafa] dark:bg-black font-semibold'>{children}</thead>;
  },
  th({ children }) {
    return <th className='!text-left p-4'>{children}</th>;
  },
  td({ children }) {
    return <td className='p-4 border-t border-[#f0f0f0] dark:border-gray-700'>{children}</td>;
  },
  h1({ children }) {
    return <h3 className='text-2xl font-bold my-4 border-b border-slate-300 pb-4'>{children}</h3>;
  },
  h2({ children }) {
    return <h3 className='text-xl font-bold my-3'>{children}</h3>;
  },
  h3({ children }) {
    return <h3 className='text-lg font-semibold my-2'>{children}</h3>;
  },
  h4({ children }) {
    return <h3 className='text-base font-semibold my-1'>{children}</h3>;
  },
  a({ children, href }) {
    return (
      <div className='inline-block text-blue-600 dark:text-blue-400'>
        <LinkOutlined className='mr-1' />
        <a href={href} target='_blank' rel='noreferrer'>
          {children}
        </a>
      </div>
    );
  },
  img({ src, alt }) {
    return (
      <div>
        <Image
          className='min-h-[1rem] max-w-full max-h-full border rounded'
          src={src}
          alt={alt}
          placeholder={
            <Tag icon={<SyncOutlined spin />} color='processing'>
              Image Loading...
            </Tag>
          }
          fallback='/pictures/fallback.png'
        />
      </div>
    );
  },
  blockquote({ children }) {
    return (
      <blockquote className='py-4 px-6 border-l-4 border-blue-600 rounded bg-white my-2 text-gray-500 dark:bg-slate-800 dark:text-gray-200 dark:border-white shadow-sm'>
        {children}
      </blockquote>
    );
  },
  button({ children, className, ...restProps }) {
    if (className === 'chat-link') {
      const msg = (restProps as any)?.['data-msg'];
      return <VisChatLink msg={msg}>{children}</VisChatLink>;
    }
    return (
      <button className={className} {...restProps}>
        {children}
      </button>
    );
  },
};

const returnSqlVal = (val: string) => {
  const punctuationMap: any = {
    '，': ',',
    '。': '.',
    '？': '?',
    '！': '!',
    '：': ':',
    '；': ';',
    '“': '"',
    '”': '"',
    '‘': "'",
    '’': "'",
    '（': '(',
    '）': ')',
    '【': '[',
    '】': ']',
    '《': '<',
    '》': '>',
    '—': '-',
    '、': ',',
    '…': '...',
  };
  const regex = new RegExp(Object.keys(punctuationMap).join('|'), 'g');
  return val.replace(regex, match => punctuationMap[match]);
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
      ? Object.keys(data?.data?.[0])?.map(item => {
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
      children: <CodePreview code={formatSql(returnSqlVal(data?.sql), 'mysql') as string} language={'sql'} />,
    };
    const DataItem = {
      key: 'data',
      label: 'Data',
      children: <Table dataSource={data?.data} columns={columns} scroll={{ x: true }} virtual={true} />,
    };
    const TabItems: TabsProps['items'] =
      data?.type === 'response_table' ? [DataItem, SqlItem] : [ChartItem, SqlItem, DataItem];

    return (
      <div>
        <Tabs defaultActiveKey={data?.type === 'response_table' ? 'data' : 'chart'} items={TabItems} size='small' />
        {children}
      </div>
    );
  },
  references: function ({ children }) {
    if (children) {
      try {
        const referenceData = JSON.parse(children as string);
        const references = referenceData.references;
        return <ReferencesContent references={references} />;
      } catch {
        return null;
      }
    }
  },
  summary: function ({ children }) {
    return (
      <div>
        <p className='mb-2'>
          <ReadOutlined className='mr-2' />
          <span className='font-semibold'>Document Summary</span>
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
