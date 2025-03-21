import { apiInterceptors, getModelList, startModel, stopModel } from '@/client/api';
import ModelForm from '@/components/model/model-form';
import BlurredCard, { InnerDropdown } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { IModelData } from '@/types/model';
import { getModelIcon } from '@/utils/constants';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Modal, Tag, message } from 'antd';
import moment from 'moment';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

function Models() {
  const { t } = useTranslation();
  const [models, setModels] = useState<Array<IModelData>>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState<boolean>(false);

  async function getModels() {
    const [, res] = await apiInterceptors(getModelList());
    setModels(res ?? []);
  }

  async function startTheModel(info: IModelData) {
    if (loading) return;
    const content = t(`confirm_start_model`) + info.model_name;

    showConfirm(t('start_model'), content, async () => {
      setLoading(true);
      const [, , res] = await apiInterceptors(
        startModel({
          host: info.host,
          port: info.port,
          model: info.model_name,
          worker_type: info.worker_type,
          delete_after: false,
          params: {},
        }),
      );
      setLoading(false);
      if (res?.success) {
        message.success(t('start_model_success'));
        await getModels();
      }
    });
  }

  async function stopTheModel(info: IModelData, delete_after = false) {
    if (loading) return;

    const action = delete_after ? 'stop_and_delete' : 'stop';
    const content = t(`confirm_${action}_model`) + info.model_name;
    showConfirm(t(`${action}_model`), content, async () => {
      setLoading(true);
      const [, , res] = await apiInterceptors(
        stopModel({
          host: info.host,
          port: info.port,
          model: info.model_name,
          worker_type: info.worker_type,
          delete_after: delete_after,
          params: {},
        }),
      );
      setLoading(false);
      if (res?.success === true) {
        message.success(t(`${action}_model_success`));
        await getModels();
      }
    });
  }

  const showConfirm = (title: string, content: string, onOk: () => Promise<void>) => {
    Modal.confirm({
      title,
      content,
      onOk: async () => {
        await onOk();
      },
      okButtonProps: {
        className: 'bg-button-gradient',
      },
    });
  };

  useEffect(() => {
    getModels();
  }, []);

  // TODO: unuesed function
  // const onSearch = useDebounceFn(
  //   async (e: any) => {
  //     const v = e.target.value;
  //     await modelSearch({ model_name: v });
  //   },
  //   { wait: 500 },
  // ).run;

  const returnLogo = (name: string) => {
    return getModelIcon(name);
  };

  return (
    <ConstructLayout>
      <div className='px-6 overflow-y-auto'>
        <div className='flex justify-between items-center mb-6'>
          <div className='flex items-center gap-4'>
            {/* <Input
              variant="filled"
              prefix={<SearchOutlined />}
              placeholder={t('please_enter_the_keywords')}
              onChange={onSearch}
              onPressEnter={onSearch}
              allowClear
              className="w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
            /> */}
          </div>

          <div className='flex items-center gap-4'>
            <Button
              className='border-none text-white bg-button-gradient'
              icon={<PlusOutlined />}
              onClick={() => {
                setIsModalOpen(true);
              }}
            >
              {t('create_model')}
            </Button>
          </div>
        </div>

        <div className='flex flex-wrap mx-[-8px] '>
          {models.map(item => (
            <BlurredCard
              logo={returnLogo(item.model_name)}
              description={
                <div className='flex flex-col gap-1 relative text-xs bottom-4'>
                  <div className='flex overflow-hidden'>
                    <p className='w-28 text-gray-500 mr-2'>Host:</p>
                    <p className='flex-1 text-ellipsis'>{item.host}</p>
                  </div>
                  <div className='flex overflow-hidden'>
                    <p className='w-28 text-gray-500 mr-2'>Manage Host:</p>
                    <p className='flex-1 text-ellipsis'>
                      {item.manager_host}:{item.manager_port}
                    </p>
                  </div>
                  <div className='flex overflow-hidden'>
                    <p className='w-28 text-gray-500 mr-2'>Last Heart Beat:</p>
                    <p className='flex-1 text-ellipsis'>{moment(item.last_heartbeat).format('YYYY-MM-DD HH:mm:ss')}</p>
                  </div>
                </div>
              }
              name={item.model_name}
              key={item.model_name}
              RightTop={
                <InnerDropdown
                  menu={{
                    items: [
                      {
                        key: 'stop_model',
                        label: (
                          <span className='text-red-400' onClick={() => stopTheModel(item)}>
                            {t('stop_model')}
                          </span>
                        ),
                      },
                      {
                        key: 'start_model',
                        label: (
                          <span className='text-green-400' onClick={() => startTheModel(item)}>
                            {t('start_model')}
                          </span>
                        ),
                      },
                      {
                        key: 'stop_and_delete_model',
                        label: (
                          <span className='text-red-400' onClick={() => stopTheModel(item, true)}>
                            {t('stop_and_delete_model')}
                          </span>
                        ),
                      },
                    ],
                  }}
                />
              }
              rightTopHover={false}
              Tags={
                <div>
                  <Tag color={item.healthy ? 'green' : 'red'}>{item.healthy ? 'Healthy' : 'Unhealthy'}</Tag>
                  <Tag>{item.worker_type}</Tag>
                </div>
              }
            />
          ))}
        </div>
        <Modal
          width={800}
          open={isModalOpen}
          title={t('create_model')}
          onCancel={() => {
            setIsModalOpen(false);
          }}
          footer={null}
        >
          <ModelForm
            onCancel={() => {
              setIsModalOpen(false);
            }}
            onSuccess={() => {
              setIsModalOpen(false);
              getModels();
            }}
          />
        </Modal>
      </div>
    </ConstructLayout>
  );
}

export default Models;
