import React, { useState, useEffect, useRef, useMemo } from 'react';
import { RoadmapTask, RoadmapPhase } from '../types';
import {
  ZoomIn, ZoomOut, Maximize2, RotateCcw, Search,
  Compass, CheckCircle2, Clock, AlertCircle,
  ArrowRight, X, CheckSquare, Square,
  BookOpen, Target, HelpCircle, Layers, SlidersHorizontal
} from 'lucide-react';

interface Props {
  projectName: string;
  stage: string;
  phases: RoadmapPhase[];
  tasks: RoadmapTask[];
  onUpdateTask?: (taskId: string, updates: Partial<RoadmapTask>) => Promise<void>;
}

interface NodePosition {
  task: RoadmapTask;
  x: number;
  y: number;
  width: number;
  height: number;
  isSpine: boolean;
  branch: 'center' | 'left' | 'right';
}

export const RoadmapMindMap: React.FC<Props> = ({
  projectName,
  stage: _stage,
  phases = [],
  tasks = [],
  onUpdateTask
}) => {
  // Mode: Execution vs Learning
  const [roadmapMode, setRoadmapMode] = useState<'execution' | 'learning'>('execution');
  // View mode: Map canvas vs Accessible list
  const [viewMode, setViewMode] = useState<'map' | 'list'>('map');
  // Selected task for inspector drawer
  const [selectedTask, setSelectedTask] = useState<RoadmapTask | null>(null);
  // Search query
  const [searchQuery, setSearchQuery] = useState('');
  // Pan and Zoom transform state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 40, y: 40 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });
  // Legend visibility
  const [showLegend, setShowLegend] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Close inspector on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedTask(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Filter tasks based on search
  const searchMatches = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return tasks.filter(t =>
      (t.title || '').toLowerCase().includes(q) ||
      (t.task_code ? t.task_code.toLowerCase().includes(q) : false) ||
      (t.phase || '').toLowerCase().includes(q) ||
      (t.description ? t.description.toLowerCase().includes(q) : false)
    );
  }, [searchQuery, tasks]);

  // Layout calculation for roadmap.sh map structure
  // Central spine with left and right branch distribution
  const layout = useMemo(() => {
    const NODE_WIDTH = 240;
    const NODE_HEIGHT = 90;
    const HORIZONTAL_GAP = 120;
    const VERTICAL_GAP = 40;
    const CENTER_X = 500;

    const positions: Record<string, NodePosition> = {};

    // Group tasks by phase preserving ordering
    const phaseGroups: { phase: RoadmapPhase; tasks: RoadmapTask[] }[] = [];
    const knownPhases = new Set<string>();

    (phases || []).forEach(p => {
      knownPhases.add(p.name);
      phaseGroups.push({
        phase: p,
        tasks: (tasks || []).filter(t => t.phase === p.name)
      });
    });

    // Unassigned phase tasks
    const unassigned = (tasks || []).filter(t => !knownPhases.has(t.phase));
    if (unassigned.length > 0) {
      phaseGroups.push({
        phase: { name: 'Additional Delivery Work', start_date: '', end_date: '' },
        tasks: unassigned
      });
    }

    let currentY = 60;

    phaseGroups.forEach(group => {
      if (group.tasks.length === 0) return;

      // Identify spine vs side branch tasks
      const spineTasks = group.tasks.filter(t =>
        t.priority === 'Critical' ||
        t.branch_type === 'core_spine' ||
        (!t.branch_type && group.tasks.indexOf(t) === 0)
      );

      const branchTasks = group.tasks.filter(t => !spineTasks.includes(t));

      // Lay out spine tasks down the center
      spineTasks.forEach(task => {
        positions[task.task_code || task.id] = {
          task,
          x: CENTER_X - NODE_WIDTH / 2,
          y: currentY,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
          isSpine: true,
          branch: 'center'
        };
        currentY += NODE_HEIGHT + VERTICAL_GAP;
      });

      // Distribute branch tasks symmetrically on left and right
      let leftY = currentY - (spineTasks.length * (NODE_HEIGHT + VERTICAL_GAP));
      let rightY = leftY;

      branchTasks.forEach((task, idx) => {
        const isLeft = idx % 2 === 0;
        if (isLeft) {
          positions[task.task_code || task.id] = {
            task,
            x: CENTER_X - NODE_WIDTH / 2 - HORIZONTAL_GAP - NODE_WIDTH,
            y: leftY,
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
            isSpine: false,
            branch: 'left'
          };
          leftY += NODE_HEIGHT + 24;
        } else {
          positions[task.task_code || task.id] = {
            task,
            x: CENTER_X + NODE_WIDTH / 2 + HORIZONTAL_GAP,
            y: rightY,
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
            isSpine: false,
            branch: 'right'
          };
          rightY += NODE_HEIGHT + 24;
        }
      });

      currentY = Math.max(currentY, leftY, rightY) + 40;
    });

    // Edges based on dependencies and semantic edge_type
    const edges: {
      fromId: string;
      toId: string;
      fromPos: NodePosition;
      toPos: NodePosition;
      type: 'prerequisite' | 'optional_branch' | 'alternative' | 'parent_group';
    }[] = [];

    tasks.forEach(task => {
      const taskPos = positions[task.task_code || task.id];
      if (!taskPos) return;

      (task.dependencies || []).forEach(depCode => {
        const depPos = positions[depCode] || Object.values(positions).find(p => p.task.task_code === depCode || p.task.id === depCode);
        if (depPos) {
          edges.push({
            fromId: depPos.task.task_code || depPos.task.id,
            toId: task.task_code || task.id,
            fromPos: depPos,
            toPos: taskPos,
            type: task.edge_type === 'optional_branch' ? 'optional_branch' :
                  task.edge_type === 'alternative' ? 'alternative' :
                  task.edge_type === 'parent_group' ? 'parent_group' : 'prerequisite'
          });
        }
      });
    });

    return { positions, edges, totalHeight: currentY + 100 };
  }, [phases, tasks]);

  // Zoom handlers
  const handleZoomIn = () => setZoom(z => Math.min(2.0, z + 0.15));
  const handleZoomOut = () => setZoom(z => Math.max(0.4, z - 0.15));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 40, y: 40 });
  };
  const handleFit = () => {
    if (!containerRef.current) return;
    const containerWidth = containerRef.current.clientWidth;
    const desiredZoom = Math.min(1.0, (containerWidth - 80) / 1100);
    setZoom(Math.max(0.5, desiredZoom));
    setPan({ x: 20, y: 20 });
  };

  // Mouse pan handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.interactive-node') || (e.target as HTMLElement).closest('.control-btn')) {
      return;
    }
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
  };

  const handleMouseUp = () => setIsPanning(false);

  // Jump to searched node
  const handleJumpToNode = (task: RoadmapTask) => {
    setSelectedTask(task);
    const pos = layout.positions[task.task_code || task.id];
    if (pos && containerRef.current) {
      const containerWidth = containerRef.current.clientWidth;
      const targetX = containerWidth / 2 - pos.x * zoom - (pos.width * zoom) / 2;
      const targetY = 200 - pos.y * zoom;
      setPan({ x: targetX, y: targetY });
    }
  };

  // Status toggle handler
  const handleStatusChange = async (task: RoadmapTask, newStatus: RoadmapTask['status']) => {
    if (onUpdateTask) {
      await onUpdateTask(task.id, { status: newStatus });
      setSelectedTask(prev => prev && prev.id === task.id ? { ...prev, status: newStatus } : prev);
    }
  };

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'finished' || s === 'completed') return { badge: '#10b981', border: '#059669', bg: 'rgba(16, 185, 129, 0.12)' };
    if (s === 'in progress' || s === 'ongoing') return { badge: '#3b82f6', border: '#2563eb', bg: 'rgba(59, 130, 246, 0.12)' };
    return { badge: '#6b7280', border: 'var(--border-color)', bg: 'var(--bg-card)' };
  };

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      minHeight: 650,
      background: 'var(--bg-card)',
      borderRadius: 12,
      border: '1px solid var(--border-color)',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Top Map Control Bar */}
      <div style={{
        padding: '12px 18px',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        background: 'var(--bg-subtle)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* View mode toggle */}
          <div style={{
            display: 'inline-flex',
            borderRadius: 8,
            padding: 3,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)'
          }}>
            <button
              onClick={() => setViewMode('map')}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: viewMode === 'map' ? 'var(--primary-color, #2563eb)' : 'transparent',
                color: viewMode === 'map' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Compass size={14} /> Map Canvas
            </button>
            <button
              onClick={() => setViewMode('list')}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: viewMode === 'list' ? 'var(--primary-color, #2563eb)' : 'transparent',
                color: viewMode === 'list' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Layers size={14} /> Accessible Outline
            </button>
          </div>

          {/* Execution vs Learning Roadmap Toggle */}
          <div style={{
            display: 'inline-flex',
            borderRadius: 8,
            padding: 3,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-color)'
          }}>
            <button
              onClick={() => setRoadmapMode('execution')}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: roadmapMode === 'execution' ? 'var(--primary-color, #2563eb)' : 'transparent',
                color: roadmapMode === 'execution' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Target size={14} /> Execution Roadmap
            </button>
            <button
              onClick={() => setRoadmapMode('learning')}
              style={{
                padding: '5px 12px',
                fontSize: 12,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: roadmapMode === 'learning' ? 'var(--primary-color, #2563eb)' : 'transparent',
                color: roadmapMode === 'learning' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <BookOpen size={14} /> Learning Roadmap
            </button>
          </div>
        </div>

        {/* Search, Zoom and Legend Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Search box */}
          <div style={{ position: 'relative', width: 220 }}>
            <Search size={14} style={{ position: 'absolute', left: 9, top: 9, color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search nodes or code..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 28px 6px 30px',
                fontSize: 12,
                borderRadius: 6,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)',
                outline: 'none'
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: 6,
                  top: 7,
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  cursor: 'pointer'
                }}
              >
                <X size={13} />
              </button>
            )}
            {searchQuery && searchMatches.length > 0 && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                marginTop: 4,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-color)',
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                zIndex: 40,
                maxHeight: 200,
                overflowY: 'auto'
              }}>
                {searchMatches.map(m => (
                  <div
                    key={m.id}
                    onClick={() => handleJumpToNode(m)}
                    style={{
                      padding: '8px 12px',
                      fontSize: 12,
                      cursor: 'pointer',
                      borderBottom: '1px solid var(--border-subtle)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 700, marginRight: 6, color: 'var(--primary-color, #2563eb)' }}>{m.task_code}</span>
                      <span>{m.title}</span>
                    </div>
                    <ArrowRight size={12} color="var(--text-muted)" />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Zoom controls */}
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-card)', borderRadius: 6, border: '1px solid var(--border-color)', padding: 2 }}>
            <button className="control-btn" onClick={handleZoomOut} title="Zoom Out" style={{ padding: '4px 8px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-main)' }}>
              <ZoomOut size={14} />
            </button>
            <span style={{ fontSize: 11, padding: '0 6px', fontWeight: 600, color: 'var(--text-muted)' }}>{Math.round(zoom * 100)}%</span>
            <button className="control-btn" onClick={handleZoomIn} title="Zoom In" style={{ padding: '4px 8px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-main)' }}>
              <ZoomIn size={14} />
            </button>
            <button className="control-btn" onClick={handleReset} title="Reset" style={{ padding: '4px 8px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-main)' }}>
              <RotateCcw size={14} />
            </button>
            <button className="control-btn" onClick={handleFit} title="Fit to Map" style={{ padding: '4px 8px', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-main)' }}>
              <Maximize2 size={14} />
            </button>
          </div>

          {/* Legend toggle */}
          <button
            className="control-btn"
            onClick={() => setShowLegend(s => !s)}
            style={{
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 6,
              border: '1px solid var(--border-color)',
              background: showLegend ? 'var(--bg-subtle)' : 'var(--bg-card)',
              color: 'var(--text-main)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5
            }}
          >
            <SlidersHorizontal size={14} /> Legend
          </button>
        </div>
      </div>

      {/* Legend Modal/Dropdown */}
      {showLegend && (
        <div style={{
          position: 'absolute',
          top: 60,
          right: 20,
          zIndex: 35,
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: 8,
          padding: 16,
          boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
          maxWidth: 320,
          fontSize: 12
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 700 }}>Roadmap.sh Visual Syntax</span>
            <X size={14} style={{ cursor: 'pointer' }} onClick={() => setShowLegend(false)} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, color: 'var(--text-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 24, height: 14, borderRadius: 3, border: '2px solid #2563eb', background: 'rgba(37, 99, 235, 0.1)' }} />
              <span><strong>Core Spine:</strong> Critical delivery path</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 24, height: 14, borderRadius: 3, border: '1px dashed #6b7280', background: 'var(--bg-subtle)' }} />
              <span><strong>Optional Branch:</strong> Parallel enhancement</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 24, height: 14, borderRadius: 3, border: '1px solid #8b5cf6', background: 'rgba(139, 92, 246, 0.1)' }} />
              <span><strong>Alternative:</strong> Pivot or secondary strategy</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 24, height: 2, background: '#3b82f6' }} />
              <span><strong>Solid Line:</strong> Prerequisite dependency</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 24, height: 2, borderTop: '2px dashed #9ca3af' }} />
              <span><strong>Dashed Line:</strong> Optional workstream connection</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Content: Map Canvas or Accessible List */}
      {viewMode === 'map' ? (
        <div
          ref={containerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{
            position: 'relative',
            flex: 1,
            minHeight: 600,
            overflow: 'hidden',
            cursor: isPanning ? 'grabbing' : 'grab',
            userSelect: 'none',
            background: 'radial-gradient(circle, rgba(120,120,120,0.12) 1px, transparent 1px) 0 0 / 24px 24px var(--bg-card)'
          }}
        >
          {/* Zoom/Pan Scaled Stage */}
          <div style={{
            position: 'absolute',
            left: 0,
            top: 0,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
            transition: isPanning ? 'none' : 'transform 0.08s ease-out'
          }}>
            {/* SVG Connecting Edges */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: 1200,
                height: layout.totalHeight,
                pointerEvents: 'none',
                overflow: 'visible'
              }}
            >
              <defs>
                <marker
                  id="roadmap-arrow"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="var(--text-muted)" />
                </marker>
                <marker
                  id="roadmap-arrow-active"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="#2563eb" />
                </marker>
              </defs>

              {layout.edges.map((edge, idx) => {
                const startX = edge.fromPos.x + edge.fromPos.width / 2;
                const startY = edge.fromPos.y + edge.fromPos.height;
                const endX = edge.toPos.x + edge.toPos.width / 2;
                const endY = edge.toPos.y;

                // Bezier curve
                const cY1 = startY + Math.max(30, (endY - startY) / 2);
                const cY2 = endY - Math.max(30, (endY - startY) / 2);
                const pathD = `M ${startX} ${startY} C ${startX} ${cY1}, ${endX} ${cY2}, ${endX} ${endY}`;

                const isSelected = selectedTask && (
                  selectedTask.id === edge.fromPos.task.id ||
                  selectedTask.id === edge.toPos.task.id
                );

                return (
                  <path
                    key={`edge-${idx}`}
                    d={pathD}
                    fill="none"
                    stroke={isSelected ? '#2563eb' : edge.type === 'optional_branch' ? '#9ca3af' : 'var(--border-color)'}
                    strokeWidth={isSelected ? 2.5 : edge.type === 'optional_branch' ? 1.5 : 2}
                    strokeDasharray={edge.type === 'optional_branch' ? '5,5' : 'none'}
                    markerEnd={isSelected ? 'url(#roadmap-arrow-active)' : 'url(#roadmap-arrow)'}
                  />
                );
              })}
            </svg>

            {/* Nodes */}
            {Object.values(layout.positions).map(pos => {
              const task = pos.task;
              const isSelected = selectedTask?.id === task.id;
              const isMatch = searchMatches.some(m => m.id === task.id);
              const statusCfg = getStatusColor(task.status);

              return (
                <div
                  key={task.id}
                  className="interactive-node"
                  onClick={() => setSelectedTask(task)}
                  style={{
                    position: 'absolute',
                    left: pos.x,
                    top: pos.y,
                    width: pos.width,
                    minHeight: pos.height,
                    borderRadius: 10,
                    padding: '10px 14px',
                    background: isSelected ? 'var(--bg-subtle)' : statusCfg.bg,
                    border: isSelected
                      ? '2px solid var(--primary-color, #2563eb)'
                      : pos.isSpine
                      ? '2px solid #2563eb'
                      : `1px solid ${statusCfg.border}`,
                    boxShadow: isSelected
                      ? '0 0 0 3px rgba(37,99,235,0.2), 0 8px 24px rgba(0,0,0,0.12)'
                      : isMatch
                      ? '0 0 0 3px rgba(245, 158, 11, 0.4)'
                      : '0 2px 8px rgba(0,0,0,0.06)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    boxSizing: 'border-box'
                  }}
                >
                  {/* Node Header: Code, Priority, Mode tag */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: pos.isSpine ? '#2563eb' : 'var(--border-color)',
                        color: pos.isSpine ? '#fff' : 'var(--text-main)'
                      }}>
                        {task.task_code || 'TASK'}
                      </span>
                      {pos.isSpine && (
                        <span style={{ fontSize: 9.5, fontWeight: 600, color: '#2563eb' }}>Core Path</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        background: statusCfg.badge
                      }} />
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{task.status}</span>
                    </div>
                  </div>

                  {/* Title */}
                  <div style={{
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: 'var(--text-main)',
                    lineHeight: 1.35,
                    marginBottom: 8
                  }}>
                    {task.title}
                  </div>

                  {/* Footer: mode-specific info */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10.5, color: 'var(--text-muted)' }}>
                    {roadmapMode === 'execution' ? (
                      <>
                        <span>{task.effort || task.timeline || '1-2 wks'}</span>
                        <span>{task.assigned_role || 'Lead'}</span>
                      </>
                    ) : (
                      <>
                        <span>Skill: Delivery</span>
                        <span>Prereqs: {task.dependencies?.length || 0}</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Accessible Structured Outline View */
        <div style={{ padding: 24, overflowY: 'auto', flex: 1 }}>
          <h4 style={{ margin: '0 0 16px 0', fontSize: 15, fontWeight: 700 }}>
            {projectName} — Accessible Roadmap Outline
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {(phases.length > 0 ? phases : Array.from(new Set(tasks.map(t => t.phase))).map(name => ({ name, start_date: '', end_date: '' }))).map(phase => {
              const phaseTasks = tasks.filter(t => t.phase === phase.name);
              return (
                <div key={phase.name} style={{ border: '1px solid var(--border-color)', borderRadius: 8, padding: 16 }}>
                  <h5 style={{ margin: '0 0 10px 0', fontSize: 14, fontWeight: 600 }}>{phase.name}</h5>
                  <ul style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {phaseTasks.map(t => (
                      <li key={t.id} style={{ fontSize: 13 }}>
                        <strong>[{t.task_code}]</strong> {t.title} — <em>{t.status}</em> ({t.priority} Priority)
                        {t.definition_of_done && (
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                            Done when: {t.definition_of_done}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Node Inspector Drawer */}
      {selectedTask && (
        <div style={{
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 0,
          width: 380,
          maxWidth: '90%',
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border-color)',
          boxShadow: '-8px 0 32px rgba(0,0,0,0.18)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto'
        }}>
          {/* Drawer Header */}
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            background: 'var(--bg-subtle)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '2px 7px',
                  borderRadius: 4,
                  background: 'var(--primary-color, #2563eb)',
                  color: '#fff'
                }}>
                  {selectedTask.task_code}
                </span>
                <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{selectedTask.phase}</span>
              </div>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>
                {selectedTask.title}
              </h4>
            </div>
            <button
              onClick={() => setSelectedTask(null)}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                color: 'var(--text-muted)',
                padding: 4
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Drawer Body */}
          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Status Selector */}
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                Execution Status
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                {(['Pending', 'In Progress', 'Finished'] as RoadmapTask['status'][]).map(st => (
                  <button
                    key={st}
                    onClick={() => handleStatusChange(selectedTask, st)}
                    style={{
                      flex: 1,
                      padding: '7px 10px',
                      fontSize: 11.5,
                      fontWeight: 600,
                      borderRadius: 6,
                      border: selectedTask.status === st ? '2px solid var(--primary-color, #2563eb)' : '1px solid var(--border-color)',
                      background: selectedTask.status === st ? 'var(--bg-subtle)' : 'var(--bg-card)',
                      color: 'var(--text-main)',
                      cursor: 'pointer'
                    }}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            {/* Definition of Done */}
            <div style={{ background: 'var(--bg-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <CheckCircle2 size={14} color="#10b981" />
                <span style={{ fontSize: 11.5, fontWeight: 700 }}>Definition of Done</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-main)', lineHeight: 1.4 }}>
                {selectedTask.definition_of_done || selectedTask.deliverables || 'All acceptance criteria verified and deliverable released.'}
              </p>
            </div>

            {/* Concrete Action Steps / Checklist */}
            <div>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                Implementation Steps
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(selectedTask.steps || ['Analyze requirements and prerequisites', 'Implement core deliverable', 'Review quality and verify acceptance criteria']).map((step, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 12 }}>
                    <CheckSquare size={14} color="var(--primary-color, #2563eb)" style={{ marginTop: 2, flexShrink: 0 }} />
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Prerequisites */}
            <div>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
                Prerequisites & Dependencies
              </span>
              {selectedTask.dependencies && selectedTask.dependencies.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {selectedTask.dependencies.map(dep => (
                    <span
                      key={dep}
                      onClick={() => {
                        const target = tasks.find(t => t.task_code === dep || t.id === dep);
                        if (target) handleJumpToNode(target);
                      }}
                      style={{
                        padding: '4px 8px',
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 4,
                        background: 'var(--bg-subtle)',
                        border: '1px solid var(--border-color)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}
                    >
                      <ArrowRight size={11} /> {dep}
                    </span>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No upstream prerequisites. Can start immediately.</span>
              )}
            </div>

            {/* Delivery Metadata */}
            <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 11.5 }}>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Estimated Effort</span>
                <strong>{selectedTask.effort || '1-2 weeks'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Assigned Role</span>
                <strong>{selectedTask.assigned_role || 'Technical Lead'}</strong>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Start Date</span>
                <span>{selectedTask.start_date || 'Baseline'}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block' }}>Target Completion</span>
                <span>{selectedTask.end_date || 'Horizon'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
