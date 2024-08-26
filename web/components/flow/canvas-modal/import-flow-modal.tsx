import { Modal, Form, Button, Space, message, Checkbox, Upload } from "antd";
import { apiInterceptors, importFlow } from "@/client/api";
import { Node, Edge } from "reactflow";
import { UploadOutlined } from "@mui/icons-material";
import { t } from "i18next";
import { useTranslation } from "react-i18next";

type Props = {
  isImportModalOpen: boolean;
  setNodes: React.Dispatch<
    React.SetStateAction<Node<any, string | undefined>[]>
  >;
  setEdges: React.Dispatch<React.SetStateAction<Edge<any>[]>>;
  setIsImportFlowModalOpen: (value: boolean) => void;
};

export const ImportFlowModal: React.FC<Props> = ({
  setNodes,
  setEdges,
  isImportModalOpen,
  setIsImportFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  // TODO: Implement onFlowImport
  const onFlowImport = async (values: any) => {
    // const input = document.createElement('input');
    // input.type = 'file';
    // input.accept = '.json';
    // input.onchange = async (e: any) => {
    //   const file = e.target.files[0];
    //   const reader = new FileReader();
    //   reader.onload = async (event) => {
    //     const flowData = JSON.parse(event.target?.result as string) as IFlowData;
    //     setNodes(flowData.nodes);
    //     setEdges(flowData.edges);
    //   };
    //   reader.readAsText(file);
    // };
    // input.click;
    console.log(values);
    values.file = values.file?.[0];

    const [, , res] = await apiInterceptors(importFlow(values));

    if (res?.success) {
      messageApi.success(t("Export_Flow_Success"));
    } else if (res?.err_msg) {
      messageApi.error(res?.err_msg);
    }

    setIsImportFlowModalOpen(false);
  };

  return (
    <>
      <Modal
        title="Import Flow"
        open={isImportModalOpen}
        onCancel={() => setIsImportFlowModalOpen(false)}
        footer={[
          <Button onClick={() => setIsImportFlowModalOpen(false)}>
            {t("cancel")}
          </Button>,
          <Button type="primary" htmlType="submit">
            {t("verify")}
          </Button>,
        ]}
      >
        <Form
          form={form}
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 16 }}
          onFinish={onFlowImport}
        >
          <Form.Item
            name="file"
            label="File"
            valuePropName="fileList"
            getValueFromEvent={(e) => (Array.isArray(e) ? e : e && e.fileList)}
            rules={[{ required: true, message: "Please upload a file" }]}
          >
            <Upload accept=".json,.zip" beforeUpload={() => false} maxCount={1}>
              <Button icon={<UploadOutlined />}> {t("Upload")}</Button>
            </Upload>
          </Form.Item>

          <Form.Item label="save flow" name="save_flow" valuePropName="checked">
            <Checkbox />
          </Form.Item>
        </Form>
      </Modal>

      {contextHolder}
    </>
  );
};
