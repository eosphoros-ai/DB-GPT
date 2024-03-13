import { IDocument } from '@/types/knowledge';
import React from 'react';
import { FileDone, FileSync } from '../icons';
import FileError from '../icons/file-error';

interface IProps {
  document: IDocument;
}

export default function FileStatusIcon({ document }: IProps) {
  switch (document.status) {
    case 'RUNNING':
      return <FileSync />;
    case 'FINISHED':
      return <FileDone />;
    case 'FAILED':
      return <FileError />;
    default:
      return <FileDone />;
  }
}
