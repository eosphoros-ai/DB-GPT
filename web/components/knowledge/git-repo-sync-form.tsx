import { apiInterceptors, syncGitRepo } from '@/client/api';
import { Button, Form, Input, Switch, message } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

type FieldType = {
  repo_url: string;
  branch: string;
  exclude_dirs: string;
  include_dirs: string;
  build_graph: boolean;
};

type IProps = {
  spaceName: string;
  onSuccess?: () => void;
};

/**
 * Git 仓库同步表单
 * 在创建 git_repo 类型的知识空间后，配置 Git 仓库并触发同步
 */
export default function GitRepoSyncForm(props: IProps) {
  const { spaceName, onSuccess } = props;
  const { t } = useTranslation();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [form] = Form.useForm();

  const handleFinish = async (fieldsValue: FieldType) => {
    const { repo_url, branch, exclude_dirs, include_dirs, build_graph } = fieldsValue;
    setSpinning(true);
    const [err, data] = await apiInterceptors(
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
        chunk_strategy: 'CHUNK_BY_MARKDOWN_HEADER',
      }),
    );
    setSpinning(false);
    if (err) {
      message.error(t('sync_failed') + ': ' + (err as Error).message);
      return;
    }
    message.success(
      `${t('sync_completed')}: ${data?.indexed ?? 0} ${t('files_indexed')}, ${data?.skipped ?? 0} ${t('skipped')}`,
    );
    onSuccess?.();
  };

  return (
    <div className='mt-4'>
      <div className='flex items-center gap-2 mb-4'>
        <div className='flex items-center justify-center w-9 h-9 rounded-full bg-gray-100 dark:bg-gray-700'>
          <svg width='18' height='18' viewBox='0 0 24 24' fill='#24292F' className='dark:fill-gray-200'>
            <path d='M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943' />
          </svg>
        </div>
        <div>
          <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>Git Repository</span>
          <p className='text-xs text-gray-400 dark:text-gray-500 m-0'>{t('ds_git_repo_desc')}</p>
        </div>
      </div>
      <Form
        form={form}
        size='large'
        layout='vertical'
        name='git_repo_sync'
        initialValues={{ branch: 'main', build_graph: false }}
        onFinish={handleFinish}
        autoComplete='off'
      >
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
        <Form.Item>
          <Button type='primary' htmlType='submit' loading={spinning}>
            {t('Start_Sync')}
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
}
