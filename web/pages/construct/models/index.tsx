import BlurredCard from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { apiInterceptors, getModelList, modelSearch, stopModel } from '@/client/api';
import ModelForm from '@/components/model/model-form';
import { IModelData } from '@/types/model';
import { MODEL_ICON_DICT } from '@/utils/constants';
import { PlusOutlined } from '@ant-design/icons';
import { useDebounceFn } from 'ahooks';
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
  async function stopTheModel(info: IModelData) {
    if (loading) {
      return;
    }
    setLoading(true);
    const [, res] = await apiInterceptors(
      stopModel({
        host: info.host,
        port: info.port,
        model: info.model_name,
        worker_type: info.model_type,
        params: {},
      }),
    );
    setLoading(false);
    if (res === true) {
      message.success(t('stop_model_success'));
    }
  }
  useEffect(() => {
    getModels();
  }, []);
  const onSearch = useDebounceFn(
    async (e: any) => {
      let v = e.target.value;
      await modelSearch({ model_name: v });
    },
    { wait: 500 },
  ).run;

  const returnLogo = (name: string) => {
    const formatterModal = name?.replaceAll('-', '_').split('_')[0];
    const dict = Object.keys(MODEL_ICON_DICT);
    for (let i = 0; i < dict.length; i++) {
      const element = dict[i];
      if (formatterModal?.includes(element)) {
        return MODEL_ICON_DICT[element];
      }
    }
    return '/pictures/model.png';
  };

  return (
    <ConstructLayout>
      <div className="px-6 overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
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

          <div className="flex items-center gap-4">
            <Button
              className="border-none text-white bg-button-gradient"
              icon={<PlusOutlined />}
              onClick={() => {
                setIsModalOpen(true);
              }}
            >
              {t('create_model')}
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap mx-[-8px] ">
          {models.map((item) => (
            <BlurredCard
              logo={returnLogo(item.model_name)}
              description={
                <div className="flex flex-col gap-1 relative text-xs bottom-4">
                  <div className="flex overflow-hidden">
                    <p className="w-28 text-gray-500 mr-2">Host:</p>
                    <p className="flex-1 text-ellipsis">{item.host}</p>
                  </div>
                  <div className="flex overflow-hidden">
                    <p className="w-28 text-gray-500 mr-2">Manage Host:</p>
                    <p className="flex-1 text-ellipsis">
                      {item.manager_host}:{item.manager_port}
                    </p>
                  </div>
                  <div className="flex overflow-hidden">
                    <p className="w-28 text-gray-500 mr-2">Last Heart Beat:</p>
                    <p className="flex-1 text-ellipsis">{moment(item.last_heartbeat).format('YYYY-MM-DD')}</p>
                  </div>
                </div>
              }
              name={item.model_name}
              key={item.model_name}
              rightTopHover={false}
              Tags={
                <div>
                  <Tag color={item.healthy ? 'green' : 'red'}>{item.healthy ? 'Healthy' : 'Unhealthy'}</Tag>
                  <Tag>{item.model_type}</Tag>
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
