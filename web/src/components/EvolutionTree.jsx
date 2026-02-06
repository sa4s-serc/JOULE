import { useEffect, useRef, useState } from 'react';
import { GitBranch, Maximize2, Minimize2, Star, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

const EvolutionTree = ({ paretoData, evaluationHistory, onNodeClick }) => {
    const canvasRef = useRef(null);
    const containerRef = useRef(null);
    const scrollContainerRef = useRef(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [hoveredNode, setHoveredNode] = useState(null);
    const [zoom, setZoom] = useState(1);
    const [selectedNodeId, setSelectedNodeId] = useState(null);

    // Build tree structure from evaluation history with proper parent-child relationships
    const buildTree = () => {
        const generations = {};
        const nodeMap = new Map();

        // First pass: organize by generation and create node map
        evaluationHistory.forEach((ev, idx) => {
            const gen = ev.generation || 0;
            if (!generations[gen]) generations[gen] = [];
            
            const node = {
                id: ev.variant_id || ev.id || `node-${idx}`,
                mutation: ev.mutation || 'Unknown',
                success: ev.success,
                metrics: ev.metrics,
                generation: gen,
                index: idx,
                parentId: ev.parent_id || null,
                isParetoOptimal: paretoData.some(p => 
                    p.variant_id === (ev.variant_id || ev.id) || 
                    p.id === (ev.variant_id || ev.id)
                ),
                children: []
            };
            
            generations[gen].push(node);
            nodeMap.set(node.id, node);
        });

        // Second pass: establish parent-child relationships
        nodeMap.forEach(node => {
            if (node.parentId && nodeMap.has(node.parentId)) {
                const parent = nodeMap.get(node.parentId);
                parent.children.push(node.id);
            }
        });

        return { generations, nodeMap };
    };

    const drawTree = () => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const { generations, nodeMap } = buildTree();
        const genKeys = Object.keys(generations).sort((a, b) => parseInt(a) - parseInt(b));
        
        if (genKeys.length === 0) return;

        // Enhanced visual parameters - calculate based on actual data
        const nodeRadius = 10;
        const paretoRadius = 14;
        const minGenSpacing = 180; // Increased for better visibility
        const verticalPadding = 100;
        const minNodeSpacing = 50; // Increased spacing between nodes
        
        // Calculate total nodes to determine if we need more space
        const maxNodesInGen = Math.max(...genKeys.map(k => generations[k].length));
        
        // Use the dimensions from state (already calculated in useEffect)
        const width = canvas.width;
        const height = canvas.height;
        
        const genSpacing = Math.max(minGenSpacing, width / (genKeys.length + 1));

        // Calculate positions for all nodes with better spacing
        const nodePositions = new Map();
        
        genKeys.forEach((genKey, genIdx) => {
            const gen = generations[genKey];
            const x = genSpacing * (genIdx + 1);
            
            // Calculate vertical spacing based on number of nodes
            const availableHeight = height - 2 * verticalPadding;
            const nodeCount = gen.length;
            const spacing = nodeCount > 1 ? Math.max(minNodeSpacing, availableHeight / (nodeCount - 1)) : 0;
            const totalHeight = spacing * (nodeCount - 1);
            const startY = (height - totalHeight) / 2;
            
            gen.forEach((node, nodeIdx) => {
                const y = nodeCount === 1 ? height / 2 : startY + (nodeIdx * spacing);
                nodePositions.set(node.id, { x, y, node });
            });
        });

        // Draw connections with proper parent-child relationships
        ctx.lineWidth = 2.5;
        
        nodePositions.forEach(({ x, y, node }) => {
            if (node.children && node.children.length > 0) {
                node.children.forEach(childId => {
                    const childPos = nodePositions.get(childId);
                    if (childPos) {
                        // Determine connection color based on relationship
                        const childNode = nodeMap.get(childId);
                        let strokeColor = 'rgba(255, 255, 255, 0.15)';
                        
                        if (node.isParetoOptimal && childNode.isParetoOptimal) {
                            strokeColor = 'rgba(0, 255, 157, 0.5)'; // Pareto to Pareto - brighter
                        } else if (childNode.isParetoOptimal) {
                            strokeColor = 'rgba(0, 255, 157, 0.3)'; // To Pareto
                        } else if (node.success && childNode.success) {
                            strokeColor = 'rgba(0, 184, 255, 0.35)'; // Success to Success
                        }
                        
                        // Draw curved connection
                        ctx.strokeStyle = strokeColor;
                        ctx.beginPath();
                        ctx.moveTo(x, y);
                        
                        // Bezier curve for smoother connections
                        const midX = (x + childPos.x) / 2;
                        ctx.bezierCurveTo(midX, y, midX, childPos.y, childPos.x, childPos.y);
                        ctx.stroke();
                    }
                });
            }
        });

        // Draw nodes with enhanced visuals
        const drawnNodes = [];
        
        nodePositions.forEach(({ x, y, node }) => {
            const radius = node.isParetoOptimal ? paretoRadius : nodeRadius;
            const isSelected = selectedNodeId === node.id;
            
            // Node color based on status
            let fillColor, strokeColor, strokeWidth;
            
            if (node.isParetoOptimal) {
                fillColor = '#00ff9d'; // Pareto optimal - bright green
                strokeColor = isSelected ? '#ffff00' : '#ffffff';
                strokeWidth = isSelected ? 4 : 3;
                
                // Enhanced glow for Pareto optimal
                ctx.shadowColor = fillColor;
                ctx.shadowBlur = isSelected ? 25 : 20;
            } else if (node.success) {
                fillColor = '#00b8ff'; // Valid solution - blue
                strokeColor = isSelected ? '#ffff00' : 'rgba(255, 255, 255, 0.5)';
                strokeWidth = isSelected ? 3 : 2;
                ctx.shadowBlur = isSelected ? 15 : 0;
                ctx.shadowColor = isSelected ? '#ffff00' : 'transparent';
            } else {
                fillColor = '#ff4d4d'; // Failed - red
                strokeColor = isSelected ? '#ffff00' : 'rgba(255, 255, 255, 0.3)';
                strokeWidth = isSelected ? 3 : 1.5;
                ctx.shadowBlur = isSelected ? 15 : 0;
                ctx.shadowColor = isSelected ? '#ffff00' : 'transparent';
            }

            // Draw node circle
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = fillColor;
            ctx.fill();
            ctx.shadowBlur = 0;
            
            // Draw border
            ctx.strokeStyle = strokeColor;
            ctx.lineWidth = strokeWidth;
            ctx.stroke();
            
            // Add star icon for Pareto optimal nodes
            if (node.isParetoOptimal) {
                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('★', x, y);
            }

            drawnNodes.push({ ...node, x, y, radius });
        });

        // Draw generation labels with better styling
        ctx.shadowBlur = 0;
        ctx.fillStyle = '#94a3b8';
        ctx.font = 'bold 14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        
        genKeys.forEach((genKey, genIdx) => {
            const gen = generations[genKey];
            const x = genSpacing * (genIdx + 1);
            const paretoCount = gen.filter(n => n.isParetoOptimal).length;
            const successCount = gen.filter(n => n.success).length;
            
            // Generation number
            ctx.fillStyle = '#e2e8f0';
            ctx.fillText(`Gen ${genKey}`, x, 25);
            
            // Stats below generation number
            ctx.font = '11px Inter, sans-serif';
            ctx.fillStyle = '#64748b';
            ctx.fillText(`${gen.length} nodes`, x, 45);
            
            // Success rate
            ctx.fillStyle = '#94a3b8';
            ctx.fillText(`${successCount} valid`, x, 60);
            
            // Pareto count if any
            if (paretoCount > 0) {
                ctx.fillStyle = '#00ff9d';
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.fillText(`★ ${paretoCount} optimal`, x, 75);
            }
        });

        // Store nodes for interaction
        canvas.drawnNodes = drawnNodes;
    };

    const handleCanvasClick = (e) => {
        const canvas = canvasRef.current;
        if (!canvas || !canvas.drawnNodes) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        // Find clicked node
        const clickedNode = canvas.drawnNodes.find(node => {
            const dx = x - node.x;
            const dy = y - node.y;
            return Math.sqrt(dx * dx + dy * dy) <= node.radius + 5;
        });

        if (clickedNode) {
            setSelectedNodeId(clickedNode.id);
            
            // Find the full evaluation data with code
            const fullData = evaluationHistory.find(ev => 
                (ev.variant_id && ev.variant_id === clickedNode.id) || 
                (ev.id && ev.id === clickedNode.id)
            );
            
            if (onNodeClick) {
                // Pass the complete node data including code
                onNodeClick({
                    ...clickedNode,
                    code: fullData?.code || null,
                    fullData: fullData
                });
            }
            
            // Redraw to show selection
            drawTree();
        }
    };

    const handleCanvasHover = (e) => {
        const canvas = canvasRef.current;
        if (!canvas || !canvas.drawnNodes) return;

        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        // Find hovered node
        const hovered = canvas.drawnNodes.find(node => {
            const dx = x - node.x;
            const dy = y - node.y;
            return Math.sqrt(dx * dx + dy * dy) <= node.radius + 5;
        });

        setHoveredNode(hovered || null);
        canvas.style.cursor = hovered ? 'pointer' : 'default';
    };

    const toggleFullscreen = () => {
        setIsFullscreen(!isFullscreen);
    };

    const handleZoomIn = () => {
        setZoom(prev => Math.min(prev + 0.2, 3));
    };

    const handleZoomOut = () => {
        setZoom(prev => Math.max(prev - 0.2, 0.5));
    };

    const handleResetZoom = () => {
        setZoom(1);
        if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollLeft = 0;
            scrollContainerRef.current.scrollTop = 0;
        }
    };

    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                const rect = containerRef.current.getBoundingClientRect();
                
                // Calculate required dimensions based on data
                const { generations } = buildTree();
                const genKeys = Object.keys(generations);
                const maxNodesInGen = genKeys.length > 0 
                    ? Math.max(...genKeys.map(k => generations[k].length))
                    : 1;
                
                const minGenSpacing = 180;
                const minNodeSpacing = 50;
                const verticalPadding = 100;
                
                // Calculate minimum required dimensions
                const minWidth = Math.max(rect.width, genKeys.length * minGenSpacing + 100);
                const minHeight = Math.max(
                    isFullscreen ? window.innerHeight - 200 : 600,
                    maxNodesInGen * minNodeSpacing + 2 * verticalPadding
                );
                
                setDimensions({
                    width: minWidth,
                    height: minHeight
                });
            }
        };

        updateDimensions();
        window.addEventListener('resize', updateDimensions);
        return () => window.removeEventListener('resize', updateDimensions);
    }, [isFullscreen, evaluationHistory]);

    useEffect(() => {
        drawTree();
    }, [dimensions, paretoData, evaluationHistory, selectedNodeId]);

    return (
        <div 
            ref={containerRef}
            className="card glass" 
            style={{ 
                height: isFullscreen ? 'calc(100vh - 100px)' : '700px',
                position: isFullscreen ? 'fixed' : 'relative',
                top: isFullscreen ? '50px' : 'auto',
                left: isFullscreen ? '50px' : 'auto',
                right: isFullscreen ? '50px' : 'auto',
                zIndex: isFullscreen ? 1000 : 'auto',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
            }}
        >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexShrink: 0 }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <GitBranch size={18} /> Evolutionary Tree
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 'normal' }}>
                        ({evaluationHistory.length} variants across {Object.keys(buildTree().generations).length} generations)
                    </span>
                </h3>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <div style={{ 
                        display: 'flex', 
                        gap: '0.25rem', 
                        background: 'rgba(0, 0, 0, 0.3)',
                        borderRadius: '6px',
                        padding: '0.25rem'
                    }}>
                        <button 
                            className="btn-small" 
                            onClick={handleZoomOut}
                            disabled={zoom <= 0.5}
                            style={{ 
                                padding: '0.4rem',
                                minWidth: 'auto',
                                opacity: zoom <= 0.5 ? 0.5 : 1
                            }}
                            title="Zoom Out"
                        >
                            <ZoomOut size={14} />
                        </button>
                        <button 
                            className="btn-small" 
                            onClick={handleResetZoom}
                            style={{ 
                                padding: '0.4rem 0.6rem',
                                minWidth: 'auto',
                                fontSize: '0.75rem'
                            }}
                            title="Reset Zoom"
                        >
                            {Math.round(zoom * 100)}%
                        </button>
                        <button 
                            className="btn-small" 
                            onClick={handleZoomIn}
                            disabled={zoom >= 3}
                            style={{ 
                                padding: '0.4rem',
                                minWidth: 'auto',
                                opacity: zoom >= 3 ? 0.5 : 1
                            }}
                            title="Zoom In"
                        >
                            <ZoomIn size={14} />
                        </button>
                    </div>
                    <button 
                        className="btn-small" 
                        onClick={toggleFullscreen}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                        {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                        {isFullscreen ? 'Exit' : 'Fullscreen'}
                    </button>
                </div>
            </div>

            <div 
                ref={scrollContainerRef}
                style={{ 
                    flex: 1, 
                    position: 'relative', 
                    overflow: 'auto',
                    minHeight: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    background: 'rgba(0, 0, 0, 0.2)',
                    borderRadius: '8px'
                }}
            >
                <div style={{ 
                    position: 'relative', 
                    minHeight: '100%',
                    minWidth: '100%',
                    display: 'inline-block'
                }}>
                    <canvas
                        ref={canvasRef}
                        width={dimensions.width}
                        height={dimensions.height}
                        onClick={handleCanvasClick}
                        onMouseMove={handleCanvasHover}
                        style={{ 
                            display: 'block',
                            transform: `scale(${zoom})`,
                            transformOrigin: 'top left',
                            imageRendering: 'crisp-edges'
                        }}
                    />

                    {hoveredNode && (
                        <div style={{
                            position: 'absolute',
                            top: '10px',
                            right: '10px',
                            background: 'rgba(13, 17, 26, 0.98)',
                            border: hoveredNode.isParetoOptimal ? '2px solid #00ff9d' : '1px solid var(--border)',
                            borderRadius: '12px',
                            padding: '1rem',
                            fontSize: '0.85rem',
                            maxWidth: '320px',
                            minWidth: '250px',
                            pointerEvents: 'none',
                            zIndex: 10,
                            boxShadow: hoveredNode.isParetoOptimal 
                                ? '0 8px 24px rgba(0, 255, 157, 0.3)' 
                                : '0 4px 12px rgba(0, 0, 0, 0.5)',
                            wordWrap: 'break-word',
                            overflowWrap: 'break-word'
                        }}>
                            {hoveredNode.isParetoOptimal && (
                                <div style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: '0.5rem',
                                    marginBottom: '0.75rem',
                                    padding: '0.5rem',
                                    background: 'rgba(0, 255, 157, 0.1)',
                                    borderRadius: '6px',
                                    color: '#00ff9d',
                                    fontWeight: 'bold',
                                    fontSize: '0.8rem'
                                }}>
                                    <Star size={16} fill="#00ff9d" /> PARETO OPTIMAL
                                </div>
                            )}
                            
                            <div style={{ 
                                fontWeight: 'bold', 
                                marginBottom: '0.75rem', 
                                color: hoveredNode.isParetoOptimal ? '#00ff9d' : 'var(--primary)',
                                fontSize: '0.9rem',
                                wordBreak: 'break-word',
                                overflowWrap: 'break-word',
                                hyphens: 'auto'
                            }}>
                                {hoveredNode.mutation}
                            </div>
                            
                            <div style={{ 
                                display: 'grid', 
                                gap: '0.5rem',
                                padding: '0.75rem',
                                background: 'rgba(0, 0, 0, 0.3)',
                                borderRadius: '6px',
                                fontSize: '0.8rem'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                    <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Generation:</span>
                                    <span style={{ fontWeight: 'bold', color: 'var(--text-main)' }}>
                                        {hoveredNode.generation}
                                    </span>
                                </div>
                                
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                    <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Status:</span>
                                    <span style={{ 
                                        fontWeight: 'bold',
                                        color: hoveredNode.success ? 'var(--success)' : 'var(--danger)'
                                    }}>
                                        {hoveredNode.success ? '✓ Success' : '✗ Failed'}
                                    </span>
                                </div>
                                
                                {hoveredNode.metrics && (
                                    <>
                                        <div style={{ 
                                            height: '1px', 
                                            background: 'rgba(255, 255, 255, 0.1)',
                                            margin: '0.25rem 0'
                                        }} />
                                        
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Energy:</span>
                                            <span style={{ fontFamily: 'monospace', color: '#00ff9d', fontSize: '0.75rem' }}>
                                                {hoveredNode.metrics.energy_joules?.toExponential(3)} J
                                            </span>
                                        </div>
                                        
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Time:</span>
                                            <span style={{ fontFamily: 'monospace', color: '#00b8ff', fontSize: '0.75rem' }}>
                                                {(hoveredNode.metrics.duration_seconds * 1000).toFixed(2)} ms
                                            </span>
                                        </div>
                                    </>
                                )}
                            </div>
                            
                            {hoveredNode.children && hoveredNode.children.length > 0 && (
                                <div style={{ 
                                    marginTop: '0.75rem',
                                    fontSize: '0.75rem',
                                    color: 'var(--text-muted)',
                                    fontStyle: 'italic'
                                }}>
                                    {hoveredNode.children.length} child variant{hoveredNode.children.length > 1 ? 's' : ''}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            <div style={{ 
                marginTop: '1rem', 
                display: 'flex', 
                gap: '2rem', 
                fontSize: '0.8rem',
                justifyContent: 'center',
                alignItems: 'center',
                paddingTop: '1rem',
                borderTop: '1px solid var(--border)',
                flexShrink: 0,
                flexWrap: 'wrap'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ 
                        width: 14, 
                        height: 14, 
                        borderRadius: '50%', 
                        background: '#00ff9d',
                        border: '2px solid #ffffff',
                        boxShadow: '0 0 8px rgba(0, 255, 157, 0.5)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '10px',
                        color: '#fff'
                    }}>★</div>
                    <span style={{ fontWeight: '600' }}>Pareto Optimal</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ 
                        width: 12, 
                        height: 12, 
                        borderRadius: '50%', 
                        background: '#00b8ff',
                        border: '1.5px solid rgba(255, 255, 255, 0.5)'
                    }} />
                    <span>Valid Solution</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ 
                        width: 12, 
                        height: 12, 
                        borderRadius: '50%', 
                        background: '#ff4d4d',
                        border: '1.5px solid rgba(255, 255, 255, 0.3)'
                    }} />
                    <span>Failed</span>
                </div>
                <div style={{ 
                    height: '20px', 
                    width: '1px', 
                    background: 'var(--border)' 
                }} />
                <div style={{ 
                    fontSize: '0.75rem', 
                    color: 'var(--text-muted)',
                    fontStyle: 'italic'
                }}>
                    {paretoData.length} Pareto optimal solution{paretoData.length !== 1 ? 's' : ''} found • Click nodes to view code
                </div>
            </div>
        </div>
    );
};

export default EvolutionTree;
