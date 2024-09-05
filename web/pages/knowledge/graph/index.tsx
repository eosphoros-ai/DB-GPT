import { apiInterceptors, getGraphVis } from '@/client/api';
import { RollbackOutlined } from '@ant-design/icons';
import type { Graph, GraphData, GraphOptions, ID, IPointerEvent, PluginOptions } from '@antv/g6';
import { idOf } from '@antv/g6';
import { Graphin } from '@antv/graphin';
import { Button, Spin } from 'antd';
import { groupBy } from 'lodash';
import { useRouter } from 'next/router';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { GraphVisResult } from '../../../types/knowledge';
import { getDegree, getSize, isInCommunity } from '../../../utils/graph';

type GraphVisData = GraphVisResult | null;

const PALETTE = ['#5F95FF', '#61DDAA', '#F6BD16', '#7262FD', '#78D3F8', '#9661BC', '#F6903D', '#008685', '#F08BB4'];

function GraphVis() {
  const LIMIT = 500;
  const router = useRouter();
  const [data, setData] = useState<GraphVisData>(null);
  const graphRef = useRef<Graph | null>();
  const [isReady, setIsReady] = useState(false);

  const fetchGraphVis = async () => {
    const [_, data] = await apiInterceptors(getGraphVis(spaceName as string, { limit: LIMIT }));
    setData(data);
  };

  const transformData = (data: GraphVisData): GraphData => {
    if (!data) return { nodes: [], edges: [] };

    const nodes = data.nodes.map(node => ({ id: node.id, data: node }));
    const edges = data.edges.map(edge => ({
      source: edge.source,
      target: edge.target,
      data: edge,
    }));

    return { nodes, edges };
  };

  const back = () => {
    router.push(`/construct/knowledge`);
  };

  const {
    query: { spaceName },
  } = useRouter();

  useEffect(() => {
    if (spaceName) fetchGraphVis();
  }, [spaceName]);

  const graphData = useMemo(() => transformData(data), [data]);

  useEffect(() => {
    if (isReady && graphRef.current) {
      const groupedNodes = groupBy(graphData.nodes, node => node.data!.communityId);
      const plugins: PluginOptions = [];
      Object.entries(groupedNodes).forEach(([key, nodes]) => {
        if (!key || nodes.length < 2) return;
        const color = graphRef.current?.getElementRenderStyle(idOf(nodes[0])).fill;
        plugins.push({
          key,
          type: 'bubble-sets',
          members: nodes.map(idOf),
          stroke: color,
          fill: color,
          fillOpacity: 0.1,
        });
      });

      graphRef.current.setPlugins(prev => [...prev, ...plugins]);
    }
  }, [isReady]);

  const getNodeSize = (nodeId: ID) => {
    return getSize(getNodeDegree(nodeId));
  };

  const getNodeDegree = (nodeId?: ID) => {
    if (!nodeId) return 0;
    return getDegree(graphData.edges!, nodeId);
  };

  const options: GraphOptions = {
    data: graphData,
    autoFit: 'center',
    node: {
      style: d => {
        const style = {
          size: getNodeSize(idOf(d)),
          label: true,
          labelLineWidth: 2,
          labelText: d.data?.name as string,
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: '#e5e7eb',
          labelPadding: [0, 6],
          labelBackgroundRadius: 4,
          labelMaxWidth: '400%',
          labelWordWrap: true,
        };
        if (!isInCommunity(graphData, idOf(d))) {
          Object.assign(style, { fill: '#b0b0b0' });
        }
        return style;
      },
      state: {
        active: {
          lineWidth: 2,
          labelWordWrap: false,
          labelFontSize: 12,
          labelFontWeight: 'bold',
        },
        inactive: {
          label: false,
        },
      },
      palette: {
        type: 'group',
        field: 'communityId',
        color: PALETTE,
      },
    },
    edge: {
      style: {
        lineWidth: 1,
        stroke: '#e2e2e2',
        endArrow: true,
        endArrowType: 'vee',
        label: true,
        labelFontSize: 8,
        labelBackground: true,
        labelText: e => e.data!.name as string,
        labelBackgroundFill: '#e5e7eb',
        labelPadding: [0, 6],
        labelBackgroundRadius: 4,
        labelMaxWidth: '60%',
        labelWordWrap: true,
      },
      state: {
        active: {
          stroke: '#b0b0b0',
          labelWordWrap: false,
          labelFontSize: 10,
          labelFontWeight: 'bold',
        },
        inactive: {
          label: false,
        },
      },
    },
    behaviors: [
      'drag-canvas',
      'zoom-canvas',
      'drag-element',
      {
        type: 'hover-activate',
        degree: 1,
        state: 'active',
        enable: (event: IPointerEvent) => ['node'].includes(event.targetType),
      },
    ],
    animation: false,
    layout: {
      type: 'force',
      preventOverlap: true,
      nodeSize: d => getNodeSize(d?.id as ID),
      linkDistance: edge => {
        const { source, target } = edge as { source: ID; target: ID };
        const nodeSize = Math.min(getNodeSize(source), getNodeSize(target));
        const degree = Math.min(getNodeDegree(source), getNodeDegree(target));
        return degree === 1 ? nodeSize * 2 : Math.min(degree * nodeSize * 1.5, 700);
      },
    },
    transforms: ['process-parallel-edges'],
  };

  if (!data) return <Spin className='h-full justify-center content-center' />;

  return (
    <div className='p-4 h-full overflow-y-scroll relative px-2'>
      <Graphin
        ref={ref => {
          graphRef.current = ref;
        }}
        style={{ height: '100%', width: '100%' }}
        options={options}
        onReady={() => {
          setIsReady(true);
        }}
      >
        <Button style={{ background: '#fff' }} onClick={back} icon={<RollbackOutlined />}>
          Back
        </Button>
      </Graphin>
    </div>
  );
}

export default GraphVis;
