import React, { useRef, useState, useEffect } from 'react';
import { BMCData } from '../types';
import { Download, Sparkles, X, ChevronRight, CheckCircle2, AlertCircle, HelpCircle } from 'lucide-react';

interface Props {
  projectName: string;
  stage: string;
  data: BMCData;
}

export const RadialBMCInfographic: React.FC<Props> = ({ projectName, stage, data }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const blocksConfig = [
    { key: 'value_propositions', title: 'Value Propositions', color: '#6366f1', angle: -90, icon: '💎', description: 'Core bundles of value and solutions addressing target customer pain points.' },
    { key: 'customer_relationships', title: 'Customer Relationships', color: '#ec4899', angle: -50, icon: '🤝', description: 'Types of relationships established with each customer segment.' },
    { key: 'channels', title: 'Channels', color: '#f43f5e', angle: -10, icon: '📢', description: 'Touchpoints through which you communicate and deliver value propositions.' },
    { key: 'customer_segments', title: 'Customer Segments', color: '#fb7185', angle: 30, icon: '👥', description: 'Distinct groups of people or organizations the venture aims to serve.' },
    { key: 'revenue_streams', title: 'Revenue Streams', color: '#10b981', angle: 70, icon: '💰', description: 'Cash generated from each customer segment through pricing mechanisms.' },
    { key: 'cost_structure', title: 'Cost Structure', color: '#f59e0b', angle: 110, icon: '⚖️', description: 'All monetary expenses incurred to operate the business model.' },
    { key: 'key_partnerships', title: 'Key Partnerships', color: '#06b6d4', angle: 150, icon: '🔗', description: 'Network of suppliers, distributors, and strategic alliances.' },
    { key: 'key_activities', title: 'Key Activities', color: '#3b82f6', angle: 190, icon: '⚡', description: 'Most crucial actions a company must perform to execute successfully.' },
    { key: 'key_resources', title: 'Key Resources', color: '#8b5cf6', angle: 230, icon: '🏛️', description: 'Most important physical, intellectual, human, or financial assets.' },
  ];

  const width = 1100;
  const height = 750;
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = 390;
  const radiusY = 270;

  // Keyboard navigation for detail drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedKey(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

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

  const activeBlockConfig = blocksConfig.find(b => b.key === selectedKey);
  const activeItems: string[] = selectedKey ? ((data as any)[selectedKey] || []) : [];
  const activeGuidance = selectedKey && data.actionable_guidance ? data.actionable_guidance[selectedKey] : null;

  return (
    <div className="radial-bmc-container" style={{ position: 'relative', width: '100%', background: '#ffffff', borderRadius: 12, border: '1px solid #e2e8f0', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
            <Sparkles size={18} color="#6366f1" /> Radial Business Model Canvas Mind Map
          </h3>
          <p style={{ fontSize: 12, color: '#64748b', margin: '4px 0 0 0' }}>
            Interactive Alexander Osterwalder 9-block architecture. Click or activate any card to view complete details & actionable guidance.
          </p>
        </div>
        <button
          onClick={downloadSVG}
          className="btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
          title="Download vector SVG"
        >
          <Download size={14} /> Download SVG
        </button>
      </div>

      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', minWidth: 900, height: 'auto', maxHeight: 720, display: 'block' }}
          role="img"
          aria-label={`Radial Business Model Canvas for ${projectName}`}
        >
          <defs>
            <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="centerNodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#7c3aed" />
            </linearGradient>
            <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.08" floodColor="#0f172a" />
            </filter>
            <filter id="hoverGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="6" stdDeviation="10" floodOpacity="0.2" floodColor="#6366f1" />
            </filter>
          </defs>

          {/* Background Ambient Glow */}
          <circle cx={centerX} cy={centerY} r={radiusX * 0.9} fill="url(#centerGlow)" />

          {/* Dynamic Connectors from Center to 9 Blocks */}
          {blocksConfig.map((b, i) => {
            const rad = (b.angle * Math.PI) / 180;
            const cardX = centerX + radiusX * Math.cos(rad);
            const cardY = centerY + radiusY * Math.sin(rad);
            const isHighlighted = selectedKey === b.key;

            return (
              <g key={`conn-${i}`}>
                <line
                  x1={centerX}
                  y1={centerY}
                  x2={cardX}
                  y2={cardY}
                  stroke={b.color}
                  strokeWidth={isHighlighted ? '3' : '2'}
                  strokeDasharray={isHighlighted ? 'none' : '4 4'}
                  opacity={isHighlighted ? 0.9 : 0.45}
                />
                <circle cx={(centerX + cardX) / 2} cy={(centerY + cardY) / 2} r={isHighlighted ? 4 : 3} fill={b.color} opacity="0.9" />
              </g>
            );
          })}

          {/* Center Company Node */}
          <g
            transform={`translate(${centerX}, ${centerY})`}
            style={{ cursor: 'pointer' }}
            tabIndex={0}
            role="button"
            aria-label={`Center venture node: ${projectName}`}
            onClick={() => setSelectedKey(null)}
          >
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
              9-Block Canvas Core
            </text>
          </g>

          {/* Surrounding 9 Interactive Block Cards */}
          {blocksConfig.map((b, i) => {
            const rad = (b.angle * Math.PI) / 180;
            const cardW = 195;
            const cardH = 125;
            const cardX = centerX + radiusX * Math.cos(rad) - cardW / 2;
            const cardY = centerY + radiusY * Math.sin(rad) - cardH / 2;
            const items: string[] = (data as any)[b.key] || [];
            const isSelected = selectedKey === b.key;

            return (
              <g
                key={`card-${i}`}
                transform={`translate(${cardX}, ${cardY})`}
                style={{ cursor: 'pointer', transition: 'transform 0.2s ease' }}
                tabIndex={0}
                role="button"
                aria-label={`Inspect ${b.title}: ${items.length} items`}
                onClick={() => setSelectedKey(b.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setSelectedKey(b.key);
                  }
                }}
              >
                {/* Card Container */}
                <rect
                  width={cardW}
                  height={cardH}
                  rx="10"
                  fill="#ffffff"
                  stroke={isSelected ? b.color : '#e2e8f0'}
                  strokeWidth={isSelected ? '2.5' : '1.5'}
                  filter={isSelected ? 'url(#hoverGlow)' : 'url(#cardShadow)'}
                />
                {/* Top Category Accent Line */}
                <path d={`M 0 10 Q 0 0 10 0 L ${cardW - 10} 0 Q ${cardW} 0 ${cardW} 10 L ${cardW} 28 L 0 28 Z`} fill={b.color} opacity={isSelected ? 0.25 : 0.12} />
                <rect x="0" y="0" width={cardW} height="3" fill={b.color} rx="1" />

                {/* Header with Icon and Title */}
                <text x="10" y="19" fontSize="11" fontWeight="800" fill={b.color} fontFamily="sans-serif">
                  {b.icon} {b.title}
                </text>

                {/* Item Pills / Readable Summary without clipping */}
                {items.slice(0, 3).map((it, idx) => {
                  const label = it.length > 25 ? it.slice(0, 23) + '…' : it;
                  return (
                    <g key={`line-${idx}`} transform={`translate(10, ${44 + idx * 22})`}>
                      <circle cx="3" cy="-3" r="2.5" fill={b.color} />
                      <text x="10" y="0" fontSize="9.5" fill="#334155" fontWeight="500" fontFamily="sans-serif">
                        {label}
                      </text>
                    </g>
                  );
                })}

                {/* Counter Footer */}
                <g transform={`translate(10, ${cardH - 10})`}>
                  <rect x="0" y="-10" width={cardW - 20} height="15" rx="4" fill={isSelected ? b.color : '#f1f5f9'} opacity={isSelected ? 0.15 : 0.7} />
                  <text x="6" y="1" fontSize="8" fill={b.color} fontWeight="700" fontFamily="sans-serif">
                    {items.length} items • Click for guidance ➔
                  </text>
                </g>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Slide-over Inspection Panel for Full Detail & Actionable Guidance */}
      {selectedKey && activeBlockConfig && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            bottom: 0,
            width: 'min(480px, 95%)',
            background: '#ffffff',
            boxShadow: '-8px 0 24px rgba(15, 23, 42, 0.15)',
            borderTopRightRadius: 12,
            borderBottomRightRadius: 12,
            borderLeft: '1px solid #e2e8f0',
            zIndex: 30,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            animation: 'fadeIn 0.2s ease-out'
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="detail-panel-title"
        >
          {/* Drawer Header */}
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: '#f8fafc' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 22 }}>{activeBlockConfig.icon}</span>
                <h4 id="detail-panel-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: activeBlockConfig.color }}>
                  {activeBlockConfig.title}
                </h4>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: 12, color: '#64748b' }}>
                {activeBlockConfig.description}
              </p>
            </div>
            <button
              onClick={() => setSelectedKey(null)}
              style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4, borderRadius: 4 }}
              aria-label="Close details"
            >
              <X size={18} />
            </button>
          </div>

          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Complete Items List - No Clipping */}
            <div>
              <h5 style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={15} color={activeBlockConfig.color} />
                Complete Section Content ({activeItems.length} Points)
              </h5>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activeItems.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: '#1e293b',
                      wordBreak: 'break-word'
                    }}
                  >
                    <span style={{ fontWeight: 700, color: activeBlockConfig.color, marginRight: 6 }}>#{idx + 1}</span>
                    {item}
                  </div>
                ))}
              </div>
            </div>

            {/* Actionable Guidance (BMC-004, BMC-012) */}
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 14 }}>
              <h5 style={{ fontSize: 13, fontWeight: 700, color: '#166534', margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={15} color="#16a34a" /> Actionable Guidance: What to Test, Decide & Validate
              </h5>
              <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.6, color: '#14532d' }}>
                {activeGuidance || "Execute structured interviews with 15 target users in this category to validate willingness-to-pay and measure conversion friction."}
              </p>
            </div>

            {/* Assumptions (BMC-011) */}
            {data.assumptions && data.assumptions.length > 0 && (
              <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: 14 }}>
                <h5 style={{ fontSize: 13, fontWeight: 700, color: '#92400e', margin: '0 0 6px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertCircle size={15} color="#d97706" /> Identified Venture Assumptions
                </h5>
                <ul style={{ margin: '6px 0 0 0', paddingLeft: 18, fontSize: 12, color: '#78350f', lineHeight: 1.5 }}>
                  {data.assumptions.map((assump, aIdx) => (
                    <li key={aIdx} style={{ marginBottom: 4 }}>{assump}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
