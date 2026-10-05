/** Descriptions verified against backend/app/routers/analysis.py; no calculation here. */
export default function MethodDetails({ method }: { method: 'pathfinder' | 'communities' }) {
    return <details className="method-details"><summary>¿Cómo funciona? · Detalles del método</summary>
        {method === 'pathfinder' ? <>
            <p><strong>Directo:</strong> C(p) = Σ(1 − w). Ordena los caminos por coste ascendente. Si falta el peso, usa 0.5.</p>
            <p><strong>Lateral:</strong> C(p) = Σ f(w,t) + Σ 0.5 log₁₀(grado(n) + 1), para los nodos Concept del camino. f vale 2 si w &gt; t; 1.5 si w &lt; t − 0.3; y 1 − w en otro caso. t es el umbral configurado. Penaliza las conexiones fuera del intervalo; no las elimina.</p>
            <p><strong>Topológico:</strong> minimiza el número de saltos. Con umbral positivo exige w ≥ umbral en todas las aristas; un peso ausente se toma como 1 en ese filtro. Las consultas exploran hasta 8 saltos. Los layouts de esta vista no participan en el cálculo.</p>
        </> : <>
            <p><strong>Standard:</strong> el peso entre conceptos cuenta los archivos compartidos que pasan el umbral. El tamaño de concepto cuenta archivos distintos asociados.</p>
            <p><strong>Fuzzy:</strong> el peso proyectado suma min(w₁,w₂) por archivo compartido. El tamaño suma pesos de relaciones admitidas. Ambos pesos de cada par deben superar el umbral.</p>
            <p>GDS Louvain usa el peso de esa proyección. La respuesta incluye hasta 12 comunidades y 25 conceptos por comunidad; focus y zoom solo actúan sobre esos datos recibidos.</p>
        </>}
    </details>;
}
