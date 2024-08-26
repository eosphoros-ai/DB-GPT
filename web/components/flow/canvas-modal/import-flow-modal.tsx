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
type FileType = Parameters<GetProp<UploadProps, 'beforeUpload'>>[0];

export const ImportFlowModal: React.FC<Props> = ({
  setNodes,
  setEdges,
  isImportModalOpen,
  setIsImportFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // TODO: Implement onFlowImport
  const onFlowImport = async (values: any) => {
    values.file = values.file?.[0];

    const formData:any = new FormData();
    fileList.forEach((file) => {
      formData.append('file', file as FileType);
    });
    const [, , res] = await apiInterceptors(importFlow(formData));

    if (res?.success) {
      messageApi.success(t("Export_Flow_Success"));
    } else if (res?.err_msg) {
      messageApi.error(res?.err_msg);
    }

    setIsImportFlowModalOpen(false);
  };

  const props: UploadProps = {
    onRemove: (file) => {
      const index = fileList.indexOf(file);
      const newFileList = fileList.slice();
      newFileList.splice(index, 1);
      setFileList(newFileList);
    },
    beforeUpload: (file) => {
      setFileList([...fileList, file]);

      return false;
    },
    fileList,
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
