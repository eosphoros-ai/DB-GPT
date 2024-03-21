import React, { useState } from 'react';
import { useRequest } from 'ahooks';
import { Button, Select, Table, Tooltip } from 'antd';
import { Input, Tree, Empty, Tabs } from 'antd';
import type { DataNode } from 'antd/es/tree';
import MonacoEditor from './monaco-editor';
import { sendGetRequest, sendSpacePostRequest } from '@/utils/request';
import { useSearchParams } from 'next/navigation';
import { OnChange } from '@monaco-editor/react';
import Header from './header';
import Chart from '../chart';
import { CaretRightOutlined, MenuFoldOutlined, MenuUnfoldOutlined, SaveFilled } from '@ant-design/icons';
import { ColumnType } from 'antd/es/table';
import Database from '../icons/database';
import TableIcon from '../icons/table';
import Field from '../icons/field';

const { Search } = Input;

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
  tableData?: any;
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

function DbEditorContent({ editorValue, chartData, tableData, handleChange }: IProps) {
  const chartWrapper = React.useMemo(() => {
    if (!chartData) return null;

    return (
      <div className="flex-1 overflow-auto p-3" style={{ flexShrink: 0, overflow: 'hidden' }}>
        <Chart chartsData={[chartData]} />
      </div>
    );
  }, [chartData]);

  return (
    <div className="flex flex-1 h-full gap-4">
      <div className="h-full flex-1 flex overflow-hidden bg-white rounded">
        <MonacoEditor value={editorValue?.sql || ''} language="mysql" onChange={handleChange} thoughts={editorValue?.thoughts || ''} />
      </div>
      <div className="flex-1 h-full overflow-y-auto bg-white rounded">
        {tableData?.values?.length > 0 ? (
          <Table
            rowKey={tableData?.columns?.[0]}
            columns={(tableData?.columns as any[]).map<ColumnType<any>>((item) => ({
              key: item,
              dataIndex: item,
              label: item,
            }))}
            dataSource={tableData?.values}
          />
        ) : (
          <div className="h-full flex justify-center items-center">
            <Empty />
          </div>
        )}
        {chartWrapper}
      </div>
    </div>
  );
}

function DbEditor() {
  const [expandedKeys, setExpandedKeys] = React.useState<React.Key[]>([]);
  const [searchValue, setSearchValue] = React.useState('');
  const [currentRound, setCurrentRound] = React.useState<null | string | number>();
  const [autoExpandParent, setAutoExpandParent] = React.useState(true);
  const [chartData, setChartData] = React.useState();
  const [editorValue, setEditorValue] = React.useState<EditorValueProps | EditorValueProps[]>();
  const [newEditorValue, setNewEditorValue] = React.useState<EditorValueProps>();
  const [tableData, setTableData] = React.useState<{ columns: string[]; values: any }>();
  const [currentTabIndex, setCurrentTabIndex] = React.useState<string>();
  const [isMenuExpand, setIsMenuExpand] = useState<boolean>(true);

  const searchParams = useSearchParams();
  const id = searchParams?.get('id');
  const scene = searchParams?.get('scene');

  const { data: rounds, loading: roundsLoading } = useRequest(
    async () =>
      await sendGetRequest('/v1/editor/sql/rounds', {
        con_uid: id,
      }),
    {
      onSuccess: (res) => {
        const lastItem = res?.data?.[res?.data?.length - 1];
        if (lastItem) {
          setCurrentRound(lastItem?.round);
        }
      },
    },
  );

  const { run: runSql, loading: runLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item) => item.round === currentRound)?.db_name;
      return await sendSpacePostRequest(`/api/v1/editor/sql/run`, {
        db_name,
        sql: newEditorValue?.sql,
      });
    },
    {
      manual: true,
      onSuccess: (res) => {
        setTableData({
          columns: res?.data?.colunms,
          values: res?.data?.values,
        });
      },
    },
  );

  const { run: runCharts, loading: runChartsLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item) => item.round === currentRound)?.db_name;
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
      onSuccess: (res) => {
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
      onSuccess: (res) => {
        if (res?.success) {
          runSql();
        }
      },
    },
  );

  const { run: submitChart, loading: submitChartLoading } = useRequest(
    async () => {
      const db_name = rounds?.data?.find((item) => item.round === currentRound)?.db_name;
      return await sendSpacePostRequest(`/api/v1/chart/editor/submit`, {
        conv_uid: id,
        chart_title: newEditorValue?.title,
        db_name,
        old_sql: editorValue?.[currentTabIndex]?.sql,
        new_chart_type: newEditorValue?.showcase,
        new_sql: newEditorValue?.sql,
        new_comment: newEditorValue?.thoughts?.match(/^\n--(.*)\n\n$/)?.[1]?.trim() || newEditorValue?.thoughts,
        gmt_create: new Date().getTime(),
      });
    },
    {
      manual: true,
      onSuccess: (res) => {
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
    async (round) =>
      await sendGetRequest('/v1/editor/sql', {
        con_uid: id,
        round,
      }),
    {
      manual: true,
      onSuccess: (res) => {
        let sql = undefined;
        try {
          if (Array.isArray(res?.data)) {
            sql = res?.data;
            setCurrentTabIndex('0');
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

  const treeData = React.useMemo(() => {
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
            <Tooltip title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}>
              <div className="flex items-center">
                {renderIcon(item.type)}&nbsp;&nbsp;&nbsp;
                {beforeStr}
                <span className="text-[#1677ff]">{searchValue}</span>
                {afterStr}&nbsp;
                {item?.type && <div className="text-gray-400">{item?.type}</div>}
              </div>
            </Tooltip>
          ) : (
            <Tooltip title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}>
              <div className="flex items-center">
                {renderIcon(item.type)}&nbsp;&nbsp;&nbsp;
                {strTitle}&nbsp;
                {item?.type && <div className="text-gray-400">{item?.type}</div>}
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

  const dataList = React.useMemo(() => {
    let res: { key: string | number; title: string; parentKey?: string | number }[] = [];
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

  const getParentKey = (key: React.Key, tree: DataNode[]): React.Key => {
    let parentKey: React.Key;
    for (let i = 0; i < tree.length; i++) {
      const node = tree[i];
      if (node.children) {
        if (node.children.some((item) => item.key === key)) {
          parentKey = node.key;
        } else if (getParentKey(key, node.children)) {
          parentKey = getParentKey(key, node.children);
        }
      }
    }
    return parentKey!;
  };

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { value } = e.target;
    if (tables?.data) {
      if (!value) {
        setExpandedKeys([]);
      } else {
        const newExpandedKeys = dataList
          .map((item) => {
            if (item.title.indexOf(value) > -1) {
              return getParentKey(item.key, treeData);
            }
            return null;
          })
          .filter((item, i, self) => item && self.indexOf(item) === i);
        setExpandedKeys(newExpandedKeys as React.Key[]);
      }
      setSearchValue(value);
      setAutoExpandParent(true);
    }
  };

  React.useEffect(() => {
    if (currentRound) {
      handleGetEditorSql(currentRound);
    }
  }, [handleGetEditorSql, currentRound]);

  React.useEffect(() => {
    if (editorValue && scene === 'chat_dashboard' && currentTabIndex) {
      runCharts();
    }
  }, [currentTabIndex, scene, editorValue, runCharts]);

  React.useEffect(() => {
    if (editorValue && scene !== 'chat_dashboard') {
      runSql();
    }
  }, [scene, editorValue, runSql]);

  function resolveSqlAndThoughts(value: string | undefined) {
    if (!value) {
      return { sql: '', thoughts: '' };
    }
    const match = value && value.match(/(--.*)\n([\s\S]*)/);
    let thoughts = '';
    let sql;
    if (match && match.length >= 3) {
      thoughts = match[1];
      sql = match[2];
    }
    return { sql, thoughts };
  }

  return (
    <div className="flex flex-col w-full h-full">
      <Header />
      <div className="relative flex flex-1 overflow-auto">
        <div className={`w-80 ml-4 ${isMenuExpand && 'hidden'}`}>
          <div className="flex items-center py-3">
            <Select
              size="small"
              className="w-60"
              value={currentRound}
              options={rounds?.data?.map((item: RoundProps) => {
                return {
                  label: item.round_name,
                  value: item.round,
                };
              })}
              onChange={(e) => {
                setCurrentRound(e);
              }}
            />
          </div>
          <Search style={{ marginBottom: 8 }} placeholder="Search" onChange={onChange} />

          {treeData && treeData.length > 0 && (
            <Tree
              className="h-[795px] overflow-y-auto flex-1"
              onExpand={(newExpandedKeys: React.Key[]) => {
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
          )}
        </div>
        {!isMenuExpand ? (
          <MenuFoldOutlined
            onClick={() => {
              setIsMenuExpand(!isMenuExpand);
            }}
            className="w-4 cursor-pointer"
          />
        ) : (
          <MenuUnfoldOutlined
            onClick={() => {
              setIsMenuExpand(!isMenuExpand);
            }}
            className="w-4 cursor-pointer"
          />
        )}
        {/* operations */}
        <div className="flex flex-col flex-1 max-w-full overflow-hidden p-4">
          <div className="mb-4 bg-white pl-4 pt-2 pb-2">
            <Button
              className="mr-2"
              type="primary"
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
              type="primary"
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
          {Array.isArray(editorValue) ? (
            <div className="h-full">
              <Tabs
                className="h-full dark:text-white px-2"
                activeKey={currentTabIndex}
                onChange={(activeKey) => {
                  setCurrentTabIndex(activeKey);
                  setNewEditorValue(editorValue?.[Number(activeKey)]);
                }}
                items={editorValue?.map((item, i) => ({
                  key: i + '',
                  label: item?.title,
                  children: (
                    <div className="flex flex-col h-full">
                      <DbEditorContent
                        editorValue={item}
                        handleChange={(value) => {
                          const { sql, thoughts } = resolveSqlAndThoughts(value);
                          setNewEditorValue((old) => {
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
                  ),
                }))}
              />
            </div>
          ) : (
            <DbEditorContent
              editorValue={editorValue}
              handleChange={(value) => {
                const { sql, thoughts } = resolveSqlAndThoughts(value);
                setNewEditorValue((old) => {
                  return Object.assign({}, old, {
                    sql,
                    thoughts,
                  });
                });
              }}
              tableData={tableData}
              chartData={undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default DbEditor;
