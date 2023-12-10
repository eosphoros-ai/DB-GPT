import { IDocument } from '@/types/knowledge';
import { Button, Tooltip } from 'antd';
import { useRouter } from 'next/router';
import React from 'react';
import FileStatusIcon from '../common/FileStatusIcon';

interface IProps {
  documents: IDocument[];
  dbParam?: string;
}

export default function DocList(props: IProps) {
  const { documents, dbParam } = props;
  const router = useRouter();

  const handleClick = (id: number) => {
    router.push(`/knowledge/chunk/?spaceName=${dbParam}&id=${id}`);
  };

  if (!documents?.length) return null;

  return (
    <div className="absolute flex overflow-scroll h-12 top-[-35px] w-full z-10">
      {documents.map((doc) => {
        let color;
        switch (doc.status) {
          case 'RUNNING':
            color = '#2db7f5';
            break;
          case 'FINISHED':
            color = '#87d068';
            break;
          case 'FAILED':
            color = '#f50';
            break;
          default:
            color = '#87d068';
            break;
        }
        return (
          <Tooltip key={doc.id} title={doc.result}>
            <Button
              style={{ color }}
              onClick={() => {
                handleClick(doc.id);
              }}
              className="shrink flex items-center mr-3"
            >
              <FileStatusIcon document={doc} />
              {doc.doc_name}
            </Button>
          </Tooltip>
        );
      })}
    </div>
  );
}
