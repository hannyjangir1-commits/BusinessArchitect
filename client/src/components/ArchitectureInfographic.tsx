import React, { useRef, useState, useEffect } from 'react';
import { TechStackData, TechRecommendation } from '../types';
import { Download, Layers, Server, Database, Cloud, ShieldCheck, X, CheckCircle2, AlertTriangle, ArrowRight, DollarSign } from 'lucide-react';

interface Props {
  techData: TechStackData;
  projectName: string;
  versionName?: string;
  onDownloadSvg?: () => void;
}

interface TierGroup {
  id: string;
  name: string;
  icon: any;
  color: string;
  bg: string;
  borderColor: string;
  items: TechRecommendation[];
}

export const ArchitectureInfographic: React.FC<Props> = ({
  techData,
  projectName,
  versionName = 'Active Blueprint',
  onDownloadSvg
}) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [selectedTech, setSelectedTech] = useState<TechRecommendation | null>(null);

  const recommendations = techData?.recommendations || [];

  // Close modal on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedTech(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Classify recommendations into standard & non-technical operational architectural tiers
  const tiers: TierGroup[] = [
    {
      id: 'business_ops',
      name: 'Business Operations, POS & Payments Tier',
      icon: Layers,
      color: '#059669',
      bg: '#ecfdf5',
      borderColor: '#a7f3d0',
      items: recommendations.filter(r =>
        /pos|payment|retail|commerce|store|operation|order|billing/i.test(r?.category || '')
      )
    },
    {
      id: 'client',
      name: 'Client & Presentation Tier',
      icon: Layers,
      color: '#6f865f',
      bg: '#f0f1e9',
      borderColor: '#dfe2d6',
      items: recommendations.filter(r =>
        /front|client|ui|mobile|web|presentation/i.test(r?.category || '') &&
        !/pos|payment|retail|commerce/i.test(r?.category || '')
      )
    },
    {
      id: 'application',
      name: 'Application & API Services Tier',
      icon: Server,
      color: '#6d855f',
      bg: '#f0f1e9',
      borderColor: '#d6dccf',
      items: recommendations.filter(r =>
        /back|api|server|service|microservice/i.test(r?.category || '') &&
        !/pos|payment|retail|commerce/i.test(r?.category || '')
      )
    },
    {
      id: 'data',
      name: 'Data & State Management Tier',
      icon: Database,
      color: '#0d9488',
      bg: '#f0fdfa',
      borderColor: '#99f6e4',
      items: recommendations.filter(r =>
        /data|storage|sql|cache|queue/i.test(r?.category || '')
      )
    },
    {
      id: 'cloud',
      name: 'Cloud, Infrastructure & DevOps Tier',
      icon: Cloud,
      color: '#d97706',
      bg: '#fffbeb',
      borderColor: '#fde68a',
      items: recommendations.filter(r =>
        /cloud|host|devops|infra|deploy|container/i.test(r?.category || '')
      )
    },
    {
      id: 'security',
      name: 'Security, Observability & Platform Services',
      icon: ShieldCheck,
      color: 'var(--text-main)',
      bg: '#f7f6ef',
      borderColor: 'var(--text-muted)',
      items: recommendations.filter(r =>
        /sec|auth|monitor|telemetry|audit|service/i.test(r?.category || '') &&
        !/front|client|back|api|data|cloud|devops|pos|payment|commerce/i.test(r?.category || '')
      )
    }
  ];

  // Distribute uncategorized items into the application tier
  const matchedTechs = new Set(tiers.flatMap(t => t.items.map(i => i?.technology || '')));
  const unassigned = recommendations.filter(r => r && !matchedTechs.has(r.technology || ''));
  if (unassigned.length > 0) {
    tiers[2].items.push(...unassigned);
  }

  // Filter to active tiers with items
  const activeTiers = tiers.filter(t => t.items.length > 0);

  const handleDownloadDirectSvg = () => {
    if (onDownloadSvg) {
      onDownloadSvg();
      return;
    }
    if (!svgRef.current) return;
    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svgRef.current);
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${projectName.toLowerCase().replace(/[^a-z0-9]/g, '_')}_architecture_diagram.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const svgWidth = 1000;
  const headerHeight = 70;
  const tierSpacing = 30;
  const nodeHeight = 84;
  const tierHeaderH = 34;

  let currentY = headerHeight;
  const tierLayouts = activeTiers.map(tier => {
    const tierY = currentY;
    const itemsCount = tier.items.length;
    const colWidth = Math.min(300, (svgWidth - 60) / Math.max(itemsCount, 1));
    const totalRowWidth = itemsCount * colWidth;
    const startX = (svgWidth - totalRowWidth) / 2;
    const tierTotalH = tierHeaderH + nodeHeight + 20;

    currentY += tierTotalH + tierSpacing;

    return {
      tier,
      tierY,
      tierTotalH,
      colWidth,
      startX,
      items: tier.items.map((item, idx) => ({
        item,
        x: startX + idx * colWidth + 8,
        y: tierY + tierHeaderH + 6,
        w: colWidth - 16,
        h: nodeHeight
      }))
    };
  });

  const totalSvgHeight = Math.max(600, currentY + 20);

  return (
    <div className="card" style={{ padding: 20, marginBottom: 20, position: 'relative' }}>
      {/* Visual Diagram Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
            System Architecture Blueprint Infographic
          </h3>
          <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '3px 0 0 0' }}>
            Interactive multi-tier service topology. Click any node to explore role, rationale, risks, and implementation guidance.
          </p>
        </div>

        <button
          onClick={handleDownloadDirectSvg}
          className="btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px', gap: 6, display: 'flex', alignItems: 'center' }}
          title="Download vector SVG architecture diagram"
        >
          <Download size={14} color="#6d855f" />
          <span>Download SVG Diagram</span>
        </button>
      </div>

      {/* SVG Canvas Container */}
      <div
        style={{
          width: '100%',
          overflowX: 'auto',
          background: '#ffffff',
          borderRadius: 8,
          border: '1px solid #dfe2d6',
          boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.02)'
        }}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${svgWidth} ${totalSvgHeight}`}
          style={{ width: '100%', minWidth: 700, height: 'auto', display: 'block' }}
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label={`Architecture Topology for ${projectName}`}
        >
          <defs>
            <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f7f6ef" />
              <stop offset="100%" stopColor="var(--text-main)" />
            </linearGradient>
            <filter id="cardShadow" x="-5%" y="-5%" width="110%" height="115%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="var(--text-main)" floodOpacity="0.06" />
            </filter>
            <filter id="activeNodeGlow" x="-10%" y="-10%" width="120%" height="125%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#6d855f" floodOpacity="0.25" />
            </filter>
            <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#7c8478" />
            </marker>
          </defs>

          {/* Canvas Background */}
          <rect width={svgWidth} height={totalSvgHeight} fill="url(#bgGrad)" />

          {/* Header Banner */}
          <g transform="translate(30, 20)">
            <rect width={svgWidth - 60} height="46" rx="8" fill="#e8ede2" />
            <text x="20" y="28" fill="#626b5f" fontSize="15" fontWeight="700" fontFamily="system-ui, -apple-system, sans-serif">
              {projectName} — {versionName} Architecture Topography ({techData.architecture_pattern || 'Standard Cloud'})
            </text>
          </g>

          {/* Inter-tier Connection Arrows */}
          {tierLayouts.slice(0, -1).map((current, idx) => {
            const next = tierLayouts[idx + 1];
            const startY = current.tierY + current.tierTotalH;
            const endY = next.tierY;
            return (
              <g key={`arrow-${idx}`}>
                <line
                  x1={svgWidth / 2}
                  y1={startY}
                  x2={svgWidth / 2}
                  y2={endY}
                  stroke="#7c8478"
                  strokeWidth="2"
                  strokeDasharray="4 4"
                  markerEnd="url(#arrow)"
                />
              </g>
            );
          })}

          {/* Render Tiers and Nodes */}
          {tierLayouts.map(({ tier, tierY, tierTotalH, items }) => (
            <g key={tier.id} transform={`translate(0, ${tierY})`}>
              {/* Tier Background Container */}
              <rect
                x="30"
                y="0"
                width={svgWidth - 60}
                height={tierTotalH}
                rx="8"
                fill={tier.bg}
                stroke={tier.borderColor}
                strokeWidth="1.5"
              />

              {/* Tier Title Banner */}
              <text
                x="44"
                y="22"
                fill={tier.color}
                fontSize="12.5"
                fontWeight="700"
                fontFamily="system-ui, -apple-system, sans-serif"
                letterSpacing="0.3"
              >
                {tier.name.toUpperCase()}
              </text>

              {/* Technology Node Cards */}
              {items.map(({ item, x, y, w, h }, itemIdx) => {
                const isSelected = selectedTech?.technology === item.technology;
                return (
                  <g
                    key={item.technology || item.name || itemIdx}
                    transform={`translate(${x}, ${y - tierY})`}
                    filter={isSelected ? 'url(#activeNodeGlow)' : 'url(#cardShadow)'}
                    style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Explore ${item.technology || item.name}`}
                    onClick={() => setSelectedTech(item)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedTech(item);
                      }
                    }}
                  >
                    <rect
                      width={w}
                      height={h}
                      rx="6"
                      fill="#ffffff"
                      stroke={isSelected ? tier.color : '#dfe2d6'}
                      strokeWidth={isSelected ? '2' : '1'}
                    />
                    {/* Left accent strip */}
                    <rect
                      width="4"
                      height={h}
                      rx="2"
                      fill={tier.color}
                    />

                    {/* Technology Name */}
                    <text
                      x="12"
                      y="22"
                      fill="#626b5f"
                      fontSize="13"
                      fontWeight="700"
                      fontFamily="system-ui, -apple-system, sans-serif"
                    >
                      {(item.technology || item.name || 'Component').length > 24
                        ? `${(item.technology || item.name || 'Component').slice(0, 22)}...`
                        : (item.technology || item.name || 'Component')}
                    </text>

                    {/* Category Pill Tag */}
                    <text
                      x="12"
                      y="39"
                      fill="#687164"
                      fontSize="10.5"
                      fontWeight="600"
                      fontFamily="system-ui, -apple-system, sans-serif"
                    >
                      {item.category || 'General'}
                    </text>

                    {/* Purpose Snippet */}
                    <text
                      x="12"
                      y="56"
                      fill="#626b5f"
                      fontSize="10"
                      fontFamily="system-ui, -apple-system, sans-serif"
                    >
                      {(item.purpose || '').length > 36
                        ? `${(item.purpose || '').slice(0, 34)}...`
                        : (item.purpose || '')}
                    </text>

                    {/* Interactive Click Tip */}
                    <text
                      x="12"
                      y="74"
                      fill={tier.color}
                      fontSize="8.5"
                      fontWeight="700"
                      fontFamily="system-ui, -apple-system, sans-serif"
                    >
                      Inspect Details ➔
                    </text>
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      </div>

      {/* Explorable Technology Node Detail Drawer (TECH-011) */}
      {selectedTech && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            right: 0,
            bottom: 0,
            width: 'min(460px, 95%)',
            background: '#ffffff',
            boxShadow: '-8px 0 24px rgba(15, 23, 42, 0.15)',
            borderTopRightRadius: 8,
            borderBottomRightRadius: 8,
            borderLeft: '1px solid #dfe2d6',
            zIndex: 40,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto'
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="tech-drawer-title"
        >
          {/* Header */}
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #f0f1e9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: '#f7f6ef' }}>
            <div>
              <span className="badge" style={{ fontSize: 11, background: '#e8ede2', color: '#6d855f', marginBottom: 4, display: 'inline-block' }}>
                {selectedTech.category}
              </span>
              <h4 id="tech-drawer-title" style={{ margin: '4px 0 0 0', fontSize: 17, fontWeight: 700, color: 'var(--text-main)' }}>
                {selectedTech.technology || selectedTech.name}
              </h4>
            </div>
            <button
              onClick={() => setSelectedTech(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, borderRadius: 4 }}
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>

          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Purpose & Role Description */}
            <div>
              <h5 style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 6px 0' }}>
                Architectural Role & Purpose
              </h5>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: 'var(--text-main)' }}>
                {selectedTech.role_description || selectedTech.purpose}
              </p>
            </div>

            {/* Suitability & Rationale */}
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 12 }}>
              <h5 style={{ fontSize: 12.5, fontWeight: 700, color: '#166534', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={15} color="#16a34a" /> Selection Rationale & Suitability
              </h5>
              <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: '#14532d' }}>
                {selectedTech.suitability}
              </p>
            </div>

            {/* Implementation Guidance */}
            {selectedTech.implementation_guidance && (
              <div style={{ background: '#f0f1e9', border: '1px solid #d6dccf', borderRadius: 8, padding: 12 }}>
                <h5 style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ArrowRight size={15} color="#6d855f" /> Implementation Guidance
                </h5>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-muted)' }}>
                  {selectedTech.implementation_guidance}
                </p>
              </div>
            )}

            {/* Cost Tier */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: '#f7f6ef', border: '1px solid #dfe2d6', borderRadius: 8 }}>
              <DollarSign size={16} color="#059669" />
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>Estimated Cost Tier</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>
                  {selectedTech.estimated_cost_tier || 'Low / Free Tier'}
                </span>
              </div>
            </div>

            {/* Trade-offs & Risks */}
            {selectedTech.trade_offs && (
              <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: 12 }}>
                <h5 style={{ fontSize: 12.5, fontWeight: 700, color: '#92400e', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={15} color="#d97706" /> Known Trade-offs & Limitations
                </h5>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: '#78350f' }}>
                  {selectedTech.trade_offs}
                </p>
              </div>
            )}

            {/* Migration Risk */}
            {selectedTech.migration_risk && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                <span style={{ fontWeight: 600 }}>Migration Note: </span>
                {selectedTech.migration_risk}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
