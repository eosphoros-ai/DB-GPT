import { Modal } from 'antd';
import React, { useState } from 'react';

interface IProps {
  handleCancel: () => void;
  open: boolean;
  index: number
}

export default function AgentModal(props: IProps) {
  const { handleCancel, open } = props;

  return (
    <div>
      <Modal title="Basic Modal" open={open} onCancel={handleCancel}>
        Agent Modal
      </Modal>
    </div>
  );
}
