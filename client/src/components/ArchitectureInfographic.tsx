import React, { useRef, useState, useEffect } from 'react';
import { downloadSvg } from '../utils/svgExport';
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

  // Detect whether this is an operational / COTS / existing tools workflow (Checkpoint 5.5)
  const isOperationalOrManual = /existing tools|no custom software|manual|cots|operational/i.test(techData?.architecture_pattern || '') ||
    (recommendations.length > 0 && recommendations.every(r =>
      /whatsapp|sheets|excel|pos|square|stripe|quickbooks|calendar|notion|airtable|paper|sms|phone|manual/i.test(r?.technology || '') ||
      !/fastapi|express|django|react|vue|angular|docker|kubernetes|postgres|mysql|redis|aws|azure|gcp|microservice/i.test(r?.technology || '')
    ));

  // Classify recommendations into standard & non-technical operational architectural tiers
  const tiers: TierGroup[] = isOperationalOrManual
    ? [
        {
          id: 'contact',
          name: '1. Customer Inquiries & Communication Channels',
          icon: Layers,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /contact|message|chat|whatsapp|email|phone|inquiry|customer|sms/i.test(r?.category || '') ||
            /whatsapp|email|sms|phone/i.test(r?.technology || '')
          )
        },
        {
          id: 'records',
          name: '2. Operational Records & Booking Workflow',
          icon: Database,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            (/sheet|excel|calendar|notion|airtable|record|task|track|management/i.test(r?.category || '') ||
             /sheet|excel|calendar|notion|airtable/i.test(r?.technology || '')) &&
            !/whatsapp|email|phone/i.test(r?.technology || '')
          )
        },
        {
          id: 'operations',
          name: '3. Service Delivery & Physical Operations',
          icon: Server,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            (/pos|repair|service|inventory|dispatch|operation|store/i.test(r?.category || '') ||
             /pos|square|inventory|hardware/i.test(r?.technology || '')) &&
            !/payment|invoice|bill|stripe|quickbooks|accounting/i.test(r?.category || '')
          )
        },
        {
          id: 'financial',
          name: '4. Invoicing, Payments & Accounting',
          icon: DollarSign,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /payment|invoice|bill|stripe|square|quickbooks|accounting|bank/i.test(r?.category || '') ||
            /stripe|square|quickbooks|accounting/i.test(r?.technology || '')
          )
        },
        {
          id: 'supporting_ops',
          name: '5. Supporting Operations & Tools',
          icon: Cloud,
          color: 'var(--text-main)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            !/contact|message|chat|whatsapp|email|phone|inquiry|customer|sms|sheet|excel|calendar|notion|airtable|record|pos|repair|service|inventory|dispatch|operation|payment|invoice|bill|stripe|square|quickbooks|accounting/i.test(
              `${r?.category || ''} ${r?.technology || ''}`
            )
          )
        }
      ]
    : [
        {
          id: 'business_ops',
          name: 'Business Operations, POS & Payments Tier',
          icon: Layers,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /pos|payment|retail|commerce|store|operation|order|billing/i.test(r?.category || '')
          )
        },
        {
          id: 'client',
          name: 'Client & Presentation Tier',
          icon: Layers,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /front|client|ui|mobile|web|presentation/i.test(r?.category || '') &&
            !/pos|payment|retail|commerce/i.test(r?.category || '')
          )
        },
        {
          id: 'application',
          name: 'Application & API Services Tier',
          icon: Server,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /back|api|server|service|microservice/i.test(r?.category || '') &&
            !/pos|payment|retail|commerce/i.test(r?.category || '')
          )
        },
        {
          id: 'data',
          name: 'Data & State Management Tier',
          icon: Database,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /data|storage|sql|cache|queue/i.test(r?.category || '')
          )
        },
        {
          id: 'cloud',
          name: 'Cloud, Infrastructure & DevOps Tier',
          icon: Cloud,
          color: 'var(--primary-text)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--border-color)',
          items: recommendations.filter(r =>
            /cloud|host|devops|infra|deploy|container/i.test(r?.category || '')
          )
        },
        {
          id: 'security',
          name: 'Security, Observability & Platform Services',
          icon: ShieldCheck,
          color: 'var(--text-main)',
          bg: 'var(--bg-subtle)',
          borderColor: 'var(--text-muted)',
          items: recommendations.filter(r =>
            /sec|auth|monitor|telemetry|audit|service/i.test(r?.category || '') &&
            !/front|client|back|api|data|cloud|devops|pos|payment|commerce/i.test(r?.category || '')
          )
        }
      ];

  // Distribute uncategorized items into the middle tier
  const matchedTechs = new Set(tiers.flatMap(t => t.items.map(i => i?.technology || '')));
  const unassigned = recommendations.filter(r => r && !matchedTechs.has(r.technology || ''));
  if (unassigned.length > 0) {
    const fallbackTier = isOperationalOrManual ? tiers[1] : tiers[2];
    fallbackTier.items.push(...unassigned);
  }

  // Filter to active tiers with items
  const activeTiers = tiers.filter(t => t.items.length > 0);

  const handleDownloadDirectSvg = () => {
    if (onDownloadSvg) {
      onDownloadSvg();
      return;
    }
    if (!svgRef.current) return;
    downloadSvg(svgRef.current, `${projectName.replace(/[^a-z0-9_-]/gi, '_')}_architecture_diagram.svg`);
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
            {isOperationalOrManual ? 'Operational Toolchain & Workflow Diagram' : 'System Architecture Blueprint Infographic'}
          </h3>
          <p style={{ fontSize: 12.5, color: 'var(--text-muted)', margin: '3px 0 0 0' }}>
            {isOperationalOrManual
              ? 'Practical operational workflow sequence. Click any tool to inspect purpose, trade-offs, and implementation.'
              : 'Interactive multi-tier service topology. Click any node to explore role, rationale, risks, and implementation guidance.'}
          </p>
        </div>

        <button
          onClick={handleDownloadDirectSvg}
          className="btn-secondary"
          style={{ fontSize: 12, padding: '6px 12px', gap: 6, display: 'flex', alignItems: 'center' }}
          title="Download vector SVG architecture diagram"
        >
          <Download size={14} color="var(--primary-text)" />
          <span>Download SVG Diagram</span>
        </button>
      </div>

      {/* SVG Canvas Container */}
      <div
        style={{
          width: '100%',
          overflowX: 'auto',
          background: 'var(--bg-card)',
          borderRadius: 8,
          border: '1px solid var(--border-color)',
          boxShadow: 'inset 0 1px 3px rgb(69 60 55 / 0.02)'
        }}
      >
        <svg
          ref={svgRef}
          data-architecture-diagram="true"
          viewBox={`0 0 ${svgWidth} ${totalSvgHeight}`}
          style={{ width: '100%', minWidth: 700, height: 'auto', display: 'block' }}
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label={isOperationalOrManual ? `Operational Workflow Diagram for ${projectName}` : `Architecture Topology for ${projectName}`}
        >
          <defs>
            <filter id="cardShadow" x="-5%" y="-5%" width="110%" height="115%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="var(--text-main)" floodOpacity="0.06" />
            </filter>
            <filter id="activeNodeGlow" x="-10%" y="-10%" width="120%" height="125%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="var(--primary-text)" floodOpacity="0.25" />
            </filter>
            <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--text-muted)" />
            </marker>
          </defs>

          {/* Canvas Background */}
          <rect width={svgWidth} height={totalSvgHeight} fill="var(--bg-card)" />

          {/* Header Banner */}
          <g transform="translate(30, 20)">
            <rect width={svgWidth - 60} height="46" rx="8" fill="var(--bg-subtle)" />
            <text x="20" y="28" fill="var(--text-main)" fontSize="15" fontWeight="700" fontFamily="system-ui, -apple-system, sans-serif">
              {projectName} — {versionName} {isOperationalOrManual ? 'Operational Workflow' : 'Architecture Topography'} ({techData.architecture_pattern || (isOperationalOrManual ? 'Operational Toolchain' : 'Standard Cloud')})
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
                  stroke="var(--text-muted)"
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
                      fill="var(--bg-card)"
                      stroke={isSelected ? tier.color : 'var(--border-color)'}
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
                      fill="var(--text-main)"
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
                      fill="var(--text-main)"
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
                      fill="var(--text-main)"
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
            background: 'var(--bg-card)',
            boxShadow: '-8px 0 24px rgb(69 60 55 / 0.15)',
            borderTopRightRadius: 8,
            borderBottomRightRadius: 8,
            borderLeft: '1px solid var(--border-color)',
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
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--bg-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: 'var(--bg-subtle)' }}>
            <div>
              <span className="badge" style={{ fontSize: 11, background: 'var(--bg-subtle)', color: 'var(--primary-text)', marginBottom: 4, display: 'inline-block' }}>
                {selectedTech.category}
              </span>
              <h4 id="tech-drawer-title" style={{ margin: '4px 0 0 0', fontSize: 17, fontWeight: 700, color: 'var(--text-main)' }}>
                {selectedTech.technology || selectedTech.name}
              </h4>
            </div>
            <button
              onClick={() => setSelectedTech(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, borderRadius: 4 }}
              aria-label="Close details"
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
            <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
              <h5 style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--primary-text)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={15} color="var(--primary-text)" /> Selection Rationale & Suitability
              </h5>
              <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: 'var(--primary-text)' }}>
                {selectedTech.suitability}
              </p>
            </div>

            {/* Implementation Guidance */}
            {selectedTech.implementation_guidance && (
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
                <h5 style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ArrowRight size={15} color="var(--primary-text)" /> Implementation Guidance
                </h5>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-muted)' }}>
                  {selectedTech.implementation_guidance}
                </p>
              </div>
            )}

            {/* Cost Tier */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8 }}>
              <DollarSign size={16} color="var(--primary-text)" />
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block' }}>Estimated Cost Tier</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)' }}>
                  {selectedTech.estimated_cost_tier || 'Low / Free Tier'}
                </span>
              </div>
            </div>

            {/* Trade-offs & Risks */}
            {selectedTech.trade_offs && (
              <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
                <h5 style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--primary-text)', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={15} color="var(--primary-text)" /> Known Trade-offs & Limitations
                </h5>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.5, color: 'var(--primary-text)' }}>
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
