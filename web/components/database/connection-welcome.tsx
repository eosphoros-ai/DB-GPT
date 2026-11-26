import { DBOption, DBType } from '@/types/db';
import { ArrowRightOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import { useTranslation } from 'react-i18next';
import DatabaseTypeIcon from './database-type-icon';
import styles from './database.module.css';
import { useDatabaseCopy } from './presentation';

const recommendations = [
  { type: 'mysql', cn: '连接应用与业务系统的数据', en: 'Connect application and business data' },
  { type: 'postgresql', cn: '连接关系型数据库与分析数据', en: 'Connect relational and analytical data' },
  { type: 'sqlite', cn: '从一个已有的数据库文件开始', en: 'Start with an existing database file' },
  { type: 'clickhouse', cn: '连接事件、日志与分析数据', en: 'Connect events, logs and analytics' },
  { type: 'maxcompute', cn: '连接云端项目与数据仓库', en: 'Connect your cloud data warehouse' },
  { type: 'duckdb', cn: '连接本地分析数据库', en: 'Connect a local analytical database' },
];

export default function ConnectionWelcome({
  options,
  onConnect,
  onBrowse,
}: {
  options: DBOption[];
  onConnect: (type: DBType) => void;
  onBrowse: () => void;
}) {
  const { i18n } = useTranslation();
  const { copy } = useDatabaseCopy(i18n.language);
  const available = recommendations.flatMap(recommendation => {
    const option = options.find(item => item.value === recommendation.type && !item.disabled);
    return option ? [{ ...recommendation, option }] : [];
  });

  return (
    <section className={styles.welcome} aria-label={copy('数据源入门', 'Get started with data sources')}>
      <div className={styles.welcomeSectionHeading}>
        <div>
          <h3>{copy('从常用数据库开始', 'Start with a familiar database')}</h3>
          <p>{copy('选择类型，直接进入对应的连接表单。', 'Choose a type to open its connection settings.')}</p>
        </div>
        <Button type='link' onClick={onBrowse} icon={<ArrowRightOutlined />}>
          {copy('查看全部类型', 'View all types')}
        </Button>
      </div>
      <div className={styles.welcomeGrid}>
        {available.map(({ option, cn, en }) => (
          <button key={option.value} className={styles.welcomeType} onClick={() => onConnect(option.value)}>
            <DatabaseTypeIcon icon={option.icon} label={option.label} />
            <span className={styles.welcomeTypeText}>
              <strong>{option.label}</strong>
              <span>{copy(cn, en)}</span>
            </span>
            <ArrowRightOutlined className={styles.welcomeTypeArrow} />
          </button>
        ))}
      </div>
      <p className={styles.welcomeNote}>
        {copy(
          '添加连接时会先测试数据库是否可访问，连接配置可随时修改。',
          'We verify database access before saving. You can edit your connection settings at any time.',
        )}
      </p>
    </section>
  );
}
