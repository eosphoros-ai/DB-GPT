import { addFlow, apiInterceptors, getFlowById, updateFlowById } from '@/client/api';
import MuiLoading from '@/components/common/loading';
import AddNodes from '@/components/flow/add-nodes';
import ButtonEdge from '@/components/flow/button-edge';
import CanvasNode from '@/components/flow/canvas-node';
import { IFlowData } from '@/types/flow';
import { getUniqueNodeId, mapHumpToUnderline, mapUnderlineToHump } from '@/utils/flow';
import { SaveOutlined } from '@ant-design/icons';
import { Divider, Input, Modal, message } from 'antd';
import { useSearchParams } from 'next/navigation';
import React, { DragEvent, useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactFlow, { Background, Connection, Controls, ReactFlowProvider, addEdge, useEdgesState, useNodesState, useReactFlow, Node } from 'reactflow';
import 'reactflow/dist/style.css';

interface Props {
  // Define your component props here
}
const nodeTypes = { customNode: CanvasNode };
const edgeTypes = { buttonedge: ButtonEdge };

const Canvas: React.FC<Props> = () => {
  const { t } = useTranslation();
  const [messageApi, contextHolder] = message.useMessage();
  const searchParams = useSearchParams();
  const id = searchParams?.get('id') || '';
  const reactFlow = useReactFlow();

  const [loading, setLoading] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [name, setName] = useState('');

  async function getFlowData() {
    setLoading(true);
    const [_, data] = await apiInterceptors(getFlowById(id));
    if (data) {
      const flowData = mapUnderlineToHump(data.flow_data);
      setName(data.name);
      setNodes(flowData.nodes.map((node) => ({ ...node, type: 'customNode' })));
      setEdges(flowData.edges.map((edge) => ({ ...edge, type: 'buttonedge' })));
    }
    setLoading(false);
  }

  useEffect(() => {
    id && getFlowData();
  }, [id]);

  function onNodesClick(event: any, clickedNode: Node) {
    reactFlow.setNodes((nds) =>
      nds.map((node) => {
        if (node.id === clickedNode.id) {
          node.data = {
            ...node.data,
            selected: true,
          };
        } else {
          node.data = {
            ...node.data,
            selected: false,
          };
        }
        return node;
      }),
    );
  }

  function onConnect(connection: Connection) {
    const newEdge = {
      ...connection,
      type: 'buttonedge',
      id: `${connection.source}|${connection.target}`,
    };
    setEdges((eds) => addEdge(newEdge, eds));
  }

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const reactFlowBounds = reactFlowWrapper.current!.getBoundingClientRect();
      let nodeStr = event.dataTransfer.getData('application/reactflow');
      if (!nodeStr || typeof nodeStr === 'undefined') {
        return;
      }
      const nodeData = JSON.parse(nodeStr);
      const position = reactFlow.screenToFlowPosition({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      });
      const nodeId = getUniqueNodeId(nodeData, reactFlow.getNodes());
      nodeData.id = nodeId;
      const newNode = {
        id: nodeId,
        position,
        type: 'customNode',
        data: nodeData,
      };
      setNodes((nds) =>
        nds.concat(newNode).map((node) => {
          if (node.id === newNode.id) {
            node.data = {
              ...node.data,
              selected: true,
            };
          } else {
            node.data = {
              ...node.data,
              selected: false,
            };
          }
          return node;
        }),
      );
    },
    [reactFlow],
  );

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  function clickSave() {
    if (id) {
      handleSaveFlow();
    } else {
      setIsModalVisible(true);
    }
  }

  async function handleSaveFlow() {
    const reactFlowObject = mapHumpToUnderline(reactFlow.toObject() as IFlowData);
    if (id) {
      const [, , res] = await apiInterceptors(updateFlowById(id, { name, uid: id, flow_data: reactFlowObject }));
      if (res?.success) {
        messageApi.success(t('save_flow_success'));
      } else if (res?.err_msg) {
        messageApi.error(res?.err_msg);
      }
    } else {
      if (!name) {
        return messageApi.warning(t('flow_name_required'));
      }
      const [_, res] = await apiInterceptors(addFlow({ name, flow_data: reactFlowObject }));
      if (res?.uid) {
        messageApi.success(t('save_flow_success'));
        const history = window.history;
        history.pushState(null, '', `/flow/canvas?id=${res.uid}`);
      }
      setIsModalVisible(false);
    }
  }

  return (
    <>
      <MuiLoading visible={loading} />
      <div className="my-2 mx-4 flex flex-row justify-end items-center">
        <div className="w-8 h-8 rounded-md bg-stone-300 dark:bg-zinc-700 dark:text-zinc-200 flext justify-center items-center hover:text-blue-500 dark:hover:text-zinc-100">
          <SaveOutlined className="block text-xl" onClick={clickSave} />
        </div>
      </div>
      <Divider className="mt-0 mb-0" />
      <div className="h-[calc(100vh-60px)] w-full" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodesClick}
          onConnect={onConnect}
          onDrop={onDrop}
          onDragOver={onDragOver}
          minZoom={0.1}
          fitView
          deleteKeyCode={['Backspace', 'Delete']}
        >
          <Controls className="flex flex-row items-center" position="bottom-center" />
          <Background color="#aaa" gap={16} />
          <AddNodes />
        </ReactFlow>
      </div>
      <Modal
        title={t('flow_modal_title')}
        open={isModalVisible}
        onOk={handleSaveFlow}
        onCancel={() => {
          setIsModalVisible(false);
        }}
      >
        <>
          <p>{t('flow_name')}</p>
          <Input
            onChange={(e) => {
              setName(e.target.value);
            }}
          />
        </>
      </Modal>
      {contextHolder}
    </>
  );
};

export default function CanvasWrapper() {
  return (
    <ReactFlowProvider>
      <Canvas />
    </ReactFlowProvider>
  );
}
