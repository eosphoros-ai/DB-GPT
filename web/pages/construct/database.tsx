import { apiInterceptors, getDbList, getDbSupportType, postDbDelete, postDbRefresh } from '@/client/api';
import ConnectionWelcome from '@/components/database/connection-welcome';
import DatabaseBanner from '@/components/database/database-banner';
import DatabaseTypeIcon from '@/components/database/database-type-icon';
import styles from '@/components/database/database.module.css';
import FormDialog from '@/components/database/form-dialog';
import {
  Connection,
  connectionAddress,
  connectionName,
  connectionParams,
  databaseCategory,
  useDatabaseCopy,
} from '@/components/database/presentation';
import ConstructLayout from '@/new-components/layout/Construct';
import { DBOption, DBType, DbListResponse, DbSupportTypeResponse } from '@/types/db';
import { dbMapper } from '@/utils';
import {
  ArrowRightOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  FolderOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useAsyncEffect } from 'ahooks';
import { Alert, Button, Drawer, Input, Modal, Spin, Tooltip, message } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

export function isFileDb(dbTypeList: DBOption[], dbType: DBType) {
  return dbTypeList.find(item => item.value === dbType)?.isFileDb;
}

function Database() {
  const { i18n } = useTranslation();
  const { copy } = useDatabaseCopy(i18n.language);
  const [dbList, setDbList] = useState<DbListResponse>([]);
  const [dbSupportList, setDbSupportList] = useState<DbSupportTypeResponse>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [tab, setTab] = useState<'connections' | 'catalog'>('connections');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [modal, setModal] = useState<{ open: boolean; type?: DBType; connection?: Connection }>({ open: false });
  const [drawerType, setDrawerType] = useState<DBType>();
  const [refreshing, setRefreshing] = useState<string[]>([]);

  const refreshDbList = async () => {
    setLoading(true);
    try {
      const [err, data, response] = await apiInterceptors(getDbList());
      const failed = !!err || response?.success === false;
      setLoadError(failed);
      if (!failed) setDbList(data ?? []);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  useAsyncEffect(async () => {
    await Promise.all([
      refreshDbList(),
      (async () => {
        const [err, data] = await apiInterceptors(getDbSupportType());
        if (!err) {
          const response = data as unknown as { types?: DbSupportTypeResponse } | DbSupportTypeResponse;
          setDbSupportList(Array.isArray(response) ? response : (response?.types ?? []));
        }
      })(),
    ]);
  }, []);

  const dbTypeList = useMemo(() => {
    const supported = Array.from(new Map(dbSupportList.map(item => [item.name, item])).values()).map(item => ({
      ...(dbMapper[item.name] || { label: item.label || item.name, icon: '', desc: item.description }),
      value: item.name as DBType,
      isFileDb: ['sqlite', 'duckdb', 'access'].includes(item.name.toLowerCase()),
      parameters: item.parameters,
    }));
    const unavailable = Object.keys(dbMapper)
      .filter(type => !supported.some(item => item.value === type))
      .map(type => ({
        ...dbMapper[type],
        value: type as DBType,
        disabled: true,
      }));
    return [...supported, ...unavailable] as DBOption[];
  }, [dbSupportList]);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    dbList.forEach(item => {
      const type = item.type.toLowerCase();
      result[type] = (result[type] || 0) + 1;
    });
    return result;
  }, [dbList]);
  const needle = search.trim().toLowerCase();
  const firstConnection = !loading && !loadError && dbList.length === 0 && !needle;
  const filteredConnections = dbList.filter(item =>
    `${connectionName(item)} ${item.type} ${connectionAddress(item)} ${item.description || ''}`
      .toLowerCase()
      .includes(needle),
  );
  const filteredTypes = dbTypeList.filter(
    item =>
      `${item.label} ${item.value}`.toLowerCase().includes(needle) &&
      (category === 'all' || databaseCategory(item.value) === category),
  );
  const drawerOption = dbTypeList.find(item => item.value === drawerType);
  const drawerConnections = dbList.filter(item => item.type.toLowerCase() === drawerType?.toLowerCase());
  const categories = [
    ['all', copy('全部类型', 'All types')],
    ['relational', copy('关系型数据库', 'Relational')],
    ['analytics', copy('分析与数仓', 'Analytics')],
    ['nosql', 'NoSQL'],
    ['graph', copy('图数据库', 'Graph')],
  ];
  const categoryLabel = (type: DBType) => categories.find(item => item[0] === databaseCategory(type))?.[1];

  const openForm = (type?: DBType, connection?: Connection) => {
    setDrawerType(undefined);
    setModal({ open: true, type, connection });
  };

  const onDelete = (item: Connection) => {
    Modal.confirm({
      title: copy('删除数据源连接？', 'Delete this data source?'),
      content: copy(
        `将移除「${connectionName(item)}」的连接配置，不会删除数据库中的数据。`,
        `This removes the connection configuration for “${connectionName(item)}”. Your database contents are preserved.`,
      ),
      okText: copy('删除连接', 'Delete connection'),
      cancelText: copy('取消', 'Cancel'),
      okButtonProps: { danger: true },
      async onOk() {
        const [err, , response] = await apiInterceptors(postDbDelete(item.id), '*');
        if (err || response?.success === false) {
          const error =
            err || new Error(response?.err_msg || copy('删除失败，请重试。', 'Unable to delete. Please try again.'));
          message.error(error.message);
          throw error;
        }
        message.success(copy('连接已删除', 'Connection deleted'));
        await refreshDbList();
      },
    });
  };

  const onRefresh = async (item: Connection) => {
    setRefreshing(ids => [...ids, item.id]);
    try {
      const [err, , response] = await apiInterceptors(postDbRefresh({ id: item.id }));
      if (!err && response?.success !== false) message.success(copy('元数据已刷新', 'Metadata refreshed'));
    } finally {
      setRefreshing(ids => ids.filter(id => id !== item.id));
    }
  };

  const renderConnection = (item: Connection) => (
    <article className={styles.card} key={item.id}>
      <div className={styles.cardTop}>
        <DatabaseTypeIcon icon={dbMapper[item.type]?.icon} label={dbMapper[item.type]?.label || item.type} />
        <div className={styles.cardIdentity}>
          <h3 className={styles.cardTitle} title={connectionName(item)}>
            {connectionName(item)}
          </h3>
          <div className={styles.typeLabel}>
            {dbTypeList.find(type => type.value === item.type)?.label || item.type}
          </div>
        </div>
      </div>
      <p className={styles.cardDescription} title={item.description}>
        {item.description ||
          copy('暂无描述，可在编辑中补充数据源用途。', 'Add a description to explain how this data source is used.')}
      </p>
      <div className={styles.address} title={connectionAddress(item)}>
        <FolderOutlined />
        <span>{connectionAddress(item)}</span>
      </div>
      <div className={styles.cardFooter}>
        <span className={styles.saved}>{copy('已添加连接', 'Connection saved')}</span>
        <div className={styles.actions}>
          <Tooltip title={copy('刷新元数据', 'Refresh metadata')}>
            <Button
              type='text'
              size='small'
              aria-label={`${copy('刷新元数据', 'Refresh metadata')} ${connectionName(item)}`}
              icon={<ReloadOutlined />}
              loading={refreshing.includes(item.id)}
              onClick={() => onRefresh(item)}
            />
          </Tooltip>
          <Tooltip title={copy('编辑连接', 'Edit connection')}>
            <Button
              type='text'
              size='small'
              aria-label={`${copy('编辑连接', 'Edit connection')} ${connectionName(item)}`}
              icon={<EditOutlined />}
              onClick={() => openForm(item.type, item)}
            />
          </Tooltip>
          <Tooltip title={copy('删除连接', 'Delete connection')}>
            <Button
              danger
              type='text'
              size='small'
              aria-label={`${copy('删除连接', 'Delete connection')} ${connectionName(item)}`}
              icon={<DeleteOutlined />}
              onClick={() => onDelete(item)}
            />
          </Tooltip>
        </div>
      </div>
    </article>
  );

  const empty = (isSearch: boolean, type?: DBType) => (
    <div className={styles.empty}>
      <div className={styles.emptyIcon}>{isSearch ? <SearchOutlined /> : <DatabaseOutlined />}</div>
      <h2>
        {isSearch
          ? copy('没有找到匹配项', 'No matches found')
          : copy('连接你的第一个数据源', 'Connect your first data source')}
      </h2>
      <p>
        {isSearch
          ? copy('尝试其他关键词，或清除筛选条件。', 'Try another keyword or clear your filters.')
          : copy(
              '添加数据库连接，即可用于智能查询、分析和看板。',
              'Add a database connection to power queries, analysis and dashboards.',
            )}
      </p>
      <Button
        className={styles.primary}
        type='primary'
        icon={isSearch ? undefined : <PlusOutlined />}
        onClick={() => (isSearch ? (setSearch(''), setCategory('all')) : openForm(type))}
      >
        {isSearch ? copy('清除筛选', 'Clear filters') : copy('添加数据源', 'Add data source')}
      </Button>
    </div>
  );

  return (
    <ConstructLayout>
      <div className={styles.page}>
        <header className={styles.header}>
          <div>
            <div className={styles.eyebrow}>DATA SOURCES</div>
            <h1>{copy('数据源', 'Data sources')}</h1>
            <p className={styles.subtitle}>
              {copy('让业务数据就绪，从一个可靠的连接开始。', 'Every insight starts with a reliable data connection.')}
            </p>
          </div>
          <Button className={styles.primary} type='primary' icon={<PlusOutlined />} onClick={() => openForm()}>
            {copy('添加数据源', 'Add data source')}
          </Button>
        </header>
        <DatabaseBanner
          connectionCount={dbList.length}
          connectedTypes={dbTypeList.filter(type => counts[type.value.toLowerCase()])}
          onBrowse={() => {
            setTab('catalog');
            setSearch('');
            setCategory('all');
          }}
        />
        <div className={styles.workspace}>
          <div className={styles.toolbar}>
            <div className={styles.tabs} role='tablist' aria-label={copy('数据源视图', 'Data source views')}>
              <button
                role='tab'
                aria-selected={tab === 'connections'}
                className={`${styles.tab} ${tab === 'connections' ? styles.activeTab : ''}`}
                onClick={() => {
                  setTab('connections');
                  setSearch('');
                }}
              >
                {firstConnection ? copy('开始使用', 'Get started') : copy('已添加连接', 'Connections')}
                <span className={styles.count}>{dbList.length}</span>
              </button>
              <button
                role='tab'
                aria-selected={tab === 'catalog'}
                className={`${styles.tab} ${tab === 'catalog' ? styles.activeTab : ''}`}
                onClick={() => {
                  setTab('catalog');
                  setSearch('');
                }}
              >
                {copy('数据库目录', 'Database catalog')}
                <span className={styles.count}>{dbTypeList.length}</span>
              </button>
            </div>
            {!firstConnection || tab === 'catalog' ? (
              <Input
                className={styles.search}
                prefix={<SearchOutlined style={{ color: '#8a96a3' }} />}
                allowClear
                placeholder={
                  tab === 'connections'
                    ? copy('搜索名称、类型或地址', 'Search name, type or address')
                    : copy('搜索数据库类型', 'Search database types')
                }
                aria-label={copy('搜索数据源', 'Search data sources')}
                value={search}
                onChange={event => setSearch(event.target.value)}
              />
            ) : null}
          </div>
          <div className={styles.content}>
            {loadError ? (
              <Alert
                type='error'
                showIcon
                message={copy('无法加载数据源', 'Unable to load data sources')}
                action={
                  <Button size='small' onClick={refreshDbList}>
                    {copy('重试', 'Retry')}
                  </Button>
                }
              />
            ) : null}
            <Spin spinning={loading}>
              {tab === 'connections' ? (
                <>
                  {!firstConnection ? (
                    <div className={styles.sectionMeta}>
                      <span>
                        {copy(
                          `共 ${filteredConnections.length} 个连接，统一管理你的业务数据。`,
                          `${filteredConnections.length} connections for your business data.`,
                        )}
                      </span>
                      <Button type='text' size='small' icon={<ReloadOutlined />} onClick={refreshDbList}>
                        {copy('刷新列表', 'Refresh')}
                      </Button>
                    </div>
                  ) : null}
                  {filteredConnections.length ? (
                    <div className={styles.grid}>{filteredConnections.map(renderConnection)}</div>
                  ) : !loading && !loadError ? (
                    firstConnection ? (
                      <ConnectionWelcome
                        options={dbTypeList}
                        onConnect={type => openForm(type)}
                        onBrowse={() => {
                          setTab('catalog');
                          setSearch('');
                          setCategory('all');
                        }}
                      />
                    ) : (
                      empty(!!needle)
                    )
                  ) : null}
                </>
              ) : (
                <>
                  <div className={styles.filters}>
                    {categories.map(([value, label]) => (
                      <button
                        key={value}
                        aria-pressed={category === value}
                        className={`${styles.filter} ${category === value ? styles.activeFilter : ''}`}
                        onClick={() => setCategory(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className={styles.sectionMeta}>
                    <span>
                      {copy(
                        '选择数据库类型，查看连接或添加新数据源。',
                        'Choose a database to view connections or add a new one.',
                      )}
                    </span>
                    <span>
                      {copy(
                        `${dbTypeList.filter(type => !type.disabled).length} 种类型可用`,
                        `${dbTypeList.filter(type => !type.disabled).length} types available`,
                      )}
                    </span>
                  </div>
                  {filteredTypes.length ? (
                    <div className={styles.typeGrid}>
                      {filteredTypes.map(item => (
                        <button
                          key={item.value}
                          className={`${styles.card} ${styles.typeCard}`}
                          disabled={item.disabled}
                          onClick={() =>
                            counts[item.value.toLowerCase()] ? setDrawerType(item.value) : openForm(item.value)
                          }
                        >
                          <div className={styles.cardTop}>
                            <DatabaseTypeIcon icon={item.icon} label={item.label} />
                            <div className={styles.cardIdentity}>
                              <h3 className={styles.cardTitle}>{item.label}</h3>
                              <div className={styles.typeLabel}>{categoryLabel(item.value)}</div>
                            </div>
                          </div>
                          <div className={styles.typeFoot}>
                            <span>
                              {item.disabled
                                ? copy('当前环境未启用', 'Unavailable in this environment')
                                : counts[item.value.toLowerCase()]
                                  ? copy(
                                      `${counts[item.value.toLowerCase()]} 个连接`,
                                      `${counts[item.value.toLowerCase()]} connections`,
                                    )
                                  : copy('添加连接', 'Add connection')}
                            </span>
                            {!item.disabled ? <ArrowRightOutlined /> : null}
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    empty(true)
                  )}
                </>
              )}
            </Spin>
          </div>
        </div>
        <FormDialog
          open={modal.open}
          dbTypeList={dbTypeList}
          choiceDBType={modal.type}
          editValue={modal.connection?.id}
          initialParams={modal.connection ? connectionParams(modal.connection) : undefined}
          description={modal.connection?.description}
          onClose={() => setModal({ open: false })}
          onSuccess={() => {
            setModal({ open: false });
            setTab('connections');
            setSearch('');
            refreshDbList();
          }}
        />
        {!modal.open ? (
          <Drawer
            rootClassName={styles.surface}
            title={drawerOption?.label}
            open={!!drawerType}
            width={460}
            onClose={() => setDrawerType(undefined)}
          >
            <div className={styles.drawerIntro}>
              <p className={styles.subtitle}>
                {copy('管理该类型的数据源连接。', 'Manage connections for this database type.')}
              </p>
            </div>
            <Button
              type='primary'
              className={styles.primary}
              icon={<PlusOutlined />}
              onClick={() => openForm(drawerType)}
            >
              {copy('添加连接', 'Add connection')}
            </Button>
            <div className={styles.drawerCards}>{drawerConnections.map(renderConnection)}</div>
          </Drawer>
        ) : null}
      </div>
    </ConstructLayout>
  );
}

export default Database;
