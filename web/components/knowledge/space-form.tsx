import { I18nKeys } from '@/app/i18n';
import {
  addSpace,
  apiInterceptors,
  getChunkStrategies,
  syncBatchDocument,
  syncGitRepo,
  uploadDocument,
} from '@/client/api';
import { IChunkStrategyResponse, IStorage, StepChangeParams } from '@/types/knowledge';
import { FileTextOutlined, LinkOutlined, ReadOutlined } from '@ant-design/icons';
import { Button, Checkbox, Collapse, Divider, Form, Input, Select, Spin, Switch, Upload, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type DataSourceType = 'DOCUMENT' | 'GIT_REPO' | 'URL' | 'TEXT' | 'YUQUEURL' | 'NOTION';

type FieldType = {
  spaceName: string;
  owner: string;
  description: string;
  storage: string;
  // Index methods - multi-select
  index_methods?: string[];
  // Data source config
  dataSourceType: DataSourceType;
  // Git repo
  repo_url?: string;
  branch?: string;
  exclude_dirs?: string;
  include_dirs?: string;
  build_graph?: boolean;
  // Document upload
  doc_files?: any[];
  // URL / Text / Yuque
  web_url?: string;
  raw_text?: string;
  yuque_url?: string;
  doc_token?: string;
  // Chunk strategy
  chunk_strategy: string;
  chunk_size?: number;
  chunk_overlap?: number;
};

// Index method options — labels/descs are i18n keys resolved at render time
interface IndexMethodDef {
  value: string;
  labelKey: string;
  descKey: string;
  onlyCode?: boolean;
}
const INDEX_METHODS: IndexMethodDef[] = [
  { value: 'VectorStore', labelKey: 'index_vector_store', descKey: 'index_vector_store_desc' },
  { value: 'FullText', labelKey: 'index_full_text', descKey: 'index_full_text_desc' },
  { value: 'KnowledgeGraph', labelKey: 'index_knowledge_graph', descKey: 'index_knowledge_graph_desc', onlyCode: true },
];

type IProps = {
  handleStepChange: (params: StepChangeParams) => void;
  spaceConfig: IStorage | null;
  onSuccess?: () => void;
};

const { Dragger } = Upload;

/* ── Data source card definition ── */
interface DataSourceCardDef {
  key: DataSourceType;
  icon: React.ReactNode;
  color: string;
  bgLight: string;
  bgDark: string;
  disabled?: boolean;
}

const DS_CARDS: DataSourceCardDef[] = [
  {
    key: 'DOCUMENT',
    icon: <FileTextOutlined style={{ fontSize: 22 }} />,
    color: '#1677FF',
    bgLight: '#E6F4FF',
    bgDark: '#111D2C',
  },
  {
    key: 'GIT_REPO',
    icon: (
      <svg width='22' height='22' viewBox='0 0 24 24' fill='currentColor'>
        <path d='M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943' />
      </svg>
    ),
    color: '#24292F',
    bgLight: '#F6F8FA',
    bgDark: '#1C2128',
  },
  {
    key: 'URL',
    icon: <LinkOutlined style={{ fontSize: 22 }} />,
    color: '#722ED1',
    bgLight: '#F9F0FF',
    bgDark: '#1E1326',
  },
  {
    key: 'TEXT',
    icon: <ReadOutlined style={{ fontSize: 22 }} />,
    color: '#FA8C16',
    bgLight: '#FFF7E6',
    bgDark: '#2B2111',
  },
  {
    key: 'YUQUEURL',
    icon: (
      <svg width='22' height='22' viewBox='64 64 896 896' fill='currentColor'>
        <path d='M854.6 370.6c-9.9-39.4 9.9-102.2 73.4-124.4l-67.9-3.6s-25.7-90-143.6-98c-117.9-8.1-195-3-195-3s87.4 55.6 52.4 154.7c-25.6 52.5-65.8 95.6-108.8 144.7-1.3 1.3-2.5 2.6-3.5 3.7C319.4 605 96 860 96 860c245.9 64.4 410.7-6.3 508.2-91.1 20.5-.2 35.9-.3 46.3-.3 135.8 0 250.6-117.6 245.9-248.4-3.2-89.9-31.9-110.2-41.8-149.6z' />
      </svg>
    ),
    color: '#13C2C2',
    bgLight: '#E6FFFB',
    bgDark: '#112123',
    disabled: true,
  },
  {
    key: 'NOTION',
    icon: (
      <svg width='22' height='22' viewBox='0 0 33 34' fill='currentColor'>
        <path d='M3.8051 3.26755L20.5301 2.04319C22.5839 1.86808 23.1124 1.98538 24.4032 2.91756L29.7421 6.64773C30.623 7.28917 30.9165 7.46381 30.9165 8.16307V28.6217C30.9165 29.9038 30.4468 30.6622 28.804 30.7782L9.38138 31.9442C8.14825 32.0027 7.56135 31.8279 6.91556 31.0114L2.98395 25.9405C2.27947 25.0072 1.98651 24.3088 1.98651 23.4918V5.3068C1.98651 4.25826 2.45649 3.38366 3.8051 3.26755Z' />
        <path
          fillRule='evenodd'
          clipRule='evenodd'
          d='M3.64643 1.29903L20.3723 0.0746037C21.3849 -0.0114809 22.3097 -0.0595444 23.1918 0.139197C24.141 0.353054 24.86 0.807308 25.5578 1.31054L30.9002 5.04319L30.9158 5.05461C30.9547 5.08281 30.9968 5.11312 31.0417 5.14536C31.3674 5.37943 31.8354 5.71564 32.1631 6.09295C32.7252 6.73997 32.9031 7.45237 32.9031 8.16303V28.6217C32.9031 29.4467 32.763 30.5442 31.967 31.4425C31.1549 32.3592 30.0175 32.6721 28.9448 32.7479L28.9343 32.7486L9.48857 33.916L9.47602 33.9165C8.79263 33.949 8.01197 33.9383 7.24718 33.6609C6.41395 33.3586 5.82508 32.8277 5.35391 32.2318L5.34799 32.2243L1.40271 27.1359L1.39499 27.1257C0.55231 26.0092 0 24.8994 0 23.4918V5.30675C0 4.51862 0.17342 3.55089 0.82429 2.72219C1.51537 1.84231 2.52546 1.39554 3.6337 1.30013L3.64643 1.29903ZM20.5301 2.04315L3.80509 3.26752C2.45647 3.38361 1.9865 4.25823 1.9865 5.30675V23.4918C1.9865 24.3088 2.27946 25.0072 2.98394 25.9405L6.91553 31.0114C7.56133 31.8279 8.14822 32.0025 9.38137 31.944L28.804 30.7782C30.4468 30.6622 30.9165 29.9039 30.9165 28.6217V8.16303C30.9165 7.50025 30.6529 7.30878 29.8751 6.74438C29.8323 6.71333 29.788 6.68115 29.7421 6.6477L24.4032 2.91752C23.1124 1.98534 22.5839 1.86805 20.5301 2.04315Z'
        />
        <path d='M20.5301 2.04318C22.5838 1.86808 23.1124 1.98541 24.4031 2.91757L29.7421 6.64778C30.623 7.28918 30.9167 7.46383 30.9167 8.16301V28.6217C30.9167 29.9039 30.4468 30.6622 28.804 30.7782L9.38127 31.944C8.14822 32.0025 7.56137 31.8279 6.9156 31.0114L2.98396 25.9405C2.27951 25.0072 1.98647 24.3088 1.98645 23.492V5.30687C1.98645 4.25835 2.45646 3.38365 3.80508 3.26754L20.5301 2.04318ZM28.9214 9.91165C28.9214 9.15462 28.6285 8.74625 27.9818 8.80449L8.91064 9.91165C8.20688 9.97045 7.9722 10.3204 7.9722 11.0779V28.4466C7.97222 29.3801 8.44147 29.7293 9.49759 29.6715L27.7471 28.6217C28.8037 28.5641 28.9214 27.922 28.9214 27.1636V9.91165ZM25.988 12.0096C26.1051 12.5347 25.988 13.0592 25.4588 13.1182L24.5795 13.2926V26.1151C23.816 26.5231 23.1122 26.7563 22.5256 26.7563C21.5863 26.7563 21.351 26.4646 20.6475 25.5908L14.8959 16.6149V25.2992L16.7158 25.7076C16.7158 25.7076 16.7159 26.7563 15.2475 26.7563L11.1994 26.9897C11.0818 26.7563 11.1995 26.1739 11.6101 26.0571L12.6664 25.7662V14.2837L11.1997 14.1668C11.0822 13.6417 11.3751 12.8847 12.1972 12.8259L16.5398 12.5349L22.5256 21.6277V13.5839L20.9993 13.4098C20.8821 12.7679 21.351 12.3018 21.9379 12.244L25.988 12.0096ZM23.816 4.43331C23.2877 4.02552 22.5835 3.55846 21.2343 3.67528L5.15507 4.84121C4.56875 4.89903 4.45158 5.19046 4.68509 5.42409L6.97519 7.23083C7.91323 7.98837 8.26511 7.93069 10.0265 7.81388L26.632 6.82259C26.9842 6.82259 26.6915 6.47348 26.5739 6.41536L23.816 4.43331Z' />
      </svg>
    ),
    color: '#000000',
    bgLight: '#F1F1F1',
    bgDark: '#2D2D2D',
    disabled: true,
  },
];

/**
 * Unified Create Knowledge Space Form.
 *
 * Consolidates all configuration into one window:
 * - Basic info (name, storage, description)
 * - Data source selection (card grid): Document / Git Repo / URL / Text / Yuque
 * - Data source specific config (Git: repo url, branch, codegraph; Document: upload)
 * - Chunk strategy (front-loaded)
 *
 * On submit: creates space → (Git) triggers sync → closes.
 */
export default function SpaceForm(props: IProps) {
  const { t } = useTranslation();
  const { handleStepChange, spaceConfig, onSuccess } = props;
  const [spinning, setSpinning] = useState<boolean>(false);
  const [dataSourceType, setDataSourceType] = useState<DataSourceType>('DOCUMENT');
  const [strategies, setStrategies] = useState<Array<IChunkStrategyResponse>>([]);
  const [files, setFiles] = useState<any[]>([]);

  const [form] = Form.useForm();
  // Reactive watch of index_methods so the build_graph switch shows/hides live
  const indexMethods = Form.useWatch('index_methods', form) as string[] | undefined;
  const hasKnowledgeGraph = !!indexMethods?.includes('KnowledgeGraph');

  useEffect(() => {
    form.setFieldValue('storage', spaceConfig?.[0].name);
  }, [spaceConfig]);

  useEffect(() => {
    (async () => {
      const [err, data] = await apiInterceptors(getChunkStrategies());
      if (err) {
        console.error('Failed to load chunk strategies:', err);
      }
      if (data) {
        setStrategies(data);
      }
    })();
  }, []);

  const isGitRepo = dataSourceType === 'GIT_REPO';
  const isDocument = dataSourceType === 'DOCUMENT';

  // Update index_methods when dataSourceType changes
  useEffect(() => {
    const currentIndexMethods = form.getFieldValue('index_methods') || [];
    if (dataSourceType === 'GIT_REPO') {
      // Git repo: all three index methods available
      if (!currentIndexMethods.includes('KnowledgeGraph')) {
        form.setFieldValue('index_methods', ['VectorStore', 'FullText', 'KnowledgeGraph']);
      }
    } else if (dataSourceType === 'DOCUMENT') {
      // Document: KnowledgeGraph is available (for .md heading hierarchy)
      // Keep current selection; do not force-remove KnowledgeGraph
    } else {
      // Other types: remove KnowledgeGraph
      const filtered = currentIndexMethods.filter((m: string) => m !== 'KnowledgeGraph');
      form.setFieldValue('index_methods', filtered.length > 0 ? filtered : ['VectorStore', 'FullText']);
    }
  }, [dataSourceType]);

  const dataSourceLabels: Record<DataSourceType, { title: string; desc: string }> = useMemo(
    () => ({
      DOCUMENT: { title: t('Document'), desc: t('ds_document_desc') },
      GIT_REPO: { title: 'Git Repository', desc: t('ds_git_repo_desc') },
      URL: { title: t('URL'), desc: t('ds_url_desc') },
      TEXT: { title: t('Text'), desc: t('ds_text_desc') },
      YUQUEURL: { title: t('yuque'), desc: t('ds_yuque_desc') },
      NOTION: { title: 'Notion', desc: t('ds_notion_desc') },
    }),
    [t],
  );

  const handleFinish = async (fieldsValue: FieldType) => {
    const { spaceName, owner, description, storage, dataSourceType: dst, index_methods } = fieldsValue;
    setSpinning(true);

    // 1. Create knowledge space
    // Use first selected index method as primary vector_type
    const primaryIndex = index_methods?.[0] || storage;
    // domain_type defaults to 'Normal' (standard ETL pipeline);
    // GitRepo uses a dedicated domain index pipeline.
    const domain_type = dst === 'GIT_REPO' ? 'GitRepo' : 'Normal';
    const [err, _data, res] = await apiInterceptors(
      addSpace({
        name: spaceName,
        vector_type: primaryIndex,
        owner,
        desc: description,
        domain_type,
        index_methods: index_methods,
      }),
    );
    if (err || !res?.success) {
      setSpinning(false);
      message.error(t('create_failed') + ': ' + (err as Error)?.message);
      return;
    }
    // addSpace v1 API returns [] — use spaceName as the identifier
    // (backend _resolve_space supports both id and name)
    localStorage.setItem('cur_space_id', JSON.stringify(spaceName));

    // 2. For Git Repo, trigger sync immediately
    if (dst === 'GIT_REPO') {
      const { repo_url, branch, exclude_dirs, include_dirs, build_graph, chunk_strategy } = fieldsValue;
      if (!repo_url) {
        setSpinning(false);
        message.error(t('Please_input_the_repo_url'));
        return;
      }
      const [syncErr, syncData] = await apiInterceptors(
        syncGitRepo(spaceName, {
          repo_url,
          branch: branch || 'main',
          exclude_dirs: exclude_dirs
            ? exclude_dirs
                .split(',')
                .map(s => s.trim())
                .filter(Boolean)
            : [],
          include_dirs: include_dirs
            ? include_dirs
                .split(',')
                .map(s => s.trim())
                .filter(Boolean)
            : [],
          build_graph: build_graph ?? false,
          chunk_strategy: chunk_strategy || 'CHUNK_BY_MARKDOWN_HEADER',
        }),
      );
      setSpinning(false);
      if (syncErr) {
        message.error(t('sync_failed') + ': ' + (syncErr as Error).message);
        return;
      }
      message.success(`${t('sync_completed')}: ${syncData?.indexed ?? 0} ${t('files_indexed')}`);
      onSuccess?.();
      handleStepChange({ label: 'finish' });
      return;
    }

    // 3. For Document type, upload files and trigger sync immediately
    if (dst === 'DOCUMENT') {
      if (files.length === 0) {
        setSpinning(false);
        message.error(t('Please_select_file'));
        return;
      }

      // Upload each file
      const uploadedFiles: Array<{ name: string; doc_id: number }> = [];
      let uploadFailed = false;
      for (const file of files) {
        const formData = new FormData();
        formData.append('doc_name', file.name);
        formData.append('doc_file', file);
        formData.append('doc_type', 'DOCUMENT');
        const [uploadErr, docId] = await apiInterceptors(uploadDocument(spaceName, formData));
        if (uploadErr || !docId) {
          uploadFailed = true;
          message.error(t('upload_failed') + ': ' + file.name);
          break;
        }
        uploadedFiles.push({ name: file.name, doc_id: docId });
      }

      if (uploadFailed) {
        setSpinning(false);
        // Still mark as success so user can see the space was created
        onSuccess?.();
        handleStepChange({ label: 'finish' });
        return;
      }

      // Trigger batch sync for all uploaded documents
      const chunkStrategy = fieldsValue.chunk_strategy || 'Automatic';
      const syncParams = uploadedFiles.map(f => ({
        doc_id: f.doc_id,
        name: f.name,
        chunk_parameters: {
          chunk_strategy: chunkStrategy,
          ...(fieldsValue.chunk_size ? { chunk_size: fieldsValue.chunk_size } : {}),
          ...(fieldsValue.chunk_overlap ? { chunk_overlap: fieldsValue.chunk_overlap } : {}),
        },
      }));

      const [syncErr] = await apiInterceptors(syncBatchDocument(spaceName, syncParams));
      setSpinning(false);

      if (syncErr) {
        // Space created + files uploaded successfully, but sync failed/incomplete.
        // Don't block — user can re-sync from the detail page.
        message.warning(t('upload_sync_partial_failed'));
      } else {
        message.success(t('upload_sync_completed'));
      }

      onSuccess?.();
      handleStepChange({ label: 'finish' });
      return;
    }

    // 4. For other types (URL, TEXT, YUQUEURL), forward to upload step
    setSpinning(false);
    handleStepChange({
      label: 'forward',
      spaceName,
      pace: 2,
      docType: dst,
      files,
    });
  };

  return (
    <Spin spinning={spinning}>
      <Form
        form={form}
        size='large'
        className='mt-4'
        layout='vertical'
        name='create_knowledge'
        initialValues={{
          storage: spaceConfig?.[0]?.name,
          dataSourceType: 'DOCUMENT',
          branch: 'main',
          build_graph: false,
          chunk_strategy: 'Automatic',
          index_methods: ['VectorStore', 'FullText', 'KnowledgeGraph'],
        }}
        autoComplete='off'
        onFinish={handleFinish}
      >
        {/* ── Section 1: Basic Info ── */}
        <div className='mb-2 text-base font-semibold text-gray-700 dark:text-gray-300'>
          {t('Knowledge_Space_Config')}
        </div>
        <Form.Item<FieldType>
          label={t('Knowledge_Space_Name')}
          name='spaceName'
          rules={[
            { required: true, message: t('Please_input_the_name') },
            () => ({
              validator(_, value) {
                if (/[^一-龥0-9a-zA-Z_-]/.test(value)) {
                  return Promise.reject(new Error(t('the_name_can_only_contain')));
                }
                return Promise.resolve();
              },
            }),
          ]}
        >
          <Input className='h-12' placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType> className='hidden' label={t('Storage')} name='storage'>
          <Select className='h-12' placeholder={t('Please_select_the_storage')}>
            {spaceConfig?.map((item: any) => (
              <Select.Option key={item.name} value={item.name}>
                {item.desc}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item<FieldType> label={t('Description')} name='description' rules={[{ required: true }]}>
          <Input className='h-12' placeholder={t('Please_input_the_description')} />
        </Form.Item>

        {/* ── Section 1b: Index Methods ── */}
        <div className='mb-3 text-base font-semibold text-gray-700 dark:text-gray-300'>{t('Index_Method')}</div>
        <Form.Item<FieldType> name='index_methods' initialValue={['VectorStore', 'FullText', 'KnowledgeGraph']}>
          <Checkbox.Group
            className='grid grid-cols-3 gap-3 w-full'
            onChange={(values: string[]) => {
              // KnowledgeGraph is only available for GIT_REPO and DOCUMENT types.
              // For other types, remove it from the selection.
              if (dataSourceType !== 'GIT_REPO' && dataSourceType !== 'DOCUMENT') {
                const filtered = values.filter(v => v !== 'KnowledgeGraph');
                form.setFieldValue('index_methods', filtered);
              }
            }}
          >
            {INDEX_METHODS.map(method => {
              // KnowledgeGraph is available for GIT_REPO (code) and DOCUMENT (markdown headings)
              const isCodeOnly = method.onlyCode && dataSourceType !== 'GIT_REPO' && dataSourceType !== 'DOCUMENT';
              const isDisabled = isCodeOnly;
              return (
                <Checkbox
                  key={method.value}
                  value={method.value}
                  disabled={isDisabled}
                  className={`
                    flex items-center gap-3 p-3 rounded-lg border-2 transition-all
                    ${isDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer hover:border-blue-400'}
                  `}
                >
                  <div className='flex flex-col'>
                    <span className='text-sm font-medium'>{t(method.labelKey as I18nKeys)}</span>
                    <span className='text-xs text-gray-400'>{t(method.descKey as I18nKeys)}</span>
                    {method.onlyCode && !isDisabled && (
                      <span className='text-[10px] text-orange-500'>
                        {dataSourceType === 'DOCUMENT' ? t('markdown_only') : t('code_only')}
                      </span>
                    )}
                  </div>
                </Checkbox>
              );
            })}
          </Checkbox.Group>
        </Form.Item>

        <Divider />

        {/* ── Section 2: Data Source — Card Grid ── */}
        <div className='mb-3 text-base font-semibold text-gray-700 dark:text-gray-300'>
          {t('Choose_a_Datasource_type')}
        </div>
        <Form.Item<FieldType> name='dataSourceType' rules={[{ required: true }]}>
          <input type='hidden' />
        </Form.Item>
        <div className='grid grid-cols-3 sm:grid-cols-6 gap-3 mb-2'>
          {DS_CARDS.map(card => {
            const selected = dataSourceType === card.key;
            const label = dataSourceLabels[card.key];
            const isDisabled = card.disabled;
            return (
              <div
                key={card.key}
                onClick={() => {
                  if (isDisabled) return;
                  setDataSourceType(card.key);
                  form.setFieldValue('dataSourceType', card.key);
                }}
                className={`
                  group relative flex flex-col items-center gap-2 rounded-xl p-4 pt-5 pb-4
                  transition-all duration-200 select-none
                  border-2 bg-white dark:bg-gray-800/60
                  ${isDisabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}
                  ${!isDisabled && selected ? 'shadow-md scale-[1.02]' : ''}
                  ${
                    !isDisabled && !selected
                      ? 'border-transparent hover:border-gray-200 dark:hover:border-gray-600 hover:shadow-sm'
                      : ''
                  }
                `}
                style={{
                  borderColor: selected && !isDisabled ? card.color : undefined,
                  background: selected && !isDisabled ? card.bgLight : undefined,
                }}
              >
                {/* Coming soon badge */}
                {isDisabled && (
                  <div className='absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-400 leading-none'>
                    {t('ds_coming_soon')}
                  </div>
                )}
                {/* Icon circle — always uses brand color */}
                <div
                  className='flex items-center justify-center w-11 h-11 rounded-full transition-all duration-200'
                  style={{
                    background: isDisabled ? '#F5F5F5' : card.bgLight,
                    color: isDisabled ? '#D9D9D9' : card.color,
                  }}
                >
                  <span style={{ color: isDisabled ? '#D9D9D9' : card.color }}>{card.icon}</span>
                </div>
                {/* Title */}
                <span
                  className={`text-sm font-medium leading-tight text-center ${selected && !isDisabled ? 'text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'} ${isDisabled ? 'text-gray-400 dark:text-gray-500' : ''}`}
                >
                  {label?.title ?? card.key}
                </span>
                {/* Description */}
                <span className='text-[11px] leading-[14px] text-center text-gray-400 dark:text-gray-500 line-clamp-2 min-h-[28px]'>
                  {label?.desc ?? ''}
                </span>
                {/* Selected indicator — check mark */}
                {selected && !isDisabled && (
                  <div
                    className='absolute top-1.5 right-1.5 flex items-center justify-center w-5 h-5 rounded-full'
                    style={{ background: card.color }}
                  >
                    <svg width='12' height='12' viewBox='0 0 12 12' fill='none'>
                      <path
                        d='M3 6l2.5 2.5L9 4.5'
                        stroke='white'
                        strokeWidth='1.8'
                        strokeLinecap='round'
                        strokeLinejoin='round'
                      />
                    </svg>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Section 2b: Data source specific config ── */}
        {isGitRepo && (
          <div className='rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/60 dark:bg-gray-800/40 p-5 mb-2 mt-3'>
            <div className='flex items-center gap-2 mb-4'>
              <svg width='16' height='16' viewBox='0 0 24 24' fill='#24292F' className='dark:fill-gray-300'>
                <path d='M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943' />
              </svg>
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>Git Repository</span>
              <span className='text-xs text-gray-400 dark:text-gray-500'>— {t('ds_git_repo_desc')}</span>
            </div>
            <Form.Item<FieldType>
              label={t('Repository_URL')}
              name='repo_url'
              rules={[{ required: true, message: t('Please_input_the_repo_url') }]}
            >
              <Input className='h-11' placeholder='https://github.com/org/repo.git' />
            </Form.Item>
            <div className='grid grid-cols-2 gap-4'>
              <Form.Item<FieldType> label={t('Branch')} name='branch'>
                <Input className='h-11' placeholder='main' />
              </Form.Item>
              <Form.Item<FieldType> label={t('Build_CodeGraph')} name='build_graph' valuePropName='checked'>
                <Switch />
              </Form.Item>
            </div>
            <div className='grid grid-cols-2 gap-4'>
              <Form.Item<FieldType> label={t('Exclude_Dirs')} name='exclude_dirs'>
                <Input className='h-11' placeholder='node_modules, .venv, dist' />
              </Form.Item>
              <Form.Item<FieldType> label={t('Include_Dirs')} name='include_dirs'>
                <Input className='h-11' placeholder='src, docs' />
              </Form.Item>
            </div>
          </div>
        )}

        {isDocument && (
          <div className='rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/60 dark:bg-gray-800/40 p-5 mb-2 mt-3'>
            <div className='flex items-center gap-2 mb-4'>
              <FileTextOutlined style={{ color: '#1677FF', fontSize: 16 }} />
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{t('Document')}</span>
              <span className='text-xs text-gray-400 dark:text-gray-500'>— {t('ds_document_desc')}</span>
            </div>
            <Form.Item<FieldType> label={t('Upload_a_document')} name='doc_files'>
              <Dragger
                multiple
                beforeUpload={file => {
                  setFiles(prev => [...prev, file]);
                  return false;
                }}
                onRemove={file => {
                  setFiles(prev => prev.filter(f => f.uid !== file.uid));
                }}
                fileList={files}
              >
                <p className='ant-upload-drag-icon'>
                  <PlusIcon />
                </p>
                <p className='ant-upload-text text-sm text-gray-500 dark:text-gray-400'>
                  {t('click_or_drag_to_upload')}
                </p>
                <p className='ant-upload-hint text-xs text-gray-400'>PDF, PPT, Excel, Word, Text, Markdown, CSV</p>
              </Dragger>
            </Form.Item>
            {hasKnowledgeGraph && (
              <div className='mt-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'>
                <div className='text-xs text-blue-700 dark:text-blue-300'>{t('build_heading_graph_help')}</div>
              </div>
            )}
          </div>
        )}

        {dataSourceType === 'URL' && (
          <div className='rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/60 dark:bg-gray-800/40 p-5 mb-2 mt-3'>
            <div className='flex items-center gap-2 mb-4'>
              <LinkOutlined style={{ color: '#722ED1', fontSize: 16 }} />
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{t('URL')}</span>
              <span className='text-xs text-gray-400 dark:text-gray-500'>— {t('ds_url_desc')}</span>
            </div>
            <Form.Item<FieldType> label='URL' name='web_url' rules={[{ required: true }]}>
              <Input className='h-11' placeholder='https://example.com/page' />
            </Form.Item>
          </div>
        )}

        {dataSourceType === 'TEXT' && (
          <div className='rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/60 dark:bg-gray-800/40 p-5 mb-2 mt-3'>
            <div className='flex items-center gap-2 mb-4'>
              <ReadOutlined style={{ color: '#FA8C16', fontSize: 16 }} />
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{t('Text')}</span>
              <span className='text-xs text-gray-400 dark:text-gray-500'>— {t('ds_text_desc')}</span>
            </div>
            <Form.Item<FieldType> label={t('Text')} name='raw_text' rules={[{ required: true }]}>
              <Input.TextArea rows={4} placeholder={t('Fill your raw text')} />
            </Form.Item>
          </div>
        )}

        {dataSourceType === 'YUQUEURL' && (
          <div className='rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50/60 dark:bg-gray-800/40 p-5 mb-2 mt-3'>
            <div className='flex items-center gap-2 mb-4'>
              <svg width='16' height='16' viewBox='64 64 896 896' fill='#13C2C2' className='dark:fill-teal-400'>
                <path d='M854.6 370.6c-9.9-39.4 9.9-102.2 73.4-124.4l-67.9-3.6s-25.7-90-143.6-98c-117.9-8.1-195-3-195-3s87.4 55.6 52.4 154.7c-25.6 52.5-65.8 95.6-108.8 144.7-1.3 1.3-2.5 2.6-3.5 3.7C319.4 605 96 860 96 860c245.9 64.4 410.7-6.3 508.2-91.1 20.5-.2 35.9-.3 46.3-.3 135.8 0 250.6-117.6 245.9-248.4-3.2-89.9-31.9-110.2-41.8-149.6z' />
              </svg>
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{t('yuque')}</span>
              <span className='text-xs text-gray-400 dark:text-gray-500'>— {t('ds_yuque_desc')}</span>
            </div>
            <Form.Item<FieldType> label={t('yuque')} name='yuque_url' rules={[{ required: true }]}>
              <Input className='h-11' placeholder='https://yuque.antfin.com/group/book/doc' />
            </Form.Item>
            <Form.Item<FieldType> label='Token' name='doc_token'>
              <Input className='h-11' placeholder='yuque token' />
            </Form.Item>
          </div>
        )}

        <Divider />

        {/* ── Section 3: Advanced Settings (collapsed by default) ── */}
        <Collapse
          ghost
          size='small'
          expandIconPosition='end'
          items={[
            {
              key: 'advanced',
              label: (
                <span className='text-sm font-semibold text-gray-500 dark:text-gray-400'>
                  {t('Advanced_Settings') || 'Advanced Settings'}
                </span>
              ),
              children: (
                <div>
                  <div className='mb-2 text-sm text-gray-500 dark:text-gray-400'>{t('Segmentation')}</div>
                  <div className='grid grid-cols-3 gap-4'>
                    <Form.Item<FieldType> label={t('chunk_strategy')} name='chunk_strategy'>
                      <Select className='h-12'>
                        <Select.Option value='Automatic'>Automatic</Select.Option>
                        {strategies.map(s => (
                          <Select.Option key={s.strategy} value={s.strategy}>
                            {s.name}
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.Item<FieldType> label={t('chunk_size')} name='chunk_size'>
                      <Input className='h-12' placeholder='512' type='number' />
                    </Form.Item>
                    <Form.Item<FieldType> label={t('chunk_overlap')} name='chunk_overlap'>
                      <Input className='h-12' placeholder='50' type='number' />
                    </Form.Item>
                  </div>
                </div>
              ),
            },
          ]}
        />

        <Form.Item>
          <div className='flex justify-end gap-3'>
            <Button
              onClick={() => {
                form.resetFields();
                setFiles([]);
              }}
            >
              {t('cancel')}
            </Button>
            <Button type='primary' htmlType='submit' loading={spinning}>
              {isGitRepo ? t('create_and_sync') : isDocument ? t('create_and_upload') : t('Next')}
            </Button>
          </div>
        </Form.Item>
      </Form>
    </Spin>
  );
}

/* ── Small helper: Plus icon for upload ── */
function PlusIcon() {
  return (
    <svg width='48' height='48' viewBox='0 0 48 48' fill='none' xmlns='http://www.w3.org/2000/svg'>
      <rect x='4' y='4' width='40' height='40' rx='8' fill='currentColor' className='text-blue-50 dark:text-gray-700' />
      <path
        d='M24 16v16M16 24h16'
        stroke='currentColor'
        strokeWidth='2.5'
        strokeLinecap='round'
        className='text-blue-400 dark:text-blue-300'
      />
    </svg>
  );
}
