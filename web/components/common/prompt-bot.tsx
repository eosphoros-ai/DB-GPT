import { useState } from 'react';
import { List, FloatButton, Popover, Tooltip, Form, message, Select, ConfigProvider } from 'antd';
import { useRequest } from 'ahooks';
import { sendSpacePostRequest } from '@/utils/request';
import { useTranslation } from 'react-i18next';

type SelectTableProps = {
  data: any;
  loading: boolean;
  submit: (prompt: string) => void;
  close: () => void;
};

const SelectTable: React.FC<SelectTableProps> = ({ data, loading, submit, close }) => {
  const { t } = useTranslation();
  const handleClick = (content: string) => () => {
    submit(content);
    close();
  };

  return (
    <div
      style={{
        maxHeight: 400,
        overflow: 'auto',
      }}
    >
      <List
        dataSource={data?.data}
        loading={loading}
        rowKey={(record: any) => record.prompt_name}
        renderItem={(item) => (
          <List.Item key={item.prompt_name} onClick={handleClick(item.content)}>
            <Tooltip title={item.content}>
              <List.Item.Meta
                style={{ cursor: 'copy' }}
                title={item.prompt_name}
                description={t('Prompt_Info_Scene') + `：${item.chat_scene}，` + t('Prompt_Info_Sub_Scene') + `：${item.sub_chat_scene}`}
              />
            </Tooltip>
          </List.Item>
        )}
      />
    </div>
  );
};

type PromptBotProps = {
  submit: (prompt: string) => void;
};

const PromptBot: React.FC<PromptBotProps> = ({ submit }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState('common');

  const { data, loading } = useRequest(
    () => {
      const body = {
        prompt_type: current,
      };
      return sendSpacePostRequest('/prompt/list', body);
    },
    {
      refreshDeps: [current],
      onError: (err) => {
        message.error(err?.message);
      },
    },
  );

  const close = () => {
    setOpen(false);
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
  };

  const handleChange = (value: string) => {
    setCurrent(value);
  };

  return (
    <ConfigProvider
      theme={{
        components: {
          Popover: {
            minWidth: 250,
          },
        },
      }}
    >
      <Popover
        title={
          <Form.Item label={'Prompt ' + t('Type')}>
            <Select
              style={{ width: 150 }}
              value={current}
              onChange={handleChange}
              options={[
                {
                  label: t('Public') + ' Prompts',
                  value: 'common',
                },
                {
                  label: t('Private') + ' Prompts',
                  value: 'private',
                },
              ]}
            />
          </Form.Item>
        }
        content={<SelectTable {...{ data, loading, submit, close }} />}
        placement="topRight"
        trigger="click"
        open={open}
        onOpenChange={handleOpenChange}
      >
        <Tooltip title={t('Click_Select') + ' Prompt'}>
          <FloatButton className="bottom-[30%]" />
        </Tooltip>
      </Popover>
    </ConfigProvider>
  );
};

export default PromptBot;
