import { Button, Drawer, Input, Tag } from 'antd';
import React, { useState } from 'react';

interface Tags {
  reason: string;
  reason_type: string;
}
const DislikeDrawer: React.FC<{
  open: boolean;
  setFeedbackOpen: React.Dispatch<React.SetStateAction<boolean>>;
  list: Tags[];
  feedback: (params: { feedback_type: string; reason_types?: string[] | undefined; remark?: string | undefined }) => void;
  loading: boolean;
}> = ({ open, setFeedbackOpen, list, feedback, loading }) => {
  const [selectedTags, setSelectedTags] = useState<Tags[]>([]);
  const [remark, setRemark] = useState<string>('');

  return (
    <Drawer title="你的反馈助我进步" placement="bottom" open={open} onClose={() => setFeedbackOpen(false)} destroyOnClose={true} height={'auto'}>
      <div className="flex flex-col w-full gap-4">
        <div className="flex w-full flex-wrap gap-2">
          {list?.map((item) => {
            const isSelect = selectedTags.findIndex((tag) => tag.reason_type === item.reason_type) > -1;
            return (
              <Tag
                key={item.reason_type}
                className={`text-sm text-[#525964] p-1 px-2 rounded-md cursor-pointer ${isSelect ? 'border-[#0c75fc] text-[#0c75fc]' : ''}`}
                onClick={() => {
                  setSelectedTags((preArr: Tags[]) => {
                    const index = preArr.findIndex((tag) => tag.reason_type === item.reason_type);
                    if (index > -1) {
                      return [...preArr.slice(0, index), ...preArr.slice(index + 1)];
                    }
                    return [...preArr, item];
                  });
                }}
              >
                {item.reason}
              </Tag>
            );
          })}
        </div>
        <Input.TextArea
          placeholder="描述一下具体问题或更优的答案"
          className="h-24 resize-none mb-2"
          value={remark}
          onChange={(e) => setRemark(e.target.value.trim())}
        />
        <div className="flex gap-2 justify-end">
          <Button
            className="w-16 h-8"
            onClick={() => {
              setFeedbackOpen(false);
            }}
          >
            取消
          </Button>
          <Button
            type="primary"
            className="min-w-16 h-8"
            onClick={async () => {
              const reason_types = selectedTags.map((item) => item.reason_type);
              await feedback?.({
                feedback_type: 'unlike',
                reason_types,
                remark,
              });
            }}
            loading={loading}
          >
            确认
          </Button>
        </div>
      </div>
    </Drawer>
  );
};

export default DislikeDrawer;
