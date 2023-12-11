import React, { useState } from 'react';
import { IModelData } from '@/types/model';
import { useTranslation } from 'react-i18next';
import SentimentSatisfiedAltIcon from '@mui/icons-material/SentimentSatisfiedAlt';
import SentimentVeryDissatisfiedIcon from '@mui/icons-material/SentimentVeryDissatisfied';
import StopCircleIcon from '@mui/icons-material/StopCircle';
import { Tooltip, message } from 'antd';
import moment from 'moment';
import { apiInterceptors, stopModel } from '@/client/api';
import { renderModelIcon } from '../chat/header/model-selector';

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
    <div className="relative flex flex-col p-1 md:p-2 sm:w-1/2 lg:w-1/3">
      <div className="relative flex items-center p-4 min-w-min rounded-lg justify-between bg-white border-gray-200 border hover:shadow-md dark:border-gray-600 dark:bg-black dark:hover:border-white transition-all text-black dark:text-white">
        <div className="flex flex-col">
          {info.healthy && (
            <Tooltip title="Healthy">
              <SentimentSatisfiedAltIcon className="absolute top-4 right-4 !text-3xl !text-green-600" />
            </Tooltip>
          )}
          {!info.healthy && (
            <Tooltip title="Unhealthy">
              <SentimentVeryDissatisfiedIcon className="absolute top-4 right-4 !text-3xl !text-red-600" />
            </Tooltip>
          )}
          <Tooltip title="Stop Model">
            <StopCircleIcon
              className="absolute right-4 bottom-4 !text-3xl !text-orange-600 cursor-pointer"
              onClick={() => {
                stopTheModel(info);
              }}
            />
          </Tooltip>
          <div className="flex items-center">
            {renderModelIcon(info.model_name, { width: 32, height: 32 })}
            <div className="inline-block ml-2">
              <h3 className="text-lg font-semibold">{info.model_name}</h3>
              <h3 className="text-sm opacity-60">{info.model_type}</h3>
            </div>
          </div>
          <div className="text-sm mt-2">
            <p className="font-semibold">Host:</p>
            <p className="opacity-60">{info.host}</p>
            <p className="font-semibold mt-2">Manage host:</p>
            <p className="opacity-60">
              <span>{info.manager_host}:</span>
              <span>{info.manager_port}</span>
            </p>
            <p className="font-semibold mt-2">Last heart beat:</p>
            <p className="opacity-60">{moment(info.last_heartbeat).format('YYYY-MM-DD HH:MM:SS')}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ModelCard;
