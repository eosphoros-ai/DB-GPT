import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';

const featureGroups = [
  {
    title: ['Start Here', '从这里开始'],
    items: [
      {
        title: ['Overview', '产品概览'],
        description: ['Understand the vision of trusted, controlled data agents.', '了解可信、受控 Data Agent 的愿景与产品主线。'],
        link: '/docs/overview',
        icon: '📖',
      },
      {
        title: ['Your First Data Task', '第一次数据任务'],
        description: ['Connect data, select a scenario, and check the evidence.', '连接数据，选择场景，核验执行与结果。'],
        link: '/docs/data-agent/quickstart',
        icon: '🚀',
      },
      {
        title: ['Showcases', '场景案例'],
        description: ['Explore the five homepage scenarios with inputs and verification steps.', '按首页五个场景查看输入、操作和核验方法。'],
        link: '/docs/use_cases',
        icon: '⚡',
      },
    ],
  },
  {
    title: ['Build Trust and Control', '建立可信与受控的数据工作方式'],
    items: [
      {
        title: ['Semantic Center', '语义中心'],
        description: ['Review business meanings and publish metric versions agents can cite.', '审核业务含义，发布 Agent 可读取和引用的指标版本。'],
        link: '/docs/semantic-center/overview',
        icon: '🗂️',
      },
      {
        title: ['Scenario Plugins', '场景插件'],
        description: ['Reuse expert methods, skills, and task configuration.', '复用专家方法、Skills 和任务配置。'],
        link: '/docs/plugins/overview',
        icon: '🧩',
      },
      {
        title: ['Agentic Workflow', 'Agentic Workflow'],
        description: ['Coordinate agent responsibilities, deliverables, dependencies, and gates.', '组织 Agent 责任、产物、依赖与 Gate。'],
        link: '/docs/workflow/introduction',
        icon: '🔄',
      },
      {
        title: ['Controlled Execution', '受控执行'],
        description: ['Inspect resource boundaries, approvals, and actual tool evidence.', '检查资源边界、审批与真实工具证据。'],
        link: '/docs/data-agent/controlled-execution',
        icon: '🛡️',
      },
    ],
  },
  {
    title: ['Deploy and Extend', '部署与扩展'],
    items: [
      {
        title: ['Installation', '安装部署'],
        description: ['Choose an installation and configure a working model.', '选择安装方式，配置可用模型。'],
        link: '/docs/installation',
        icon: '💻',
      },
      {
        title: ['Datasources', '数据源'],
        description: ['Connect databases and other data resources.', '连接数据库与其他数据资源。'],
        link: '/docs/modules/connections',
        icon: '🔗',
      },
      {
        title: ['Harness', '执行 Harness'],
        description: ['Configure or extend the agent execution engine.', '配置或扩展 Agent 执行引擎。'],
        link: '/docs/harness/introduction',
        icon: '🔧',
      },
      {
        title: ['Plugin Package Reference', '插件包格式参考'],
        description: ['Package a reusable scenario for your team.', '为团队封装可复用场景能力。'],
        link: '/docs/plugins/package-reference',
        icon: '📦',
      },
    ],
  },
];

function FeatureCard({ title, description, link, icon, languageIndex }) {
  return (
    <Link to={useBaseUrl(link)} className="homepage-card">
      <div className="homepage-card-icon">{icon}</div>
      <div className="homepage-card-content">
        <h3 className="homepage-card-title">{title[languageIndex]}</h3>
        <p className="homepage-card-description">{description[languageIndex]}</p>
      </div>
      <div className="homepage-card-arrow">→</div>
    </Link>
  );
}

export default function Home() {
  const { siteConfig, i18n } = useDocusaurusContext();
  const languageIndex = i18n.currentLocale === 'zh-CN' ? 1 : 0;
  const isZh = languageIndex === 1;
  const tagline = isZh
    ? '打造可信、受控的 Data Agent'
    : 'Data agents for trusted, controlled data work';
  const description = isZh
    ? '通过可治理语义、场景插件、Agentic Workflow 和受控执行，将业务问题转化为可核验的查询、分析、报告与看板。'
    : 'Turn business questions into checkable queries, analysis, reports, and dashboards through governed semantics, scenario plugins, agentic workflows, and controlled execution.';
  const logoSrc = useBaseUrl('img/dbgpt_logo.svg');
  const firstTaskUrl = useBaseUrl('/docs/data-agent/quickstart');
  const overviewUrl = useBaseUrl('/docs/overview');

  return (
    <Layout title={siteConfig.title} description={description}>
      <main className="homepage-main">
        <div className="homepage-hero">
          <div className="homepage-hero-content">
            <img src={logoSrc} alt="DB-GPT Logo" className="homepage-hero-logo" />
            <p className="homepage-hero-tagline">{tagline}</p>
            <p className="homepage-hero-description">{description}</p>
            <div className="homepage-hero-buttons">
              <Link to={firstTaskUrl} className="homepage-button homepage-button-primary">
                {isZh ? '开始第一次任务' : 'Start Your First Task'}
              </Link>
              <Link to={overviewUrl} className="homepage-button homepage-button-secondary">
                {isZh ? '了解产品' : 'Explore the Product'}
              </Link>
            </div>
          </div>
        </div>
        <div className="homepage-content">
          {featureGroups.map(group => (
            <div className="homepage-section" key={group.title[0]}>
              <h2 className="homepage-section-title">{group.title[languageIndex]}</h2>
              <div className="homepage-cards-grid">
                {group.items.map(item => (
                  <FeatureCard key={item.link} {...item} languageIndex={languageIndex} />
                ))}
              </div>
            </div>
          ))}
          <div className="homepage-section homepage-quick-links-section">
            <h2 className="homepage-section-title">{isZh ? '社区与资源' : 'Community & Resources'}</h2>
            <div className="homepage-quick-links">
              <a href="https://github.com/eosphoros-ai/DB-GPT" className="homepage-quick-link">GitHub</a>
              <a href="https://github.com/eosphoros-ai/community" className="homepage-quick-link">
                {isZh ? '社区' : 'Community'}
              </a>
            </div>
          </div>
        </div>
      </main>
    </Layout>
  );
}
