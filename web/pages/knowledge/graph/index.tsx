import React, { useEffect, useMemo, useRef, useState } from "react";
import { Button, Spin } from "antd";
import { RollbackOutlined } from "@ant-design/icons";
import { apiInterceptors, getGraphVis } from "@/client/api";
import { useRouter } from "next/router";
import { ExtensionCategory, idOf, register } from "@antv/g6";
import type {
  Graph,
  GraphData,
  GraphOptions,
  IPointerEvent,
  PluginOptions,
} from "@antv/g6";
import type { GraphVisResult } from "../../../types/knowledge";
import { Graphin } from "@antv/graphin";
import {
  getCommunityId,
  getNodeDegree,
  getNodeSize,
  isInCommunity,
} from "./util";
import { ConnectedComponent } from "./extension/connected-component";
import { groupBy } from "lodash";

type GraphVisData = GraphVisResult | null;

register(ExtensionCategory.LAYOUT, "connected-component", ConnectedComponent);

const PALETTE = [
  "#5F95FF",
  "#61DDAA",
  "#F6BD16",
  "#7262FD",
  "#78D3F8",
  "#9661BC",
  "#F6903D",
  "#008685",
  "#F08BB4",
];

function GraphVis() {
  const LIMIT = 500;
  const router = useRouter();
  const [data, setData] = useState<GraphVisData>(null);
  const graphRef = useRef<Graph | null>();
  const [isReady, setIsReady] = useState(false);

  const fetchGraphVis = async () => {
    const [_, data] = await apiInterceptors(
      getGraphVis(spaceName as string, { limit: LIMIT })
    );
    setData(data);
  };

  const transformData = (data: GraphVisData): GraphData => {
    if (!data) return { nodes: [], edges: [] };

    const nodes = data.nodes.map((node) => ({ id: node.vid, data: node }));
    const edges = data.edges.map((edge) => ({
      source: edge.src,
      target: edge.dst,
      data: edge,
    }));

    nodes.forEach((datum) => {
      datum.data.communityId = getCommunityId(edges, idOf(datum));
    });

    return { nodes, edges };
  };

  const back = () => {
    router.push(`/knowledge`);
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
      const groupedNodes = groupBy(
        graphData.nodes,
        (node) => node.data!.communityId
      );
      const plugins: PluginOptions = [];
      Object.entries(groupedNodes).forEach(([key, nodes]) => {
        if (nodes.length < 2) return;
        const color = graphRef.current?.getElementRenderStyle(
          idOf(nodes[0])
        ).fill;
        plugins.push({
          key,
          type: "bubble-sets",
          members: nodes.map(idOf),
          stroke: color,
          fill: color,
          fillOpacity: 0.1,
        });
      });

      graphRef.current.setPlugins((prev) => [...prev, ...plugins]);
    }
  }, [isReady]);

  const options: GraphOptions = {
    data: graphData,
    autoFit: "center",
    node: {
      style: (d) => {
        const style = {
          size: getNodeSize(getNodeDegree(graphData.edges!, idOf(d))),
          label: true,
          labelLineWidth: 2,
          labelText: d.id,
          labelFontSize: 10,
          labelBackground: true,
          labelBackgroundFill: "#e5e7eb",
          labelPadding: [0, 6],
          labelBackgroundRadius: 4,
        };
        if (!isInCommunity(graphData, idOf(d))) {
          Object.assign(style, { fill: "#b0b0b0" });
        }
        return style;
      },
      state: {
        inactive: {
          label: false,
        },
      },
      palette: {
        type: "group",
        field: "communityId",
        color: PALETTE,
      },
    },
    edge: {
      style: {
        lineWidth: 1,
        stroke: "#e2e2e2",
        endArrow: true,
        endArrowType: "vee",
        label: true,
        labelFontSize: 8,
        labelBackground: true,
        labelText: (d) => d.data!.label!.toString(),
        labelBackgroundFill: "#e5e7eb",
        labelPadding: [0, 6],
        labelBackgroundRadius: 4,
      },
      state: {
        inactive: {
          label: false,
        },
      },
    },
    behaviors: [
      "drag-canvas",
      "zoom-canvas",
      "drag-element",
      {
        type: "hover-activate",
        degree: 1,
        inactiveState: "inactive",
        enable: (event: IPointerEvent) =>
          ["node", "edge"].includes(event.targetType),
      },
    ],
    animation: false,
    layout: [
      { type: "connected-component" },
      {
        type: "force",
        preventOverlap: true,
        leafCluster: true,
        clustering: false,
        nodeClusterBy: "communityId",
        clusterNodeStrength: 600,
      },
    ],
    transforms: ["process-parallel-edges"],
  };

  if (!data) return <Spin className="h-full justify-center content-center" />;

  return (
    <div className="p-4 h-full overflow-y-scroll relative px-2">
      <Graphin
        ref={(ref) => {
          graphRef.current = ref;
        }}
        style={{ height: "100%", width: "100%" }}
        options={options}
        onReady={() => {
          setIsReady(true);
        }}
      >
        <Button
          style={{ background: "#fff" }}
          onClick={back}
          icon={<RollbackOutlined />}
        >
          Back
        </Button>
      </Graphin>
    </div>
  );
}

export default GraphVis;
