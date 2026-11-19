import { DBOption } from '@/types/db';
import { CheckCircleOutlined, LinkOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import { useTranslation } from 'react-i18next';
import DatabaseTypeIcon from './database-type-icon';
import styles from './database.module.css';
import { useDatabaseCopy } from './presentation';

export default function DatabaseBanner({
  connectionCount,
  connectedTypes,
  onBrowse,
}: {
  connectionCount: number;
  connectedTypes: DBOption[];
  onBrowse: () => void;
}) {
  const { i18n } = useTranslation();
  const { copy } = useDatabaseCopy(i18n.language);
  const first = connectionCount === 0;
  const steps = [
    [
      copy('选择数据库', 'Choose a database'),
      copy('找到你正在使用的数据库类型', 'Choose the database you already use'),
    ],
    [
      copy('填写连接信息', 'Configure the connection'),
      copy('准备主机地址、凭据或文件路径', 'Have your host, credentials or file path ready'),
    ],
    [
      copy('测试并开始使用', 'Verify and get started'),
      copy('连接成功后，即可用于查询、分析和看板', 'Use your connection for queries, analysis and dashboards'),
    ],
  ];
  return (
    <section className={`${styles.welcomeHero} ${styles.banner}`} aria-label={copy('数据源引导', 'Data source guide')}>
      <div>
        <div className={styles.welcomeBadge}>
          <LinkOutlined />
          {first
            ? copy('从第一个连接开始', 'START WITH YOUR FIRST CONNECTION')
            : copy('连接业务数据，发现更多洞察', 'CONNECT DATA. DISCOVER INSIGHTS.')}
        </div>
        <h2>
          {first
            ? copy('连接你的数据，让分析开始。', 'Connect your data. Start exploring.')
            : copy('让数据就绪，让洞察发生。', 'Your data, ready for your next insight.')}
        </h2>
        <p className={styles.welcomeDescription}>
          {first
            ? copy(
                '接入已有数据库，让 DB-GPT 帮你查询数据、发现洞察和构建看板。选择一个数据库类型，我们会引导你完成连接。',
                'Connect an existing database to query your data, discover insights and build dashboards. Choose a database to configure your first connection.',
              )
            : copy(
                '在这里统一管理数据库连接，为智能查询、数据分析和看板提供数据。你可以接入更多数据库，也可以随时调整已有连接。',
                'Manage your database connections for intelligent queries, data analysis and dashboards. Connect more databases or update your existing settings.',
              )}
        </p>
        <Button className={styles.primary} type='primary' icon={<LinkOutlined />} onClick={onBrowse}>
          {first ? copy('选择数据库类型', 'Choose a database') : copy('连接更多数据', 'Connect more data')}
        </Button>
      </div>
      {first ? (
        <ol className={styles.welcomeSteps}>
          {steps.map(([title, detail], index) => (
            <li key={title}>
              <span className={styles.welcomeStepNumber}>
                {index === 2 ? <CheckCircleOutlined /> : `0${index + 1}`}
              </span>
              <div>
                <strong>{title}</strong>
                <p>{detail}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <div className={styles.bannerOverview}>
          <div className={styles.bannerStats}>
            <div>
              <strong>{connectionCount}</strong>
              <span>{copy('已添加连接', 'Saved connections')}</span>
            </div>
            <div>
              <strong>{connectedTypes.length}</strong>
              <span>{copy('数据库类型', 'Database types')}</span>
            </div>
          </div>
          <div className={styles.bannerTypes}>
            {connectedTypes.slice(0, 4).map(type => (
              <span key={type.value}>
                <DatabaseTypeIcon icon={type.icon} label={type.label} compact />
                {type.label}
              </span>
            ))}
          </div>
          <p>
            {copy(
              '查询 · 分析 · 看板，从连接好的数据开始。',
              'Queries, analysis and dashboards start with connected data.',
            )}
          </p>
        </div>
      )}
    </section>
  );
}
