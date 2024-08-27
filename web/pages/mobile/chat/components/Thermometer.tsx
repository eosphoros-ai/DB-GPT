import { ControlOutlined } from '@ant-design/icons';
import { Dropdown, Slider } from 'antd';
import React, { useContext } from 'react';
import { MobileChatContext } from '../';
import IconFont from '@/new-components/common/Icon';

const Thermometer: React.FC = () => {
  const { temperature, setTemperature } = useContext(MobileChatContext);

  // temperature变化;
  const onChange = (value: any) => {
    if (isNaN(value)) {
      return;
    }
    setTemperature(value);
  };

  return (
    <Dropdown
      trigger={['click']}
      dropdownRender={() => {
        return (
          <div className="flex h-28 bg-white dark:bg-[rgba(255,255,255,0.5)] items-center justify-center rounded-xl py-3">
            <Slider defaultValue={0.5} max={1.0} min={0.0} step={0.1} vertical={true} onChange={onChange} value={temperature} />
          </div>
        );
      }}
      placement="top"
    >
      <div className="flex items-center justify-between border rounded-xl bg-white dark:bg-black w-14 p-2 flex-shrink-0">
        <IconFont type="icon-icons-temperature" className="text-sm" />
        <span className="text-xs font-medium">{temperature}</span>
      </div>
    </Dropdown>
  );
};

export default Thermometer;
