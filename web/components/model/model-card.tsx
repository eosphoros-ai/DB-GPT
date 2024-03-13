import React, { useState } from 'react';
import { IModelData } from '@/types/model';
import { useTranslation } from 'react-i18next';
import { message } from 'antd';
import moment from 'moment';
import { apiInterceptors, stopModel } from '@/client/api';
import GptCard from '../common/gpt-card';
import { PauseCircleOutlined } from '@ant-design/icons';
import { MODEL_ICON_MAP } from '@/utils';

interface Props {
  info: IModelData;
}

function ModelCard({ info }: Props) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState<boolean>(false);

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
  return (
    <GptCard
      className="w-96"
      title={info.model_name}
      tags={[
        {
          text: info.healthy ? 'Healthy' : 'Unhealthy',
          color: info.healthy ? 'green' : 'red',
          border: true,
        },
        info.model_type,
      ]}
      icon={MODEL_ICON_MAP[info.model_name]?.icon || '/models/huggingface.svg'}
      operations={[
        {
          children: (
            <div>
              <PauseCircleOutlined className="mr-2" />
              <span className="text-sm">Stop Model</span>
            </div>
          ),
          onClick: () => {
            stopTheModel(info);
          },
        },
      ]}
    >
      <div className="flex flex-col gap-1 px-4 pb-4 text-xs">
        <div className="flex overflow-hidden">
          <p className="w-28 text-gray-500 mr-2">Host:</p>
          <p className="flex-1 text-ellipsis">{info.host}</p>
        </div>
        <div className="flex overflow-hidden">
          <p className="w-28 text-gray-500 mr-2">Manage Host:</p>
          <p className="flex-1 text-ellipsis">
            {info.manager_host}:{info.manager_port}
          </p>
        </div>
        <div className="flex overflow-hidden">
          <p className="w-28 text-gray-500 mr-2">Last Heart Beat:</p>
          <p className="flex-1 text-ellipsis">{moment(info.last_heartbeat).format('YYYY-MM-DD')}</p>
        </div>
      </div>
    </GptCard>
  );
}

export default ModelCard;
