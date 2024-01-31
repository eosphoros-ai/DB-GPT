import React from 'react';

const RequiredIcon: React.FC<{ optional?: boolean | undefined }> = ({ optional }) => {
  if (optional) {
    return null;
  }
  return <span className="text-red-600 align-middle inline-block">&nbsp;*</span>;
};

export default RequiredIcon;
