import { FileTextFilled, FileWordTwoTone, IeCircleFilled } from '@ant-design/icons';

export default function DocIcon({ type }: { type: string }) {
  if (type === 'TEXT') {
    return <FileTextFilled className="text-[#2AA3FF] mr-2 !text-lg" />;
  } else if (type === 'DOCUMENT') {
    return <FileWordTwoTone className="text-[#2AA3FF] mr-2 !text-lg" />;
  } else {
    return <IeCircleFilled className="text-[#2AA3FF] mr-2 !text-lg" />;
  }
}
