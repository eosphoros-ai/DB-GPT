import React from 'react';
import { useRequest } from 'ahooks';
import { Select, Option, Table, Box, Typography, Tooltip } from '@mui/joy';
import { Button } from 'antd';
import AutoAwesomeMotionIcon from '@mui/icons-material/AutoAwesomeMotion';
import { Input, Tree, Empty, Tabs } from 'antd';
import type { DataNode } from 'antd/es/tree';
import MonacoEditor from './monaco-editor';
import { sendGetRequest, sendSpacePostRequest } from '@/utils/request';
import { useSearchParams } from 'next/navigation';
import { OnChange } from '@monaco-editor/react';
import Header from './header';
import Chart from '../chart';

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
    if (!chartData) return <div></div>;
    return (
      <div className="flex-1 overflow-auto p-3" style={{ flexShrink: 0, overflow: 'hidden' }}>
        <Chart chartsData={[chartData]} />
      </div>
    );
  }, [chartData]);

  return (
    <>
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1" style={{ flexShrink: 0, overflow: 'auto' }}>
          <MonacoEditor value={editorValue?.sql || ''} language="mysql" onChange={handleChange} thoughts={editorValue?.thoughts || ''} />
        </div>
        {chartWrapper}
      </div>
      <div className="h-96 border-[var(--joy-palette-divider)] border-t border-solid overflow-auto">
        {tableData?.values?.length > 0 ? (
          <Table aria-label="basic table" stickyHeader>
            <thead>
              <tr>
                {tableData?.columns?.map((column: any, i: number) => (
                  <th key={column + i}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableData?.values?.map((value: any, i: number) => (
                <tr key={i}>
                  {Object.keys(value)?.map((v) => (
                    <td key={v}>{value[v]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="h-full flex justify-center items-center">
            <Empty />
          </div>
        )}
      </div>
    </>
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
        const showTitle =
          index > -1 ? (
            <Tooltip title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}>
              <span>
                {beforeStr}
                <span className="text-[#1677ff]">{searchValue}</span>
                {afterStr}
                {item?.type && (
                  <Typography gutterBottom level="body3" className="pl-0.5" style={{ display: 'inline' }}>
                    {`[${item?.type}]`}
                  </Typography>
                )}
              </span>
            </Tooltip>
          ) : (
            <Tooltip title={(item?.comment || item?.title) + (item?.can_null === 'YES' ? '(can null)' : `(can't null)`)}>
              <span>
                {strTitle}
                {item?.type && (
                  <Typography gutterBottom level="body3" className="pl-0.5" style={{ display: 'inline' }}>
                    {`[${item?.type}]`}
                  </Typography>
                )}
              </span>
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
        <div
          className="text h-full border-[var(--joy-palette-divider)] border-r border-solid p-3 max-h-full overflow-auto"
          style={{ width: '300px' }}
        >
          <div className="absolute right-4 top-2 z-10">
            <Button
              className="mr-2"
              type="primary"
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
              loading={submitLoading || submitChartLoading}
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
          <div className="flex items-center py-3">
            <Select
              className="h-4 min-w-[240px]"
              size="sm"
              value={currentRound as string | null | undefined}
              onChange={(e: React.SyntheticEvent | null, newValue: string | null) => {
                setCurrentRound(newValue);
              }}
            >
              {rounds?.data?.map((item: RoundProps) => (
                <Option key={item?.round} value={item?.round}>
                  {item?.round_name}
                </Option>
              ))}
            </Select>
            <AutoAwesomeMotionIcon className="ml-2" />
          </div>
          <Search style={{ marginBottom: 8 }} placeholder="Search" onChange={onChange} />
          {treeData && treeData.length > 0 && (
            <Tree
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
        <div className="flex flex-col flex-1 max-w-full overflow-hidden">
          {Array.isArray(editorValue) ? (
            <>
              <Box
                className="h-full"
                sx={{
                  '.ant-tabs-content, .ant-tabs-tabpane-active': {
                    height: '100%',
                  },
                  '& .ant-tabs-card.ant-tabs-top >.ant-tabs-nav .ant-tabs-tab, & .ant-tabs-card.ant-tabs-top >div>.ant-tabs-nav .ant-tabs-tab': {
                    borderRadius: '0',
                  },
                }}
              >
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
              </Box>
            </>
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
