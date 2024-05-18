import React, { useEffect,useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import euler from 'cytoscape-euler';
import { Button } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
cytoscape.use(euler)
import { apiInterceptors,getGraphVis } from '@/client/api';
import { useRouter } from 'next/router';

const LAYOUTCONFIG = {
  name: 'euler',
  springLength: 340,
  fit: false,
  springCoeff: 0.0008,
  mass: 20,
  dragCoeff: 1,
  gravity: -20,
  pull: 0.009,
  randomize: false,
  padding: 0,
  maxIterations: 1000,
  maxSimulationTime: 4000,    
}

function GraphVis() {
  const myRef = useRef<HTMLDivElement>(null);
  const LIMIT = 500
  const router = useRouter();
  const fetchGraphVis = async () => {
    const [_, data] =  await apiInterceptors(getGraphVis(spaceName as string,{limit:LIMIT}))
    if(myRef.current && data){
      let processedData = processResult(data)
      renderGraphVis(processedData)
    }
  }
  const processResult = (data:{nodes:Array<any>,edges:Array<any>}) => {
    let nodes:any[] = []
    let edges:any[] = []
    data.nodes.forEach((node:any)=>{
      let n = {
        data:{
          id:node.vid,
          displayName:node.vid,
        }
      }
      nodes.push(n)
    })
    data.edges.forEach((edge:any)=>{
      let e = {
        data:{
          id:edge.src+'_'+edge.dst+'_'+edge.label,
          source:edge.src,
          target:edge.dst,
          displayName:edge.label
        }
      }
      edges.push(e)
    })
    return {
      nodes,
      edges
    }
  }
  const renderGraphVis = (data:any)=> {
    let dom = myRef.current as HTMLDivElement
    let cy = cytoscape(
      {
        container:myRef.current,
        elements:data,
        zoom:0.3,
        pixelRatio: 'auto',
        style:[
          {
            selector: 'node',
            style: {
              width: 60,
              height: 60,
              color: '#fff',
              'text-outline-color': '#37D4BE',
              'text-outline-width': 2,
              'text-valign': 'center',
              'text-halign': 'center',
              'background-color': '#37D4BE',
              'label': 'data(displayName)'
            }
          },
          {
            selector: 'edge',
            style: {
              'width': 1,
              color: '#fff',
              'label': 'data(displayName)',
              'line-color': '#66ADFF',
              'font-size': 14,
              'target-arrow-shape': 'vee',
              'control-point-step-size': 40,
              'curve-style': 'bezier',
              'text-background-opacity': 1,
              'text-background-color': '#66ADFF',
              'target-arrow-color': '#66ADFF',
              'text-background-shape': 'roundrectangle',
              'text-border-color': '#000',
              'text-wrap': 'wrap',
              'text-valign': 'top',
              'text-halign': 'center',
              'text-background-padding':'5',
            }
          }
        ]
      }
    )
    cy.layout(LAYOUTCONFIG).run()
    cy.pan({
      x: dom.clientWidth / 2,
      y: dom.clientHeight / 2
     })
  }
  const back = ()=>{
    router.push(`/knowledge`);
  }
  const {
    query: { spaceName },
  } = useRouter();
  useEffect(()=>{
    spaceName && fetchGraphVis()
  })
  return (
    <div className="p-4 h-full overflow-y-scroll relative px-2">
       <div>
        <Button onClick={back} icon={<RollbackOutlined />}> Back </Button>
       </div>
        <div className='h-full w-full' ref={myRef}></div>
    </div>
  );
}

export default GraphVis;
