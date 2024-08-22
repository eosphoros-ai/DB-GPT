import IconFont from '@/new-components/common/Icon';
import {
  AppstoreAddOutlined,
  BarChartOutlined,
  CodeOutlined,
  CopyOutlined,
  DatabaseOutlined,
  DeploymentUnitOutlined,
  FileExcelOutlined,
  FileOutlined,
  FolderOutlined,
  GlobalOutlined,
  PictureOutlined,
  PieChartOutlined,
  ProductOutlined,
  ReadOutlined,
  RiseOutlined,
} from '@ant-design/icons';
import React from 'react';

export const agentIcon: Record<string, React.ReactNode> = {
  CodeEngineer: <CodeOutlined />,
  Reporter: <PieChartOutlined />,
  DataScientist: <BarChartOutlined />,
  Summarizer: <CopyOutlined />,
  ToolExpert: <IconFont type="icon-plugin" style={{ fontSize: 17.25, marginTop: 2 }} />,
  Indicator: <RiseOutlined />,
  Dbass: <FolderOutlined />,
};

export const resourceTypeIcon: Record<string, React.ReactNode> = {
  all: <ProductOutlined />,
  database: <DatabaseOutlined />,
  knowledge: <ReadOutlined />,
  internet: <GlobalOutlined />,
  plugin: <AppstoreAddOutlined />,
  text_file: <FileOutlined />,
  excel_file: <FileExcelOutlined />,
  image_file: <PictureOutlined />,
  awel_flow: <DeploymentUnitOutlined />,
};

const Config = () => <></>;

export default Config;
