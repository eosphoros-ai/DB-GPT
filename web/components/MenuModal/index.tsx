import { Menu, Modal, ModalProps } from 'antd';
import React, { useState } from 'react';
type Props = {
  items: Array<{
    key: string;
    label: string;
    onClick?: () => void;
    children?: React.ReactNode;
  }>;
  modal: ModalProps;
};
function MenuModal({ items, modal }: Props) {
  const [currentMenuKey, setCurrentMenuKey] = useState('edit');
  return (
    <Modal {...modal}>
      <div className='flex justify-between gap-4'>
        <div className='w-1/6'>
          <Menu
            className='h-full'
            selectedKeys={[currentMenuKey]}
            mode='inline'
            onSelect={info => {
              setCurrentMenuKey(info.key);
            }}
            inlineCollapsed={false}
            items={items.map(item => ({ key: item.key, label: item.label }))}
          />
        </div>
        <div className='w-5/6'>
          {items.map(item => {
            if (item.key === currentMenuKey) {
              return <React.Fragment key={item.key}>{item.children}</React.Fragment>;
            }
          })}
        </div>
      </div>
    </Modal>
  );
}

export default MenuModal;
