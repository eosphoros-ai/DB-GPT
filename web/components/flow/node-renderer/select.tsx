import { IFlowNodeParameter } from "@/types/flow";
import { Select } from "antd";

type SelectProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
}

export const RenderSelect = (params: SelectProps) => {
  const { data, defaultValue, onChange } = params;

  return data.options?.length > 0 && (
    <Select
      className="w-full nodrag"
      defaultValue={defaultValue}
      options={data.options.map((item: any) => ({ label: item.label, value: item.value }))}
      onChange={onChange}
    />
  ) 
}
