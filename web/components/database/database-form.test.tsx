import { ConfigurableParams } from '@/types/common';
import { DBOption } from '@/types/db';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DatabaseForm from './database-form';

const api = vi.hoisted(() => ({
  postDbAdd: vi.fn(),
  postDbEdit: vi.fn(),
  postDbTestConnect: vi.fn(),
}));
vi.mock('@/client/api', () => ({ ...api, apiInterceptors: (request: unknown) => request }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ i18n: { language: 'zh' } }) }));

const parameter = (name: string, required = false, defaultValue: string | boolean | number = '') =>
  ({
    param_name: name,
    param_type: typeof defaultValue === 'boolean' ? 'bool' : 'str',
    default_value: defaultValue,
    required,
    ext_metadata: {},
  }) as ConfigurableParams;
const options: DBOption[] = [
  {
    value: 'sqlite',
    label: 'SQLite',
    icon: '',
    parameters: [
      parameter('path', true),
      parameter('check_same_thread', false, true),
      parameter('driver', false, 'sqlite'),
    ],
  },
  {
    value: 'maxcompute',
    label: 'MaxCompute',
    icon: '',
    parameters: [
      parameter('project', true),
      parameter('access_id'),
      parameter('access_key'),
      parameter('endpoint', false, 'https://service.example/api'),
      parameter('driver', false, 'odps'),
    ],
  },
];

beforeEach(() => {
  // jsdom's CSS selector engine does not support Ant Design's :has rules.
  // Geometry is irrelevant to these form/payload tests.
  vi.spyOn(window, 'getComputedStyle').mockReturnValue({
    getPropertyValue: (property: string) => (property === 'box-sizing' ? 'border-box' : '0px'),
    boxSizing: 'border-box',
    paddingTop: '0px',
    paddingBottom: '0px',
    borderTopWidth: '0px',
    borderBottomWidth: '0px',
    fontSize: '14px',
    lineHeight: '20px',
  } as unknown as CSSStyleDeclaration);
  api.postDbTestConnect.mockResolvedValue([null, null]);
  api.postDbAdd.mockResolvedValue([null, null]);
  api.postDbEdit.mockResolvedValue([null, null]);
});

describe('data source connection form', () => {
  it('does not save when an HTTP 200 response reports a connection failure', async () => {
    api.postDbTestConnect.mockResolvedValue([null, null, { success: false, err_msg: '认证失败' }]);
    render(
      <DatabaseForm
        dbTypeList={options}
        choiceDBType='sqlite'
        initialParams={{ path: '/data/orders.db' }}
        onCancel={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '添加数据源' }));
    await screen.findByText('认证失败');
    expect(api.postDbAdd).not.toHaveBeenCalled();
  });

  it('keeps the form open when saving reports a business error', async () => {
    const success = vi.fn();
    api.postDbAdd.mockResolvedValue([null, null, { success: false, err_msg: '连接已存在' }]);
    render(
      <DatabaseForm
        dbTypeList={options}
        choiceDBType='sqlite'
        initialParams={{ path: '/data/orders.db' }}
        onCancel={vi.fn()}
        onSuccess={success}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '添加数据源' }));
    await screen.findByText('连接已存在');
    expect(success).not.toHaveBeenCalled();
  });

  it('loads a preselected connector and includes collapsed defaults when saving', async () => {
    const success = vi.fn();
    render(<DatabaseForm dbTypeList={options} choiceDBType='sqlite' onCancel={vi.fn()} onSuccess={success} />);
    fireEvent.change(screen.getByLabelText('数据库文件路径'), { target: { value: '/data/orders.db' } });
    fireEvent.click(screen.getByRole('button', { name: '添加数据源' }));
    await waitFor(() => expect(success).toHaveBeenCalledOnce());
    expect(api.postDbTestConnect).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'sqlite',
        params: { path: '/data/orders.db', check_same_thread: true, driver: 'sqlite' },
      }),
    );
    expect(api.postDbAdd).toHaveBeenCalledWith(api.postDbTestConnect.mock.calls[0][0]);
  });

  it('preserves false edit values and never changes the shared connector schema', async () => {
    render(
      <DatabaseForm
        dbTypeList={options}
        choiceDBType='sqlite'
        editValue='existing'
        initialParams={{ path: '/data/edited.db', check_same_thread: false }}
        description='Existing connection'
        onCancel={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    await waitFor(() => expect(api.postDbEdit).toHaveBeenCalledOnce());
    expect(api.postDbEdit.mock.calls[0][0]).toMatchObject({
      id: 'existing',
      description: 'Existing connection',
      params: { path: '/data/edited.db', check_same_thread: false },
    });
    expect(options[0].parameters?.[1].default_value).toBe(true);
    expect(api.postDbAdd).not.toHaveBeenCalled();
  });

  it('blocks saving after a failed connection test and clears stale feedback after editing', async () => {
    api.postDbTestConnect.mockResolvedValue([{ message: '连接被拒绝' }]);
    render(
      <DatabaseForm
        dbTypeList={options}
        choiceDBType='sqlite'
        initialParams={{ path: '/data/orders.db' }}
        onCancel={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: '添加数据源' }));
    await screen.findByText('连接被拒绝');
    expect(api.postDbAdd).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('数据库文件路径'), { target: { value: '/data/fixed.db' } });
    expect(screen.queryByText('连接被拒绝')).toBeNull();
  });

  it('clears parameters when switching connectors while preserving the description', async () => {
    render(
      <DatabaseForm
        dbTypeList={options}
        choiceDBType='sqlite'
        initialParams={{ path: '/data/orders.db' }}
        description='Business analytics'
        onCancel={vi.fn()}
        onSuccess={vi.fn()}
      />,
    );
    fireEvent.mouseDown(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByText('MaxCompute'));
    fireEvent.change(await screen.findByLabelText('项目名称'), { target: { value: 'analytics' } });
    fireEvent.click(screen.getByRole('button', { name: '添加数据源' }));
    await waitFor(() => expect(api.postDbAdd).toHaveBeenCalledOnce());
    expect(api.postDbAdd.mock.calls[0][0]).toMatchObject({
      type: 'maxcompute',
      description: 'Business analytics',
      params: { project: 'analytics', driver: 'odps', endpoint: 'https://service.example/api' },
    });
    expect(api.postDbAdd.mock.calls[0][0].params).not.toHaveProperty('path');
    expect(api.postDbAdd.mock.calls[0][0].params).not.toHaveProperty('check_same_thread');
  });
});
