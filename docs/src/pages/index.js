import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';

const featureGroups = [
  {
    title: 'Start Here',
    items: [
      {
        title: 'Overview',
        description: 'Learn what DB-GPT is and how it revolutionizes database interactions with AI.',
        link: '/docs/overview',
        icon: '📖',
      },
      {
        title: 'Getting Started',
        description: 'Get DB-GPT running in minutes with the one-line installer.',
        link: '/docs/installation',
        icon: '🚀',
      },
      {
        title: 'Show Cases',
        description: 'Explore real-world use cases and examples powered by DB-GPT.',
        link: '/docs/use_cases',
        icon: '⚡',
      },
    ],
  },
  {
    title: 'Installation',
    items: [
      {
        title: 'Source Code',
        description: 'Install from source with full control over your deployment.',
        link: '/docs/getting-started/deploy/source-code',
        icon: '💻',
      },
      {
        title: 'CLI Quick Start',
        description: 'Get started quickly with the DB-GPT CLI.',
        link: '/docs/getting-started/cli-quickstart',
        icon: '🔧',
      },
      {
        title: 'Docker Deployment',
        description: 'Deploy with Docker for quick and isolated setup.',
        link: '/docs/installation/docker',
        icon: '🐳',
      },
    ],
  },
  {
    title: 'Core Concepts',
    items: [
      {
        title: 'Agents',
        description: 'Build autonomous AI agents for complex data tasks.',
        link: '/docs/getting-started/concepts/agents',
        icon: '🤖',
      },
      {
        title: 'AWEL',
        description: 'Agentic Workflow Expression Language for orchestration.',
        link: '/docs/getting-started/concepts/awel',
        icon: '🔄',
      },
      {
        title: 'RAG',
        description: 'Retrieval-Augmented Generation for knowledge-enhanced AI.',
        link: '/docs/getting-started/concepts/rag',
        icon: '🧠',
      },
      {
        title: 'SMMF',
        description: 'Service-oriented Multi-model Management Framework.',
        link: '/docs/getting-started/concepts/smmf',
        icon: '🔌',
      },
    ],
  },
  {
    title: 'Core Components',
    items: [
      {
        title: 'Skills',
        description: 'Reusable skill packages for domain-specific tasks.',
        link: '/docs/dbgpts/introduction',
        icon: '🧩',
      },
      {
        title: 'DataSources',
        description: 'Connect to databases, warehouses, and data platforms.',
        link: '/docs/modules/connections',
        icon: '🔗',
      },
      {
        title: 'Sandbox',
        description: 'Secure sandboxed environments for code execution.',
        link: '/docs/sandbox/',
        icon: '📦',
      },
      {
        title: 'Knowledge',
        description: 'Build and manage knowledge bases for RAG.',
        link: '/docs/modules/rag',
        icon: '📚',
      },
    ],
  },
  {
    title: 'Applications',
    items: [
      {
        title: 'Chat with Data',
        description: 'Natural language queries to your databases.',
        link: '/docs/application/apps/chat_data',
        icon: '💬',
      },
      {
        title: 'Data Analysis',
        description: 'AI-powered analysis of CSV, Excel, and databases.',
        link: '/docs/cookbook/app/data_analysis_app_develop',
        icon: '📊',
      },
      {
        title: 'AWEL Flows',
        description: 'Build and run agentic workflows visually.',
        link: '/docs/application/awel',
        icon: '🎯',
      },
    ],
  },
];

const quickLinks = [
  { title: 'GitHub', href: 'https://github.com/eosphoros-ai/DB-GPT', icon: '🔗' },
  { title: 'Discord', href: 'https://discord.gg/erwfqcMP', icon: '💬' },
  { title: 'HuggingFace', href: 'https://huggingface.co/eosphoros', icon: '🤗' },
  { title: 'Community', href: 'https://github.com/eosphoros-ai/community', icon: '👥' },
];

function FeatureCard({ title, description, link, icon }) {
  return (
    <Link to={link} className="homepage-card">
      <div className="homepage-card-icon">{icon}</div>
      <div className="homepage-card-content">
        <h3 className="homepage-card-title">{title}</h3>
        <p className="homepage-card-description">{description}</p>
      </div>
      <div className="homepage-card-arrow">→</div>
    </Link>
  );
}

function FeatureSection({ title, items }) {
  return (
    <div className="homepage-section">
      <h2 className="homepage-section-title">{title}</h2>
      <div className="homepage-cards-grid">
        {items.map((item, idx) => (
          <FeatureCard key={idx} {...item} />
        ))}
      </div>
    </div>
  );
}

function QuickLink({ title, href, icon }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="homepage-quick-link">
      <span className="homepage-quick-link-icon">{icon}</span>
      <span>{title}</span>
    </a>
  );
}

export default function Home() {
  const { siteConfig } = useDocusaurusContext();
  const logoSrc = useBaseUrl('img/dbgpt_logo.svg');

  return (
    <Layout
      title={siteConfig.title}
      description="DB-GPT: Open-Source Agentic AI Data Assistant - Revolutionizing Database Interactions with Private LLM Technology"
    >
      <main className="homepage-main">
        <div className="homepage-hero">
          <div className="homepage-hero-content">
            <img src={logoSrc} alt="DB-GPT Logo" className="homepage-hero-logo" />
            <p className="homepage-hero-tagline">
              Open-Source Agentic AI Data Assistant
            </p>
            <p className="homepage-hero-description">
              Connect to your data, write SQL and code autonomously, run skills in sandboxed environments, 
              and turn analysis into reports, insights, and action.
            </p>
            <div className="homepage-hero-buttons">
              <Link to="/docs/installation" className="homepage-button homepage-button-primary">
                Get Started
              </Link>
              <Link to="/docs/overview" className="homepage-button homepage-button-secondary">
                Learn More
              </Link>
            </div>
          </div>
        </div>

        <div className="homepage-content">
          {featureGroups.map((group, idx) => (
            <FeatureSection key={idx} {...group} />
          ))}

          <div className="homepage-section homepage-quick-links-section">
            <h2 className="homepage-section-title">Community & Resources</h2>
            <div className="homepage-quick-links">
              {quickLinks.map((link, idx) => (
                <QuickLink key={idx} {...link} />
              ))}
            </div>
          </div>
        </div>
      </main>
    </Layout>
  );
}
