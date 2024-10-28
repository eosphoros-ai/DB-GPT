import { sendGetRequest, sendSpacePostRequest } from '@/utils/request';
import Icon from '@ant-design/icons';
import { OnChange } from '@monaco-editor/react';
import { useRequest } from 'ahooks';
import { Button, Input, Select, Table, Tooltip, Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useSearchParams } from 'next/navigation';
import { ChangeEvent, Key, useEffect, useMemo, useState } from 'react';
import Chart from '../chart';
import Header from './header';
import MonacoEditor, { ISession } from './monaco-editor';

import SplitScreenHeight from '@/components/icons/split-screen-height';
import SplitScreenWeight from '@/components/icons/split-screen-width';
import { CaretRightOutlined, LeftOutlined, RightOutlined, SaveFilled } from '@ant-design/icons';
import { ColumnType } from 'antd/es/table';
import classNames from 'classnames';
import MyEmpty from '../common/MyEmpty';
import Database from '../icons/database';
import Field from '../icons/field';
import TableIcon from '../icons/table';

const { Search } = Input;

type ITableData = {
  columns: string[];
  values: (string | number)[][];
};

interface EditorValueProps {
  sql?: string;
  thoughts?: string;
  title?: string;
  showcase?: string;
}

interface RoundProps {
  db_name: string;
  round: number;
  round_name: string;
}

interface IProps {
  editorValue?: EditorValueProps;
  chartData?: any;
  tableData?: ITableData;
  layout?: 'TB' | 'LR';
  tables?: any;
  handleChange: OnChange;
}

interface ITableTreeItem {
  title: string;
  key: string;
  type: string;
  default_value: string | null;
  can_null: string;
  comment: string | null;
  children: Array<ITableTreeItem>;
}

function DbEditorContent({ layout = 'LR', editorValue, chartData, tableData, tables, handleChange }: IProps) {
  const chartWrapper = useMemo(() => {
    if (!chartData) return null;
    return (
      <div className='flex-1 overflow-auto p-2' style={{ flexShrink: 0, overflow: 'hidden' }}>
        <Chart chartsData={[chartData]} />
      </div>
    );
  }, [chartData]);

  const { columns, dataSource } = useMemo<{
    columns: ColumnType<any>[];
    dataSource: Record<string, string | number>[];
  }>(() => {
    const { columns: cols = [], values: vals = [] } = tableData ?? {};
    const tbCols = cols.map<ColumnType<any>>(item => ({
      key: item,
      dataIndex: item,
      title: item,
    }));
    const tbDatas = vals.map(row => {
      return row.reduce<Record<string, string | number>>((acc, item, index) => {
        acc[cols[index]] = item;
        return acc;
      }, {});
    });

    return {
      columns: tbCols,
      dataSource: tbDatas,
    };
  }, [tableData]);
  const session: ISession = useMemo(() => {
    const map: Record<string, { columnName: string; columnType: string }[]> = {};
    const db = tables?.data;
    const tableList = db?.children;
    tableList?.forEach((table: ITableTreeItem) => {
      map[table.title] = table.children.map((column: ITableTreeItem) => {
        return {
          columnName: column.title,
          columnType: column.type,
        };
      });
    });
    return {
      async getTableList(schemaName: any) {
        if (schemaName && schemaName !== db?.title) {
          return [];
        }
        return tableList?.map((table: ITableTreeItem) => table.title) || [];
      },
      async getTableColumns(tableName: any) {
        return map[tableName] || [];
      },
      async getSchemaList() {
        return db?.title ? [db?.title] : [];
      },
    };
  }, [tables]);
  return (
    <div
      className={classNames('flex w-full flex-1 h-full gap-2 overflow-hidden', {
        'flex-col': layout === 'TB',
        'flex-row': layout === 'LR',
      })}
    >
      <div className='flex-1 flex overflow-hidden rounded'>
        <MonacoEditor
          value={editorValue?.sql || ''}
          language='mysql'
          onChange={handleChange}
          thoughts={editorValue?.thoughts || ''}
          session={session}
        />
      </div>
      <div className='flex-1 h-full overflow-auto bg-white dark:bg-theme-dark-container rounded p-4'>
        {tableData?.values.length ? (
          <Table bordered scroll={{ x: 'auto' }} rowKey={columns[0].key} columns={columns} dataSource={dataSource} />
        ) : (
          <div className='h-full flex justify-center items-center'>
            <MyEmpty />
          </div>
        )}
        {chartWrapper}
      </div>
    </div>
  );
}

function DbEditor() {
  const [expandedKeys, setExpandedKeys] = useState<Key[]>([]);
  const [searchValue, setSearchValue] = useState('');
  const [currentRound, setCurrentRound] = useState<null | string | number>();
  const [autoExpandParent, setAutoExpandParent] = useState(true);
  const [chartData, setChartData] = useState<any>();
  const [editorValue, setEditorValue] = useState<EditorValueProps | EditorValueProps[]>();
  const [newEditorValue, setNewEditorValue] = useState<EditorValueProps>();
  const [tableData, setTableData] = useState<{ columns: string[]; values: (string | number)[] }>();
  const [currentTabIndex, setCurrentTabIndex] = useState<number>();
  const [isMenuExpand, setIsMenuExpand] = useState<boolean>(false);
  const [layout, setLayout] = useState<'TB' | 'LR'>('TB');

  const searchParams = useSearchParams();
  const id = searchParams?.get('id');
  const scene = searchParams?.get('scene');

  const { data: rounds } = useRequest(
    async () =>
      await sendGetRequest('/v1/editor/sql/rounds', {
        con_uid: id,
      }),
    {
      onSuccess: res => {
        const lastItem = res?.data?.[res?.data?.length - 1];
        if (lastItem) {
          setCurrentRound(lastItem?.round);
        }
      },
    },
  );

  const { run: runSql, loading: runLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item: any) => item.round === currentRound)?.db_name;
      return await sendSpacePostRequest(`/api/v1/editor/sql/run`, {
        db_name,
        sql: newEditorValue?.sql,
      });
    },
    {
      manual: true,
      onSuccess: res => {
        setTableData({
          columns: res?.data?.colunms,
          values: res?.data?.values,
        });
      },
    },
  );

  const { run: runCharts, loading: runChartsLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item: any) => item.round === currentRound)?.db_name;
      const params: {
        db_name: string;
        sql?: string;
        chart_type?: string;
      } = {
        db_name,
        sql: newEditorValue?.sql,
      };
      if (scene === 'chat_dashboard') {
        params['chart_type'] = newEditorValue?.showcase;
      }
      return await sendSpacePostRequest(`/api/v1/editor/chart/run`, params);
    },
    {
      manual: true,
      ready: !!newEditorValue?.sql,
      onSuccess: res => {
        if (res?.success) {
          setTableData({
            columns: res?.data?.sql_data?.colunms || [],
            values: res?.data?.sql_data?.values || [],
          });
          if (!res?.data?.chart_values) {
            setChartData(undefined);
          } else {
            setChartData({
              type: res?.data?.chart_type,
              values: res?.data?.chart_values,
              title: newEditorValue?.title,
              description: newEditorValue?.thoughts,
            });
          }
        }
      },
    },
  );

  const { run: submitSql, loading: submitLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item: RoundProps) => item.round === currentRound)?.db_name;
      return await sendSpacePostRequest(`/api/v1/sql/editor/submit`, {
        conv_uid: id,
        db_name,
        conv_round: currentRound,
        old_sql: editorValue?.sql,
        old_speak: editorValue?.thoughts,
        new_sql: newEditorValue?.sql,
        new_speak: newEditorValue?.thoughts?.match(/^\n--(.*)\n\n$/)?.[1]?.trim() || newEditorValue?.thoughts,
      });
    },
    {
      manual: true,
      onSuccess: res => {
        if (res?.success) {
          runSql();
        }
      },
    },
  );

  const { run: submitChart, loading: submitChartLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item: any) => item.round === currentRound)?.db_name;
      return await sendSpacePostRequest(`/api/v1/chart/editor/submit`, {
        conv_uid: id,
        chart_title: newEditorValue?.title,
        db_name,
        old_sql: editorValue?.[currentTabIndex ?? 0]?.sql,
        new_chart_type: newEditorValue?.showcase,
        new_sql: newEditorValue?.sql,
        new_comment: newEditorValue?.thoughts?.match(/^\n--(.*)\n\n$/)?.[1]?.trim() || newEditorValue?.thoughts,
        gmt_create: new Date().getTime(),
      });
    },
    {
      manual: true,
      onSuccess: res => {
        if (res?.success) {
          runCharts();
        }
      },
    },
  );

  const { data: tables } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item: RoundProps) => item.round === currentRound)?.db_name;
      return await sendGetRequest('/v1/editor/db/tables', {
        db_name,
        page_index: 1,
        page_size: 200,
      });
    },
    {
      ready: !!rounds?.data?.find((item: RoundProps) => item.round === currentRound)?.db_name,
      refreshDeps: [rounds?.data?.find((item: RoundProps) => item.round === currentRound)?.db_name],
    },
  );

  const { run: handleGetEditorSql } = useRequest(
    async round =>
      await sendGetRequest('/v1/editor/sql', {
        con_uid: id,
        round,
      }),
    {
      manual: true,
      onSuccess: res => {
        let sql = undefined;
        try {
          if (Array.isArray(res?.data)) {
            sql = res?.data;
            setCurrentTabIndex(0);
          } else if (typeof res?.data === 'string') {
            const d = JSON.parse(res?.data);
            sql = d;
          } else {
            sql = res?.data;
          }
        } catch (e) {
          console.log(e);
        } finally {
          setEditorValue(sql);
          if (Array.isArray(sql)) {
            setNewEditorValue(sql?.[Number(currentTabIndex || 0)]);
          } else {
            setNewEditorValue(sql);
          }
        }
      },
    },
  );

  const treeData = useMemo(() => {
    const loop = (data: Array<ITableTreeItem>, parentKey?: string | number): DataNode[] =>
      data.map((item: ITableTreeItem) => {
        const strTitle = item.title;
        const index = strTitle.indexOf(searchValue);
        const beforeStr = strTitle.substring(0, index);
        const afterStr = strTitle.slice(index + searchValue.length);
        const renderIcon = (type: string) => {
          switch (type) {
            case 'db':
              return <Database />;
            case 'table':
              return <TableIcon />;
            default:
              return <Field />;
          }
        };
        const showTitle =
          index > -1 ? (
            <Tooltip
              title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}
            >
              <div className='flex items-center'>
                {renderIcon(item.type)}&nbsp;&nbsp;&nbsp;
                {beforeStr}
                <span className='text-[#1677ff]'>{searchValue}</span>
                {afterStr}&nbsp;
                {item?.type && <div className='text-gray-400'>{item?.type}</div>}
              </div>
            </Tooltip>
          ) : (
            <Tooltip
              title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}
            >
              <div className='flex items-center'>
                {renderIcon(item.type)}&nbsp;&nbsp;&nbsp;
                {strTitle}&nbsp;
                {item?.type && <div className='text-gray-400'>{item?.type}</div>}
              </div>
            </Tooltip>
          );
        if (item.children) {
          const itemKey = parentKey ? String(parentKey) + '_' + item.key : item.key;
          return { title: strTitle, showTitle, key: itemKey, children: loop(item.children, itemKey) };
        }

        return {
          title: strTitle,
          showTitle,
          key: item.key,
        };
      });
    if (tables?.data) {
      // default expand first node
      setExpandedKeys([tables?.data.key]);
      return loop([tables?.data]);
    }
    return [];
  }, [searchValue, tables]);

  const dataList = useMemo(() => {
    const res: { key: string | number; title: string; parentKey?: string | number }[] = [];
    const generateList = (data: DataNode[], parentKey?: string | number) => {
      if (!data || data?.length <= 0) return;
      for (let i = 0; i < data.length; i++) {
        const node = data[i];
        const { key, title } = node;
        res.push({ key, title: title as string, parentKey });
        if (node.children) {
          generateList(node.children, key);
        }
      }
    };
    if (treeData) {
      generateList(treeData);
    }
    return res;
  }, [treeData]);

  const getParentKey = (key: Key, tree: DataNode[]): Key => {
    let parentKey: Key;
    for (let i = 0; i < tree.length; i++) {
      const node = tree[i];
      if (node.children) {
        if (node.children.some(item => item.key === key)) {
          parentKey = node.key;
        } else if (getParentKey(key, node.children)) {
          parentKey = getParentKey(key, node.children);
        }
      }
    }
    return parentKey!;
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { value } = e.target;
    if (tables?.data) {
      if (!value) {
        setExpandedKeys([]);
      } else {
        const newExpandedKeys = dataList
          .map(item => {
            if (item.title.indexOf(value) > -1) {
              return getParentKey(item.key, treeData);
            }
            return null;
          })
          .filter((item, i, self) => item && self.indexOf(item) === i);
        setExpandedKeys(newExpandedKeys as Key[]);
      }
      setSearchValue(value);
      setAutoExpandParent(true);
    }
  };

  useEffect(() => {
    if (currentRound) {
      handleGetEditorSql(currentRound);
    }
  }, [handleGetEditorSql, currentRound]);

  useEffect(() => {
    if (editorValue && scene === 'chat_dashboard' && currentTabIndex) {
      runCharts();
    }
  }, [currentTabIndex, scene, editorValue, runCharts]);

  useEffect(() => {
    if (editorValue && scene !== 'chat_dashboard') {
      runSql();
    }
  }, [scene, editorValue, runSql]);

  function resolveSqlAndThoughts(value: string | undefined) {
    if (!value) {
      return { sql: '', thoughts: '' };
    }
    const match = value && value.match(/(--.*)?\n?([\s\S]*)/);
    let thoughts = '';
    let sql;
    if (match && match.length >= 3) {
      thoughts = match[1];
      sql = match[2];
    }
    return { sql, thoughts };
  }

  return (
    <div className='flex flex-col w-full h-full overflow-hidden'>
      <Header />
      <div className='relative flex flex-1 p-4 pt-0 overflow-hidden'>
        <div className='relative flex overflow-hidden mr-4'>
          <div
            className={classNames('h-full relative transition-[width] overflow-hidden', {
              'w-0': isMenuExpand,
              'w-64': !isMenuExpand,
            })}
          >
            <div className='relative w-64 h-full overflow-hidden flex flex-col rounded bg-white dark:bg-theme-dark-container p-4'>
              <Select
                size='middle'
                className='w-full mb-2'
                value={currentRound}
                options={rounds?.data?.map((item: RoundProps) => {
                  return {
                    label: item.round_name,
                    value: item.round,
                  };
                })}
                onChange={e => {
                  setCurrentRound(e);
                }}
              />
              <Search className='mb-2' placeholder='Search' onChange={onChange} />
              {treeData && treeData.length > 0 && (
                <div className='flex-1 overflow-y-auto'>
                  <Tree
                    onExpand={(newExpandedKeys: Key[]) => {
                      setExpandedKeys(newExpandedKeys);
                      setAutoExpandParent(false);
                    }}
                    expandedKeys={expandedKeys}
                    autoExpandParent={autoExpandParent}
                    treeData={treeData}
                    fieldNames={{
                      title: 'showTitle',
                    }}
                  />
                </div>
              )}
            </div>
          </div>
          <div className='absolute right-0 top-0 translate-x-full h-full flex items-center justify-center opacity-0 hover:opacity-100 group-hover/side:opacity-100 transition-opacity'>
            <div
              className='bg-white w-4 h-10 flex items-center justify-center dark:bg-theme-dark-container rounded-tr rounded-br z-10 text-xs cursor-pointer shadow-[4px_0_10px_rgba(0,0,0,0.06)] text-opacity-80'
              onClick={() => {
                setIsMenuExpand(!isMenuExpand);
              }}
            >
              {!isMenuExpand ? <LeftOutlined /> : <RightOutlined />}
            </div>
          </div>
        </div>
        <div className='flex flex-col flex-1 max-w-full overflow-hidden'>
          {/* Actions */}
          <div className='mb-2 bg-white dark:bg-theme-dark-container p-2 flex justify-between items-center'>
            <div className='flex gap-2'>
              <Button
                className='text-xs rounded-none'
                size='small'
                type='primary'
                icon={<CaretRightOutlined />}
                loading={runLoading || runChartsLoading}
                onClick={async () => {
                  if (scene === 'chat_dashboard') {
                    runCharts();
                  } else {
                    runSql();
                  }
                }}
              >
                Run
              </Button>
              <Button
                className='text-xs rounded-none'
                type='primary'
                size='small'
                loading={submitLoading || submitChartLoading}
                icon={<SaveFilled />}
                onClick={async () => {
                  if (scene === 'chat_dashboard') {
                    await submitChart();
                  } else {
                    await submitSql();
                  }
                }}
              >
                Save
              </Button>
            </div>
            <div className='flex gap-2'>
              <Icon
                className={classNames('flex items-center justify-center w-6 h-6 text-lg rounded', {
                  'bg-theme-primary bg-opacity-10': layout === 'TB',
                })}
                component={SplitScreenWeight}
                onClick={() => {
                  setLayout('TB');
                }}
              />
              <Icon
                className={classNames('flex items-center justify-center w-6 h-6 text-lg rounded', {
                  'bg-theme-primary bg-opacity-10': layout === 'LR',
                })}
                component={SplitScreenHeight}
                onClick={() => {
                  setLayout('LR');
                }}
              />
            </div>
          </div>
          {/* Panel */}
          {Array.isArray(editorValue) ? (
            <div className='flex flex-col h-full overflow-hidden'>
              <div className='w-full whitespace-nowrap overflow-x-auto bg-white dark:bg-theme-dark-container mb-2 text-[0px]'>
                {editorValue.map((item, index) => (
                  <Tooltip className='inline-block' key={item.title} title={item.title}>
                    <div
                      className={classNames(
                        'max-w-[240px] px-3 h-10 text-ellipsis overflow-hidden whitespace-nowrap text-sm leading-10 cursor-pointer font-semibold hover:text-theme-primary transition-colors mr-2 last-of-type:mr-0',
                        {
                          'border-b-2 border-solid border-theme-primary text-theme-primary': currentTabIndex === index,
                        },
                      )}
                      onClick={() => {
                        setCurrentTabIndex(index);
                        setNewEditorValue(editorValue?.[index]);
                      }}
                    >
                      {item.title}
                    </div>
                  </Tooltip>
                ))}
              </div>
              <div className='flex flex-1 overflow-hidden'>
                {editorValue.map((item, index) => (
                  <div
                    key={item.title}
                    className={classNames('w-full overflow-hidden', {
                      hidden: index !== currentTabIndex,
                      'block flex-1': index === currentTabIndex,
                    })}
                  >
                    <DbEditorContent
                      layout={layout}
                      editorValue={item}
                      handleChange={value => {
                        const { sql, thoughts } = resolveSqlAndThoughts(value);
                        setNewEditorValue(old => {
                          return Object.assign({}, old, {
                            sql,
                            thoughts,
                          });
                        });
                      }}
                      tableData={tableData}
                      chartData={chartData}
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <DbEditorContent
              layout={layout}
              editorValue={editorValue}
              handleChange={value => {
                const { sql, thoughts } = resolveSqlAndThoughts(value);
                setNewEditorValue(old => {
                  return Object.assign({}, old, {
                    sql,
                    thoughts,
                  });
                });
              }}
              tableData={tableData}
              chartData={undefined}
              tables={tables}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default DbEditor;
