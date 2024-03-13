/**
 * multi-models selector
 */

import { ChatContext } from '@/app/chat-context';
import { Select } from 'antd';
import { MODEL_ICON_MAP } from '@/utils/constants';
import Image from 'next/image';
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';

interface Props {
  onChange?: (model: string) => void;
}

const DEFAULT_ICON_URL = '/models/huggingface.svg';

export function renderModelIcon(model?: string, props?: { width: number; height: number }) {
  const { width, height } = props || {};

  if (!model) return null;

  return (
    <Image
      className="rounded-full border border-gray-200 object-contain bg-white inline-block"
      width={width || 24}
      height={height || 24}
      src={MODEL_ICON_MAP[model]?.icon || DEFAULT_ICON_URL}
      alt="llm"
    />
  );
}

function ModelSelector({ onChange }: Props) {
  const { t } = useTranslation();
  const { modelList, model } = useContext(ChatContext);
  if (!modelList || modelList.length <= 0) {
    return null;
  }
  return (
    <Select
      value={model}
      placeholder={t('choose_model')}
      className="w-52"
      onChange={(val) => {
        onChange?.(val);
      }}
    >
      {modelList.map((item) => (
        <Select.Option key={item}>
          <div className="flex items-center">
            {renderModelIcon(item)}
            <span className="ml-2">{MODEL_ICON_MAP[item]?.label || item}</span>
          </div>
        </Select.Option>
      ))}
    </Select>
  );
}

export default ModelSelector;
