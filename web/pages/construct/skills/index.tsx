import MarkDownContext from '@/new-components/common/MarkdownContext';
import ConstructLayout from '@/new-components/layout/Construct';
import axios from '@/utils/ctx-axios';
import {
  CloudUploadOutlined,
  DownOutlined,
  EllipsisOutlined,
  GithubOutlined,
  InboxOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  Button,
  Dropdown,
  Form,
  Input,
  MenuProps,
  Modal,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Tree,
  Upload,
  UploadFile,
  UploadProps,
  message,
  theme,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface SkillItem {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  skill_type: string;
  tags: string[];
  type: string;
  file_path: string;
}

interface TreeNode {
  title: string;
  key: string;
  children?: TreeNode[];
}

interface SkillDetail {
  skill_name: string;
  file_path: string;
  root_dir: string;
  tree: TreeNode;
  frontmatter: string;
  instructions: string;
  raw_content: string;
  content_type: string;
  metadata: Record<string, string>;
}

function getSkillEmoji(skillType: string): string {
  switch (skillType) {
    case 'data_analysis':
      return '\u{1F4CA}';
    case 'coding':
      return '\u{1F4BB}';
    case 'web_search':
      return '\u{1F50D}';
    case 'knowledge_qa':
      return '\u{1F4DA}';
    case 'chat':
      return '\u{1F4AC}';
    default:
      return '\u26A1';
  }
}

function toAntTreeData(node: TreeNode): DataNode {
  const result: DataNode = {
    title: node.title,
    key: node.key,
  };
  if (node.children && node.children.length > 0) {
    result.children = node.children.map(toAntTreeData);
  }
  return result;
}

function Skills() {
  const { t } = useTranslation();
  const [searchValue, setSearchValue] = useState('');
  const [officialOnly, setOfficialOnly] = useState(false);
  const [enabledMap, setEnabledMap] = useState<Record<string, boolean>>(() => {
    try {
      return JSON.parse(localStorage.getItem('skills_enabled_map') || '{}');
    } catch {
      return {};
    }
  });
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<SkillItem | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFileList, setUploadFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importForm] = Form.useForm();
  const [githubUrlValue, setGithubUrlValue] = useState('');
  const { token } = theme.useToken();

  const [skillsList, setSkillsList] = useState<SkillItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [skillDetail, setSkillDetail] = useState<SkillDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const listFetchCountRef = useRef(0);

  const fetchSkillsList = useCallback(async () => {
    setListLoading(true);
    const currentFetch = ++listFetchCountRef.current;
    try {
      const response = (await axios.get(`${process.env.API_BASE_URL ?? ''}/api/v1/skills/list`)) as any;
      if (currentFetch !== listFetchCountRef.current) return;
      if (response?.success && Array.isArray(response.data)) {
        setSkillsList(response.data as SkillItem[]);
      } else {
        setSkillsList([]);
      }
    } catch (err) {
      if (currentFetch !== listFetchCountRef.current) return;
      console.error('[Skills] Failed to fetch list:', err);
      setSkillsList([]);
    } finally {
      if (currentFetch === listFetchCountRef.current) {
        setListLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchSkillsList();
  }, [fetchSkillsList]);

  useEffect(() => {
    localStorage.setItem('skills_enabled_map', JSON.stringify(enabledMap));
  }, [enabledMap]);

  const fetchDetail = useCallback(async (skillName: string, filePath: string) => {
    setDetailLoading(true);
    try {
      const response = await (axios.get(`${process.env.API_BASE_URL ?? ''}/api/v1/skills/detail`, {
        params: { skill_name: skillName, file_path: filePath },
      }) as Promise<any>);
      if (response?.success && response.data) {
        setSkillDetail(response.data as SkillDetail);
      } else {
        setSkillDetail(null);
      }
    } catch (err) {
      console.error('[Skills] Failed to fetch detail:', err);
      setSkillDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const filteredSkills = useMemo(() => {
    let list = skillsList;
    if (officialOnly) {
      list = list.filter(s => s.type === 'official');
    }
    if (searchValue.trim()) {
      const q = searchValue.trim().toLowerCase();
      list = list.filter(s => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q));
    }
    return list;
  }, [skillsList, officialOnly, searchValue]);

  const handleCardClick = useCallback(
    (skill: SkillItem) => {
      setSelectedSkill(skill);
      setDetailOpen(true);
      fetchDetail(skill.name, skill.file_path);
    },
    [fetchDetail],
  );

  const handleCloseDetail = useCallback(() => {
    setDetailOpen(false);
    setSelectedSkill(null);
    setSkillDetail(null);
  }, []);

  const handleToggle = useCallback((skillId: string, checked: boolean) => {
    setEnabledMap(prev => ({ ...prev, [skillId]: checked }));
  }, []);

  const handleTreeSelect = useCallback(
    (selectedKeys: React.Key[]) => {
      if (!selectedSkill || selectedKeys.length === 0) return;
      const key = selectedKeys[0] as string;
      // Only fetch if it looks like a file (no children in the tree)
      if (skillDetail?.tree) {
        const findNode = (node: TreeNode, target: string): TreeNode | null => {
          if (node.key === target) return node;
          if (node.children) {
            for (const child of node.children) {
              const found = findNode(child, target);
              if (found) return found;
            }
          }
          return null;
        };
        const targetNode = findNode(skillDetail.tree, key);
        if (targetNode && (!targetNode.children || targetNode.children.length === 0)) {
          const rootDir = skillDetail.root_dir || '';
          const filePath = rootDir ? `${rootDir}/${key}` : key;
          fetchDetail(selectedSkill.name, filePath);
        }
      }
    },
    [selectedSkill, skillDetail, fetchDetail],
  );

  const treeData = useMemo(() => {
    if (!skillDetail?.tree) return [];
    return [toAntTreeData(skillDetail.tree)];
  }, [skillDetail]);

  const handleUpload = useCallback(async () => {
    if (uploadFileList.length === 0) return;
    setUploading(true);
    let successCount = 0;
    for (const f of uploadFileList) {
      const rawFile = f.originFileObj;
      if (!rawFile) {
        message.error(`${f.name}: ${t('skills_file_invalid')}`);
        continue;
      }
      const formData = new FormData();
      formData.append('file', rawFile, rawFile.name);
      try {
        const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/skills/upload`, {
          method: 'POST',
          body: formData,
        });
        const json = await res.json();
        if (json?.success) {
          successCount++;
        } else {
          message.error(`${f.name}: ${json?.err_msg || t('skills_upload_failed')}`);
        }
      } catch (err) {
        console.error('[Skills] Upload error:', err);
        message.error(`${f.name}: ${t('skills_upload_failed')}`);
      }
    }
    setUploading(false);
    if (successCount > 0) {
      message.success(t('skills_upload_success', { count: successCount }));
      setUploadOpen(false);
      setUploadFileList([]);
      fetchSkillsList();
    }
  }, [uploadFileList, fetchSkillsList, t]);

  const uploadProps: UploadProps = {
    multiple: true,
    accept: '.zip,.skill,.md,.yaml,.yml,.json',
    fileList: uploadFileList,
    beforeUpload: file => {
      const entry: UploadFile = {
        uid: file.uid || `${Date.now()}-${file.name}`,
        name: file.name,
        size: file.size,
        type: file.type,
        originFileObj: file as any,
      };
      setUploadFileList(prev => [...prev, entry]);
      return false;
    },
    onRemove: file => {
      setUploadFileList(prev => prev.filter(f => f.uid !== file.uid));
    },
  };

  const isValidGithubUrl = (url: string): boolean => {
    if (!url.trim()) return false;
    try {
      const parsed = new URL(url.trim());
      return ['github.com', 'skills.sh'].some(host => parsed.hostname === host || parsed.hostname.endsWith(`.${host}`));
    } catch {
      return false;
    }
  };

  const handleGithubImport = async () => {
    try {
      const values = await importForm.validateFields();
      setImportLoading(true);
      const res = (await axios.post(
        '/api/v1/skills/import_github',
        { url: values.github_url },
        { timeout: 60000 },
      )) as any;
      if (res?.success) {
        message.success(t('skills_github_import_success'));
        setImportModalVisible(false);
        importForm.resetFields();
        fetchSkillsList();
      } else {
        message.error(res?.err_msg || t('skills_github_import_failed'));
      }
    } catch (e: any) {
      if (e?.errorFields) return; // form validation error, not API error
      message.error(t('skills_github_import_failed'));
    } finally {
      setImportLoading(false);
    }
  };

  const addMenuItems: MenuProps['items'] = [
    {
      key: 'upload',
      icon: <CloudUploadOutlined />,
      label: (
        <div>
          <div className='font-medium'>{t('skills_upload_skill')}</div>
          <div className='text-xs text-gray-400'>{t('skills_upload_skill_desc')}</div>
        </div>
      ),
      onClick: () => setUploadOpen(true),
    },
    {
      key: 'import_github',
      icon: <GithubOutlined />,
      label: (
        <div>
          <div className='font-medium'>{t('skills_import_github')}</div>
          <div className='text-xs text-gray-400'>{t('skills_import_github_desc')}</div>
        </div>
      ),
      onClick: () => setImportModalVisible(true),
    },
  ];

  return (
    <ConstructLayout>
      <Spin spinning={listLoading}>
        <div className='h-screen w-full p-4 md:p-6 overflow-y-auto'>
          {/* Header */}
          <div className='mb-6'>
            <h1 className='text-2xl font-bold text-gray-900 dark:text-white mb-1'>{t('skills')}</h1>
            <p className='text-sm text-gray-500 dark:text-gray-400'>{t('skills_page_subtitle')}</p>
          </div>

          {/* Controls bar */}
          <div className='flex items-center gap-3 mb-6'>
            <Input
              prefix={<SearchOutlined className='text-gray-400' />}
              placeholder={t('skills_search_placeholder')}
              value={searchValue}
              onChange={e => setSearchValue(e.target.value)}
              allowClear
              className='w-[240px] h-[36px] backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 border border-gray-200 rounded-lg dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
            />
            <Tag
              className='cursor-pointer select-none px-3 py-1 rounded-lg text-sm'
              color={officialOnly ? 'blue' : undefined}
              onClick={() => setOfficialOnly(!officialOnly)}
            >
              {officialOnly ? '✓ ' : ''}
              {t('skills_official_tag')}
            </Tag>
            <div className='flex-1' />
            <Dropdown menu={{ items: addMenuItems }} trigger={['click']}>
              <Button className='border-none text-white bg-button-gradient flex items-center' icon={<PlusOutlined />}>
                {t('skills_add_btn')} <DownOutlined className='ml-1 text-[10px]' />
              </Button>
            </Dropdown>
          </div>

          {/* Skill cards grid */}
          {filteredSkills.length === 0 && !listLoading ? (
            <div className='flex items-center justify-center h-60 text-gray-400 dark:text-gray-500'>
              {t('skills_empty')}
            </div>
          ) : (
            <div className='grid grid-cols-1 md:grid-cols-2 gap-4 pb-12'>
              {filteredSkills.map(skill => (
                <div
                  key={skill.id || skill.name}
                  className='backdrop-filter backdrop-blur-lg bg-white bg-opacity-70 border-2 border-white rounded-lg shadow p-5 cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-200 relative group dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
                  onClick={() => handleCardClick(skill)}
                >
                  {/* Toggle switch */}
                  <div className='absolute top-4 right-4 z-10' onClick={e => e.stopPropagation()}>
                    <Switch
                      size='small'
                      checked={enabledMap[skill.id || skill.name] ?? true}
                      onChange={checked => handleToggle(skill.id || skill.name, checked)}
                    />
                  </div>

                  {/* Name + emoji */}
                  <div className='flex items-center gap-2 mb-2 pr-12'>
                    <span className='text-lg'>{getSkillEmoji(skill.skill_type)}</span>
                    <Tooltip title={skill.name}>
                      <span className='font-semibold text-base text-gray-900 dark:text-white line-clamp-1'>
                        {skill.name}
                      </span>
                    </Tooltip>
                  </div>

                  {/* Description */}
                  <p className='text-sm text-gray-500 dark:text-gray-400 line-clamp-2 min-h-[40px] mb-3'>
                    {skill.description || t('no_data')}
                  </p>

                  {/* Footer */}
                  <div className='flex items-center justify-between text-xs text-gray-400 dark:text-gray-500'>
                    <div className='flex items-center gap-2'>
                      {skill.type === 'official' ? (
                        <Tag color='blue' className='text-xs m-0'>
                          {t('skills_official_tag')}
                        </Tag>
                      ) : (
                        <span>@{skill.author || 'unknown'}</span>
                      )}
                      <span>·</span>
                      <span>{t('skills_updated_at', { date: '2026-02-06' })}</span>
                    </div>
                    <div
                      className='opacity-0 group-hover:opacity-100 transition-opacity'
                      onClick={e => e.stopPropagation()}
                    >
                      <EllipsisOutlined className='p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded cursor-pointer' />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Spin>

      {/* Detail Modal */}
      <Modal
        key={selectedSkill?.name || 'detail'}
        open={detailOpen}
        onCancel={handleCloseDetail}
        footer={null}
        width='80vw'
        style={{ maxWidth: 1000, top: 40 }}
        styles={{ body: { padding: 0 } }}
        maskClosable={true}
        destroyOnClose
      >
        {/* Modal Header */}
        <div className='flex items-center justify-between px-5 py-3 border-b border-gray-100 dark:border-gray-700'>
          <div className='flex items-center gap-2'>
            <span className='font-semibold text-base text-gray-900 dark:text-white'>
              {selectedSkill?.name || ''}.skill
            </span>
            <Tag color='blue' className='text-xs'>
              {t('skills_detail_tag')}
            </Tag>
          </div>
          <div className='flex items-center gap-2'>
            <Button type='default' size='small'>
              {t('skills_try_btn')}
            </Button>
            <EllipsisOutlined className='p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded cursor-pointer' />
          </div>
        </div>

        {/* Modal Body */}
        <Spin spinning={detailLoading}>
          <div className='flex' style={{ minHeight: 480 }}>
            {/* Left sidebar — file tree */}
            <div className='w-[220px] border-r border-gray-100 dark:border-gray-700 p-3 overflow-y-auto bg-gray-50 dark:bg-[#2a2f38]'>
              {treeData.length > 0 ? (
                <Tree
                  showLine
                  defaultExpandAll
                  treeData={treeData}
                  onSelect={handleTreeSelect}
                  className='bg-transparent'
                />
              ) : (
                <div className='text-gray-400 text-sm text-center mt-8'>{t('skills_loading')}</div>
              )}
            </div>

            {/* Right content area */}
            <div className='flex-1 overflow-y-auto p-6' style={{ maxHeight: 'calc(80vh - 100px)' }}>
              {skillDetail ? (
                <>
                  {/* YAML frontmatter block */}
                  {skillDetail.frontmatter && (
                    <div className='mb-6 rounded-lg bg-gray-50 dark:bg-[#2a2f38] border border-gray-200 dark:border-gray-700 overflow-hidden'>
                      <div className='flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700'>
                        <Tag className='text-xs m-0'>YAML</Tag>
                      </div>
                      <pre className='p-4 m-0 text-sm font-mono text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap'>
                        <code>{skillDetail.frontmatter}</code>
                      </pre>
                    </div>
                  )}

                  {/* Markdown content */}
                  {skillDetail.instructions && (
                    <div className='prose dark:prose-invert max-w-none'>
                      <MarkDownContext>{skillDetail.instructions}</MarkDownContext>
                    </div>
                  )}

                  {/* Fallback: raw content if no parsed sections */}
                  {!skillDetail.frontmatter && !skillDetail.instructions && skillDetail.raw_content && (
                    <div className='prose dark:prose-invert max-w-none'>
                      <MarkDownContext>{skillDetail.raw_content}</MarkDownContext>
                    </div>
                  )}
                </>
              ) : (
                !detailLoading && (
                  <div className='flex items-center justify-center h-full text-gray-400'>
                    {t('skills_select_file_tip')}
                  </div>
                )
              )}
            </div>
          </div>
        </Spin>
      </Modal>
      {/* Upload Modal */}
      <Modal
        open={uploadOpen}
        onCancel={() => {
          setUploadOpen(false);
          setUploadFileList([]);
        }}
        title={t('skills_upload_modal_title')}
        okText={t('Upload')}
        cancelText={t('cancel')}
        onOk={handleUpload}
        confirmLoading={uploading}
        okButtonProps={{ disabled: uploadFileList.length === 0 }}
        destroyOnClose
      >
        <div className='py-4'>
          <Upload.Dragger {...uploadProps}>
            <p className='ant-upload-drag-icon'>
              <InboxOutlined />
            </p>
            <p className='text-base font-medium'>{t('skills_upload_dragger_text')}</p>
            <p className='text-sm text-gray-400 mt-1'>{t('skills_upload_format_tip')}</p>
          </Upload.Dragger>
        </div>
      </Modal>
      <Modal
        title={null}
        open={importModalVisible}
        onOk={handleGithubImport}
        onCancel={() => {
          setImportModalVisible(false);
          importForm.resetFields();
          setGithubUrlValue('');
        }}
        confirmLoading={importLoading}
        okText={importLoading ? t('skills_github_importing') : t('skills_import_github')}
        cancelText={t('cancel')}
        width={560}
        destroyOnClose
      >
        <div className='flex items-center gap-3 pt-5 pb-4 border-b border-gray-100 dark:border-gray-700 mb-4'>
          <div
            className='flex items-center justify-center w-10 h-10 rounded-xl'
            style={{ background: token.colorPrimaryBg }}
          >
            <GithubOutlined style={{ fontSize: 20, color: token.colorPrimary }} />
          </div>
          <div>
            <h3 className='text-base font-semibold text-gray-900 dark:text-white m-0 leading-tight'>
              {t('skills_import_modal_title')}
            </h3>
            <p className='text-xs text-gray-400 dark:text-gray-500 m-0 mt-0.5'>{t('skills_import_github_desc')}</p>
          </div>
        </div>

        <div
          className='rounded-lg px-3 py-2.5 mb-4'
          style={{
            background: token.colorInfoBg,
            borderLeft: `3px solid ${token.colorInfo}`,
          }}
        >
          <span className='text-xs leading-relaxed' style={{ color: token.colorInfoText }}>
            {t('skills_import_hint')}{' '}
            <code
              className='px-1 py-0.5 rounded text-[11px]'
              style={{
                background: token.colorInfoBgHover,
                color: token.colorInfoActive,
                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
              }}
            >
              SKILL.md
            </code>{' '}
            {t('skills_import_hint_suffix')}
          </span>
        </div>

        <Form form={importForm} layout='vertical'>
          <Form.Item
            name='github_url'
            label={
              <span className='font-medium text-sm text-gray-700 dark:text-gray-300'>
                {t('skills_import_folder_label')}
                <span className='font-normal text-gray-400 dark:text-gray-500 ml-1'>
                  {t('skills_import_folder_hint')}
                </span>
              </span>
            }
            rules={[{ required: true, message: t('skills_import_url_required') }]}
            className='mb-2'
            extra={
              <div className='mt-2 flex flex-col gap-1'>
                <span className='text-xs text-gray-400 dark:text-gray-500'>{t('skills_import_example_label')}</span>
                <code
                  className='text-xs px-2 py-1 rounded block w-fit'
                  style={{
                    background: token.colorFillQuaternary,
                    color: token.colorTextSecondary,
                    fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                  }}
                >
                  https://github.com/owner/repo/tree/main
                </code>
                <code
                  className='text-xs px-2 py-1 rounded block w-fit'
                  style={{
                    background: token.colorFillQuaternary,
                    color: token.colorTextSecondary,
                    fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                  }}
                >
                  https://github.com/owner/repo/tree/main/skills/my-skill
                </code>
              </div>
            }
          >
            <Input
              prefix={<GithubOutlined className='text-gray-400' />}
              placeholder='https://github.com/owner/repo/tree/main'
              size='large'
              value={githubUrlValue}
              onChange={e => setGithubUrlValue(e.target.value)}
              allowClear
              className='rounded-lg'
            />
          </Form.Item>

          {githubUrlValue.trim().length > 0 && (
            <div className='flex items-center gap-1.5 mt-1'>
              {isValidGithubUrl(githubUrlValue) ? (
                <>
                  <span className='inline-block w-1.5 h-1.5 rounded-full' style={{ background: token.colorSuccess }} />
                  <span className='text-xs' style={{ color: token.colorSuccess }}>
                    {t('skills_import_url_valid')}
                  </span>
                </>
              ) : (
                <>
                  <span className='inline-block w-1.5 h-1.5 rounded-full' style={{ background: token.colorWarning }} />
                  <span className='text-xs' style={{ color: token.colorWarning }}>
                    {t('skills_import_url_invalid')}
                  </span>
                </>
              )}
            </div>
          )}
        </Form>
      </Modal>
    </ConstructLayout>
  );
}

export default Skills;
