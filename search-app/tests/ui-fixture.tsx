// Local visual verification only. No API calls, corpus data or production route.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { ResponsiveCirclePacking } from '@nivo/circle-packing';
import GraphCanvas from '../src/components/graph/GraphCanvas';
import ChartFrame from '../src/components/graph/ChartFrame';
import { useTheme } from '../src/hooks/useTheme';
import { MarkerType } from 'reactflow';
import '../src/index.css';

const nodes = [
    { id:'a:1', position:{x:0,y:0}, data:{label:'Memoria colectiva', nodeType:'Concept'} },
    { id:'b:2', position:{x:300,y:0}, data:{label:'Archivo oral de la comunidad', nodeType:'DigitalAsset'} },
    { id:'c:3', position:{x:600,y:0}, data:{label:'María Hernández', nodeType:'Person'} },
    { id:'d:4', position:{x:300,y:180}, data:{label:'Identidad y territorio', nodeType:'Concept'} },
];
const edges = [
    {id:'ab',source:'a:1',target:'b:2',data:{relation:'DESCRIBES',weight:.86},markerEnd:{type:MarkerType.ArrowClosed}},
    {id:'bc',source:'b:2',target:'c:3',data:{relation:'FUZZY',weight:0}},
    {id:'ad',source:'a:1',target:'d:4',data:{kind:'serendipity',weight:.52}},
];
function Fixture() {
    const {theme,toggleTheme} = useTheme();
    return <main style={{padding:24}}><h1 style={{fontSize:22}}>Verificación UI · datos sintéticos</h1><button className="btn-secondary" onClick={toggleTheme}>Tema: {theme}</button><div style={{height:650,marginTop:20}}><GraphCanvas title="Memoria, identidad y territorio" nodes={nodes} edges={edges} initialLayout="horizontal"/></div>
    <div style={{height:600,marginTop:24}}><ChartFrame title="Comunidades de prueba" legend={<div className="graph-legend">Círculo exterior: comunidad · interior: concepto</div>}><ResponsiveCirclePacking data={{name:'Root',children:[{name:'Comunidad A',children:[{name:'Memoria',loc:10},{name:'Identidad',loc:5}]},{name:'Comunidad B',children:[{name:'Territorio',loc:7}]}]}} id="name" value="loc" padding={8} colors={['#6961a8','#387d98']} enableLabels animate={false}/></ChartFrame></div>
    </main>;
}
createRoot(document.getElementById('root')!).render(<Fixture/>);
