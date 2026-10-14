import React, { useRef } from 'react';
import { BMCData } from '../types';
import { Download, Sparkles } from 'lucide-react';

interface Props {
  projectName: string;
  stage: string;
  data: BMCData;
}

export const RadialBMCInfographic: React.FC<Props> = ({ projectName, stage, data }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  // Define 9 blocks with specific radial angles and curated harmonious colors
  const blocksConfig = [
    { key: 'value_propositions', title: 'Value Propositions', color: '#6366f1', angle: -90, icon: '💎' },
    { key: 'customer_relationships', title: 'Customer Relationships', color: '#ec4899', angle: -50, icon: '🤝' },
    { key: 'channels', title: 'Channels', color: '#f43f5e', angle: -10, icon: '📢' },
    { key: 'customer_segments', title: 'Customer Segments', color: '#fb7185', angle: 30, icon: '👥' },
    { key: 'revenue_streams', title: 'Revenue Streams', color: '#10b981', angle: 70, icon: '💰' },
    { key: 'cost_structure', title: 'Cost Structure', color: '#f59e0b', angle: 110, icon: '⚖️' },
    { key: 'key_partnerships', title: 'Key Partnerships', color: '#06b6d4', angle: 150, icon: '🔗' },
    { key: 'key_activities', title: 'Key Activities', color: '#3b82f6', angle: 190, icon: '⚡' },
    { key: 'key_resources', title: 'Key Resources', color: '#8b5cf6', angle: 230, icon: '🏛️' },
  ];

  const width = 1100;
  const height = 750;
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = 390;
  const radiusY = 270;

  const downloadSVG = () => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName.toLowerCase().replace(/\s+/g, '_')}_radial_bmc.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="radial-bmc-container" style={{ position: 'relative', width: '100%', background: '#ffffff', borderRadius: 12, border: '1px solid #e2e8f0', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sparkles size={18} color="#6366f1" /> Radial Business Model Canvas Infographic
          </h3>
          <p style={{ fontSize: 12, color: '#64748b' }}>Deterministic vector visualization connecting Alexander Osterwalder's 9 core blocks</p>
        </div>
        <button
          onClick={downloadSVG}
          className="btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px' }}
        >
          <Download size={14} /> Download SVG
        </button>
      </div>

      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', minWidth: 900, height: 'auto', maxHeight: 720, display: 'block' }}
        >
          <defs>
            {/* Gradients */}
            <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="centerNodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#7c3aed" />
            </linearGradient>
            <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.08" floodColor="#0f172a" />
            </filter>
          </defs>

          {/* Background Ambient Glow */}
          <circle cx={centerX} cy={centerY} r={radiusX * 0.9} fill="url(#centerGlow)" />

          {/* Dynamic Connectors from Center to 9 Blocks */}
          {blocksConfig.map((b, i) => {
            const rad = (b.angle * Math.PI) / 180;
            const cardX = centerX + radiusX * Math.cos(rad);
            const cardY = centerY + radiusY * Math.sin(rad);

            return (
              <g key={`conn-${i}`}>
                <line
                  x1={centerX}
                  y1={centerY}
                  x2={cardX}
                  y2={cardY}
                  stroke={b.color}
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  opacity="0.45"
                />
                <circle cx={(centerX + cardX) / 2} cy={(centerY + cardY) / 2} r="3" fill={b.color} opacity="0.8" />
              </g>
            );
          })}

          {/* Center Company Node */}
          <g transform={`translate(${centerX}, ${centerY})`}>
            <circle r="72" fill="url(#centerNodeGrad)" filter="url(#cardShadow)" />
            <circle r="78" fill="none" stroke="#6366f1" strokeWidth="2" strokeDasharray="6 4" opacity="0.6" />
            <text textAnchor="middle" y="-12" fill="#ffffff" fontWeight="800" fontSize="14" fontFamily="sans-serif">
              {projectName.length > 18 ? projectName.slice(0, 16) + '...' : projectName}
            </text>
            <rect x="-45" y="4" width="90" height="18" rx="9" fill="rgba(255,255,255,0.2)" />
            <text textAnchor="middle" y="17" fill="#ffffff" fontWeight="700" fontSize="10" fontFamily="sans-serif">
              {stage}
            </text>
            <text textAnchor="middle" y="38" fill="rgba(255,255,255,0.85)" fontWeight="500" fontSize="8.5" fontFamily="sans-serif">
              Enterprise Core
            </text>
          </g>

          {/* Surrounding 9 Block Cards */}
          {blocksConfig.map((b, i) => {
            const rad = (b.angle * Math.PI) / 180;
            const cardW = 180;
            const cardH = 115;
            const cardX = centerX + radiusX * Math.cos(rad) - cardW / 2;
            const cardY = centerY + radiusY * Math.sin(rad) - cardH / 2;

            const items: string[] = (data as any)[b.key] || [];

            return (
              <g key={`card-${i}`} transform={`translate(${cardX}, ${cardY})`}>
                {/* Card Container */}
                <rect
                  width={cardW}
                  height={cardH}
                  rx="10"
                  fill="#ffffff"
                  stroke="#e2e8f0"
                  strokeWidth="1.5"
                  filter="url(#cardShadow)"
                />
                {/* Top Category Accent Line */}
                <path d={`M 0 10 Q 0 0 10 0 L ${cardW - 10} 0 Q ${cardW} 0 ${cardW} 10 L ${cardW} 28 L 0 28 Z`} fill={b.color} opacity="0.12" />
                <rect x="0" y="0" width={cardW} height="3" fill={b.color} rx="1" />

                {/* Header with Icon and Title */}
                <text x="10" y="19" fontSize="11" fontWeight="800" fill={b.color} fontFamily="sans-serif">
                  {b.icon} {b.title}
                </text>

                {/* Bullet Points */}
                {items.slice(0, 3).map((it, idx) => {
                  const truncated = it.length > 28 ? it.slice(0, 26) + '...' : it;
                  return (
                    <g key={`line-${idx}`} transform={`translate(10, ${44 + idx * 22})`}>
                      <circle cx="3" cy="-3" r="2.5" fill={b.color} />
                      <text x="10" y="0" fontSize="9.5" fill="#334155" fontWeight="500" fontFamily="sans-serif">
                        {truncated}
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
};
