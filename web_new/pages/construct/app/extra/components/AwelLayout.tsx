import React, { useEffect, useMemo } from 'react';
import cls from 'classnames';
import { Form, Select } from 'antd';
import PreviewFlow from '@/components/flow/preview-flow';
import { useRequest } from 'ahooks';
import { apiInterceptors, getFlows } from '@/client/api';
import { IFlowResponse } from '@/types/flow';
import { useTranslation } from 'react-i18next';

const AwelLayout: React.FC<{ initValue: any; updateData: (data: any) => void; classNames?: string }> = ({ initValue, updateData, classNames }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const flow = Form.useWatch('flow', form);

  const { data, loading } = useRequest(async () => {
    const [, res] = await apiInterceptors(
      getFlows({
        page: 1,
        page_size: 10000,
      }),
    );
    form.setFieldsValue({ flow: initValue?.name });
    return res ?? ({} as IFlowResponse);
  });

  const flowOptions = useMemo(() => {
    return data?.items?.map((item: any) => ({ label: item.label, value: item.name })) || [];
  }, [data]);

  const flowData = useMemo(() => {
    return data?.items?.find((item: any) => item.name === flow)?.flow_data;
  }, [data?.items, flow]);

  useEffect(() => {
    updateData([loading, data?.items?.find((item: any) => item.name === flow)]);
  }, [data?.items, flow, loading, updateData]);

  return (
    <div className={cls(classNames, 'mb-6')}>
      <Form form={form} style={{ width: '100%' }}>
        <Form.Item label={t('select_workflow')} name="flow">
          <Select className="w-1/4" placeholder={t("please_select_workflow")} options={flowOptions} allowClear />
        </Form.Item>
        {flowData && (
          <div className="w-full h-[600px] mx-auto border-[0.5px] border-dark-gray">
            <PreviewFlow flowData={flowData} />
          </div>
        )}
      </Form>
    </div>
  );
};

export default AwelLayout;
