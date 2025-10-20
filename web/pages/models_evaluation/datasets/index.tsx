import { apiInterceptors } from '@/client/api';
import {
  getBenchmarkDatasetTables,
  getBenchmarkDatasets,
  getBenchmarkTableRows,
} from '@/client/api/models_evaluation/datasets';
import { NavTo } from '@/components/models_evaluation/components/nav-to';
import { Card, Spin, Table, Tree, TreeDataNode, Typography } from 'antd';
import React, { Key, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import styles from '../styles.module.css';

const { Title, Text } = Typography;

// 定义数据类型
interface Dataset {
  dataset_id: string;
  name: string;
  tableCount: number;
}

interface TableColumn {
  name: string;
  type: string;
}

interface TableInfo {
  name: string;
  rowCount: number;
  columns: TableColumn[];
}

interface TableRow {
  [key: string]: any;
}

interface TableData {
  table: string;
  limit: number;
  rows: TableRow[];
}

type CustomTreeDataNode = TreeDataNode & {
  parent?: string; // 指向父节点
};

const DatasetsForEvaluation = () => {
  const [tableData, setTableData] = useState<TableData | null>(null);
  const [loading, setLoading] = useState({
    datasets: false,
    tables: false,
    tableData: false,
  });
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const { t } = useTranslation();
  // 构造树结构数据
  const [treeData, setTreeData] = useState<CustomTreeDataNode[]>([]);

  // 获取数据集列表
  useEffect(() => {
    async function init() {
      const result: Dataset[] = await fetchDatasets();
      setTreeData(
        result.map((item: Dataset) => ({
          title: `${item.name}(${item.tableCount} ${t('tables')})`,
          key: item.dataset_id,
          selectable: false,
        })),
      );

      setSelectedDataset(prevState => {
        if (prevState && result.map(item => item.dataset_id).includes(prevState)) return prevState;
        return result[0]?.dataset_id;
      });
    }
    init();
  }, []);

  const fetchDatasets = async () => {
    try {
      setLoading(prev => ({ ...prev, datasets: true }));
      const [err, data] = await apiInterceptors(getBenchmarkDatasets());

      if (err) {
        console.error(t('get_dataset_list_failed'), err);
        return;
      }

      return data || [];
    } catch (err) {
      console.error(t('get_dataset_list_failed'), err);
    } finally {
      setLoading(prev => ({ ...prev, datasets: false }));
    }
  };

  // 获取数据集下的表列表
  const fetchTables = async (datasetId: string): Promise<TableInfo[]> => {
    try {
      setLoading(prev => ({ ...prev, tables: true }));
      setSelectedTable(null);

      const [err, data] = await apiInterceptors(getBenchmarkDatasetTables(datasetId));

      if (err) {
        console.error(t('get_table_list_failed'), err);
        return [];
      }

      return data || [];
    } catch (err) {
      console.error(t('get_table_list_failed'), err);
      return [];
    } finally {
      setLoading(prev => ({ ...prev, tables: false }));
    }
  };

  const updateTreeData = (
    list: CustomTreeDataNode[],
    key: React.Key,
    children: CustomTreeDataNode[],
  ): CustomTreeDataNode[] =>
    list.map(node => {
      if (node.key === key) {
        return {
          ...node,
          children,
        };
      }
      if (node.children) {
        return {
          ...node,
          children: updateTreeData(node.children, key, children),
        };
      }
      return node;
    });

  const loadTreeData = async ({ key, children }: any) => {
    if (children) {
      return;
    }
    const tables = await fetchTables(key);
    setTreeData((prev: CustomTreeDataNode[]) =>
      updateTreeData(
        prev,
        key,
        tables.map(item => ({
          title: item.name,
          key: item.name,
          parent: key, // 保留父节点的指针
          isLeaf: true,
        })),
      ),
    );
    return;
  };

  const onTableSelected = async (selectedKeys: Key[], { selectedNodes }: { selectedNodes: CustomTreeDataNode[] }) => {
    setSelectedDataset(selectedNodes[0].parent as string);
    setSelectedTable(selectedKeys[0] as string);
  };

  // 获取表数据
  const fetchTableData = async (datasetId: string, tableName: string) => {
    try {
      setLoading(prev => ({ ...prev, tableData: true }));

      const [err, data] = await apiInterceptors(getBenchmarkTableRows(datasetId, tableName));

      if (err) {
        console.error(t('get_table_data_failed'), err);
        return;
      }

      setTableData(data || null);
    } catch (err) {
      console.error(t('get_table_data_failed'), err);
    } finally {
      setLoading(prev => ({ ...prev, tableData: false }));
    }
  };

  useEffect(() => {
    if (selectedDataset && selectedTable) {
      fetchTableData(selectedDataset, selectedTable);
    } else {
      setTableData(null);
    }
  }, [selectedDataset, selectedTable]);

  // 生成表格列定义
  const generateColumns = () => {
    if (!tableData || tableData.rows.length === 0) return [];

    const firstRow = tableData.rows[0];
    return Object.keys(firstRow).map((key, index) => ({
      title: key,
      dataIndex: key,
      key: key,
      width: index === 0 ? 100 : undefined,
    }));
  };

  return (
    <div className='h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12'>
      <Card
        title={
          <>
            {t('evaluation_datasets')}
            <NavTo href='/models_evaluation'>{t('back_to_evaluation_task_list')}</NavTo>
          </>
        }
        className={`w-full h-full flex-1 flex flex-col ${styles['page-card']}`}
      >
        <div className='flex h-full'>
          {/* 左侧数据集列表 */}
          <div className='w-1/4 pr-4 border-r flex flex-col'>
            <Title level={5} className='mb-4'>
              {t('dataset_list')}
            </Title>
            <div className='overflow-y-auto h-full'>
              <Tree loadData={loadTreeData} treeData={treeData} onSelect={onTableSelected} />
            </div>
          </div>

          {/* 右侧表数据 */}
          <div className='w-3/4 pl-4 flex flex-col'>
            <div className='flex justify-between items-center mb-4'>
              <Title level={5} className='mb-0'>
                {t('table_data')}
                <span className='font-normal text-sm'>{t('only_show_first_10_data')}</span>
              </Title>
              {selectedTable && <Text type='secondary'>{selectedTable}</Text>}
            </div>
            <div className='overflow-y-auto h-full'>
              {loading.tableData ? (
                <div className='flex justify-center items-center h-full'>
                  <Spin />
                </div>
              ) : tableData && tableData.rows.length > 0 ? (
                <Table
                  className={`w-full flex-auto ${styles.table}`}
                  dataSource={tableData.rows}
                  columns={generateColumns()}
                  pagination={false}
                  scroll={{ x: true }}
                  size='small'
                />
              ) : selectedTable ? (
                <Text type='secondary'>{t('no_data')}</Text>
              ) : (
                <Text type='secondary'>{t('please_select_a_table_first')}</Text>
              )}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default DatasetsForEvaluation;
