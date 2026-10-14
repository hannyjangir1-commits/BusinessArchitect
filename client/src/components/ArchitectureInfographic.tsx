import React, { useRef } from 'react';
import { TechStackData, TechRecommendation } from '../types';
import { Download, Layers, Server, Database, Cloud, ShieldCheck } from 'lucide-react';

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

  const recommendations = techData?.recommendations || [];

  // Classify recommendations into standard architectural tiers
  const tiers: TierGroup[] = [
    {
      id: 'client',
      name: 'Client & Presentation Tier',
      icon: Layers,
      color: '#0284c7',
      bg: '#f0f9ff',
      borderColor: '#bae6fd',
      items: recommendations.filter(r =>
        /front|client|ui|mobile|web|presentation/i.test(r?.category || '')
      )
    },
    {
      id: 'application',
      name: 'Application & API Services Tier',
      icon: Server,
      color: '#6366f1',
      bg: '#eef2ff',
      borderColor: '#c7d2fe',
      items: recommendations.filter(r =>
        /back|api|server|service|microservice/i.test(r?.category || '')
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
      color: '#475569',
      bg: '#f8fafc',
      borderColor: '#cbd5e1',
      items: recommendations.filter(r =>
        /sec|auth|monitor|telemetry|audit|service/i.test(r?.category || '') &&
        !/front|client|back|api|data|cloud|devops/i.test(r?.category || '')
      )
    }
  ];

  // Distribute uncategorized items into the closest matching tier
  const matchedTechs = new Set(tiers.flatMap(t => t.items.map(i => i?.technology || '')));
  const unassigned = recommendations.filter(r => r && !matchedTechs.has(r.technology || ''));
  if (unassigned.length > 0) {
    tiers[1].items.push(...unassigned);
  }

  // Filter to active tiers with items
  const activeTiers = tiers.filter(t => t.items.length > 0);

  // Handle direct SVG download
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

  // Dimensions for dynamic SVG generation
  const svgWidth = 1000;
  const headerHeight = 70;
  const tierSpacing = 30;
  const nodeHeight = 76;
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
    <div className="card" style={{ padding: 20, marginBottom: 20 }}>
      {/* Visual Diagram Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', margin: 0 }}>
            System Architecture Blueprint Infographic
          </h3>
          <p style={{ fontSize: 12.5, color: '#64748b', margin: '3px 0 0 0' }}>
            Multi-tier service topology, component suitability, and operational flow
          </p>
        </div>

        <button
          onClick={handleDownloadDirectSvg}
          className="btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px', gap: 6 }}
          title="Download vector SVG architecture diagram"
        >
          <Download size={14} color="#6366f1" />
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
          border: '1px solid #e2e8f0',
          boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.02)'
        }}
      >
        <svg
          ref={svgRef}
          viewBox={`0 0 ${svgWidth} ${totalSvgHeight}`}
          style={{ width: '100%', minWidth: 700, height: 'auto', display: 'block' }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f8fafc" />
              <stop offset="100%" stopColor="#ffffff" />
            </linearGradient>
            <filter id="cardShadow" x="-5%" y="-5%" width="110%" height="115%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0f172a" floodOpacity="0.06" />
            </filter>
            <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#94a3b8" />
            </marker>
          </defs>

          {/* Canvas Background */}
          <rect width={svgWidth} height={totalSvgHeight} fill="url(#bgGrad)" />

          {/* Header Banner */}
          <g transform="translate(30, 20)">
            <rect width={svgWidth - 60} height="46" rx="8" fill="#1e293b" />
            <text x="20" y="28" fill="#ffffff" fontSize="15" fontWeight="700" fontFamily="system-ui, -apple-system, sans-serif">
              {projectName} — Architecture Topography
            </text>
            <text x={svgWidth - 85} y="28" textAnchor="end" fill="#94a3b8" fontSize="12" fontWeight="600" fontFamily="system-ui, -apple-system, sans-serif">
              Pattern: {techData.architecture_pattern || 'Modular Monolith'} | {versionName}
            </text>
          </g>

          {/* Render Flow Arrows Between Adjacent Tiers */}
          {tierLayouts.slice(0, -1).map((tLayout, idx) => {
            const nextLayout = tierLayouts[idx + 1];
            const arrowStartY = tLayout.tierY + tLayout.tierTotalH;
            const arrowEndY = nextLayout.tierY;
            const midX = svgWidth / 2;

            return (
              <g key={`arrow-${idx}`}>
                <line
                  x1={midX}
                  y1={arrowStartY}
                  x2={midX}
                  y2={arrowEndY}
                  stroke="#94a3b8"
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
              {items.map(({ item, x, y, w, h }, itemIdx) => (
                <g key={item.technology || item.name || itemIdx} transform={`translate(${x}, ${y - tierY})`} filter="url(#cardShadow)">
                  <rect
                    width={w}
                    height={h}
                    rx="6"
                    fill="#ffffff"
                    stroke="#e2e8f0"
                    strokeWidth="1"
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
                    fill="#0f172a"
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
                    fill="#64748b"
                    fontSize="10.5"
                    fontWeight="600"
                    fontFamily="system-ui, -apple-system, sans-serif"
                  >
                    {item.category || 'General'}
                  </text>

                  {/* Purpose Snippet */}
                  <text
                    x="12"
                    y="57"
                    fill="#334155"
                    fontSize="10.5"
                    fontFamily="system-ui, -apple-system, sans-serif"
                  >
                    {(item.purpose || '').length > 38
                      ? `${(item.purpose || '').slice(0, 36)}...`
                      : (item.purpose || '')}
                  </text>
                </g>
              ))}
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
};
