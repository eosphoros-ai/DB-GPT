import { FilePdfOutlined } from '@ant-design/icons';
import React from 'react';
// The server-backed download control is replaced with the same attachment identity.
export function AttachmentMessageCards({ files }: { files: Array<{ file_id: string; name: string; size?: number }> }) {
  return <>{files.map(file => <div key={file.file_id} className='flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-700 dark:bg-[#1a1b1e]'><FilePdfOutlined className='text-red-500 text-lg' /><div><div className='text-sm'>{file.name}</div><div className='text-xs text-gray-400'>PDF{file.size === undefined ? '' : ` · ${(file.size / 1024 / 1024).toFixed(1)} MB`}</div></div></div>)}</>;
}
