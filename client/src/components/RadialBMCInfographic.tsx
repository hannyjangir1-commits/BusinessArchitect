import React, { useRef, useState, useEffect } from 'react';
import { BMCData } from '../types';
import { Download, Map, X, CheckCircle2, AlertCircle, MessageCircle } from 'lucide-react';

interface Props {
  projectName: string;
  stage: string;
  data: BMCData;
}

const SVG_NS = 'http://www.w3.org/2000/svg';

const BMC_BLOCKS = [
  { key: 'value_propositions', title: 'Value Propositions', color: '#687f5d', number: '01', angle: -90, description: 'Core bundles of value and solutions addressing target customer pain points.' },
  { key: 'customer_relationships', title: 'Customer Relationships', color: '#b77d68', number: '02', angle: -50, description: 'Types of relationships established with each customer segment.' },
  { key: 'channels', title: 'Channels', color: '#bb816a', number: '03', angle: -10, description: 'Touchpoints through which you communicate and deliver value propositions.' },
  { key: 'customer_segments', title: 'Customer Segments', color: '#c39270', number: '04', angle: 30, description: 'Distinct groups of people or organizations the venture aims to serve.' },
  { key: 'revenue_streams', title: 'Revenue Streams', color: '#788e68', number: '05', angle: 70, description: 'Cash generated from each customer segment through pricing mechanisms.' },
  { key: 'cost_structure', title: 'Cost Structure', color: '#b49460', number: '06', angle: 110, description: 'All monetary expenses incurred to operate the business model.' },
  { key: 'key_partnerships', title: 'Key Partnerships', color: '#78906c', number: '07', angle: 150, description: 'Network of suppliers, distributors, and strategic alliances.' },
  { key: 'key_activities', title: 'Key Activities', color: '#9a815c', number: '08', angle: 190, description: 'Most crucial actions a company must perform to execute successfully.' },
  { key: 'key_resources', title: 'Key Resources', color: '#b09a68', number: '09', angle: 230, description: 'Most important physical, intellectual, human, or financial assets.' },
] as const;

function appendWrappedSvgText(
  parent: SVGElement,
  value: string,
  x: number,
  y: number,
  maxChars: number,
  lineHeight: number,
  fontSize: number,
  fill: string,
  fontWeight = '400'
): number {
  const words = value.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    if (line && `${line} ${word}`.length > maxChars) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);

  const text = document.createElementNS(SVG_NS, 'text');
  text.setAttribute('x', String(x));
  text.setAttribute('y', String(y));
  text.setAttribute('font-size', String(fontSize));
  text.setAttribute('font-family', 'Arial, sans-serif');
  text.setAttribute('font-weight', fontWeight);
  text.setAttribute('fill', fill);
  lines.forEach((lineText, index) => {
    const tspan = document.createElementNS(SVG_NS, 'tspan');
    tspan.setAttribute('x', String(x));
    tspan.setAttribute('dy', index === 0 ? '0' : String(lineHeight));
    tspan.textContent = lineText;
    text.appendChild(tspan);
  });
  parent.appendChild(text);
  return Math.max(lines.length, 1) * lineHeight;
}

export function buildCompleteBmcSvg(
  sourceSvg: SVGSVGElement,
  projectName: string,
  stage: string,
  data: BMCData
): SVGSVGElement {
  const clone = sourceSvg.cloneNode(true) as SVGSVGElement;
  clone.removeAttribute('style');
  clone.setAttribute('width', '1100');

  const appendix = document.createElementNS(SVG_NS, 'g');
  let y = 790;
  y += appendWrappedSvgText(appendix, `${projectName} — Complete Business Model Canvas`, 40, y, 105, 28, 23, '#626b5f', '700');
  y += appendWrappedSvgText(appendix, `Stage: ${stage}. The sections below contain every generated point, validation guidance, and assumptions.`, 40, y + 4, 135, 21, 13, '#687164');
  y += 16;

  for (const block of BMC_BLOCKS) {
    const items = (data[block.key] as string[] | undefined) || [];
    y += appendWrappedSvgText(appendix, block.title, 40, y + 4, 115, 23, 17, block.color, '700');
    y += appendWrappedSvgText(appendix, block.description, 40, y + 4, 135, 19, 12, '#687164');
    for (const [index, item] of items.entries()) {
      y += appendWrappedSvgText(appendix, `${index + 1}. ${item}`, 56, y + 7, 132, 19, 12, 'var(--border-color)');
    }
    const guidance = data.actionable_guidance?.[block.key];
    if (guidance) {
      y += appendWrappedSvgText(appendix, `What to do: ${guidance}`, 56, y + 7, 132, 19, 12, '#166534');
    }
    y += 14;
  }

  if (data.assumptions?.length) {
    y += appendWrappedSvgText(appendix, 'Assumptions to validate', 40, y + 4, 115, 23, 17, '#92400e', '700');
    for (const [index, assumption] of data.assumptions.entries()) {
      y += appendWrappedSvgText(appendix, `${index + 1}. ${assumption}`, 56, y + 7, 132, 19, 12, '#78350f');
    }
  }

  const appendixBackground = document.createElementNS(SVG_NS, 'rect');
  appendixBackground.setAttribute('x', '0');
  appendixBackground.setAttribute('y', '750');
  appendixBackground.setAttribute('width', '1100');
  appendixBackground.setAttribute('height', String(y - 750 + 32));
  appendixBackground.setAttribute('fill', '#ffffff');
  clone.appendChild(appendixBackground);
  clone.appendChild(appendix);
  clone.setAttribute('viewBox', `0 0 1100 ${y + 32}`);
  clone.setAttribute('height', String(y + 32));
  return clone;
}

export const RadialBMCInfographic: React.FC<Props> = ({ projectName, stage, data }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const blocksConfig = BMC_BLOCKS;

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
    const completeSvg = buildCompleteBmcSvg(svgRef.current, projectName, stage, data);
    const svgData = new XMLSerializer().serializeToString(completeSvg);
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
    <div className="radial-bmc-container" style={{ position: 'relative', width: '100%', background: '#ffffff', borderRadius: 12, border: '1px solid #dfe2d6', padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
            <Map size={18} /> Radial Business Model Canvas Mind Map
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
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
              <stop offset="0%" stopColor="#82936d" stopOpacity="0.18" />
              <stop offset="100%" stopColor="var(--text-main)" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="centerNodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#5d7550" />
              <stop offset="100%" stopColor="#a68757" />
            </linearGradient>
            <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodOpacity="0.08" floodColor="var(--text-main)" />
            </filter>
            <filter id="hoverGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="6" stdDeviation="10" floodOpacity="0.2" floodColor="#6d855f" />
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
            <circle r="78" fill="none" stroke="#6d855f" strokeWidth="2" strokeDasharray="6 4" opacity="0.6" />
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
                <title>{`${b.title}: ${items.join(' ')}`}</title>
                <desc>{`${b.description} ${data.actionable_guidance?.[b.key] || ''} ${(data.assumptions || []).join(' ')}`}</desc>
                {/* Card Container */}
                <rect
                  width={cardW}
                  height={cardH}
                  rx="10"
                  fill="#ffffff"
                  stroke={isSelected ? b.color : '#dfe2d6'}
                  strokeWidth={isSelected ? '2.5' : '1.5'}
                  filter={isSelected ? 'url(#hoverGlow)' : 'url(#cardShadow)'}
                />
                {/* Top Category Accent Line */}
                <path d={`M 0 10 Q 0 0 10 0 L ${cardW - 10} 0 Q ${cardW} 0 ${cardW} 10 L ${cardW} 28 L 0 28 Z`} fill={b.color} opacity={isSelected ? 0.25 : 0.12} />
                <rect x="0" y="0" width={cardW} height="3" fill={b.color} rx="1" />

                {/* Numbered section mark keeps the map legible at compact sizes. */}
                <circle cx="17" cy="15" r="9" fill={b.color} opacity="0.14" />
                <text x="17" y="18" textAnchor="middle" fontSize="7.5" fontWeight="800" fill={b.color} fontFamily="sans-serif">
                  {b.number}
                </text>
                <text x="31" y="19" fontSize="10.5" fontWeight="800" fill={b.color} fontFamily="sans-serif">
                  {b.title}
                </text>

                {/* Item Pills / Readable Summary without clipping */}
                {items.slice(0, 3).map((it, idx) => {
                  const label = it.length > 25 ? it.slice(0, 23) + '…' : it;
                  return (
                    <g key={`line-${idx}`} transform={`translate(10, ${44 + idx * 22})`}>
                      <circle cx="3" cy="-3" r="2.5" fill={b.color} />
                      <text x="10" y="0" fontSize="9.5" fill="#626b5f" fontWeight="500" fontFamily="sans-serif">
                        {label}
                      </text>
                    </g>
                  );
                })}

                {/* Counter Footer */}
                <g transform={`translate(10, ${cardH - 10})`}>
                  <rect x="0" y="-10" width={cardW - 20} height="15" rx="4" fill={isSelected ? b.color : '#f0f1e9'} opacity={isSelected ? 0.15 : 0.7} />
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
            borderLeft: '1px solid #dfe2d6',
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
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #f0f1e9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: '#f7f6ef' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="bmc-detail-number" style={{ color: activeBlockConfig.color }}>{activeBlockConfig.number}</span>
                <h4 id="detail-panel-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: activeBlockConfig.color }}>
                  {activeBlockConfig.title}
                </h4>
              </div>
              <p style={{ margin: '4px 0 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
                {activeBlockConfig.description}
              </p>
            </div>
            <button
              onClick={() => setSelectedKey(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, borderRadius: 4 }}
              aria-label="Close details"
            >
              <X size={18} />
            </button>
          </div>

          <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Complete Items List - No Clipping */}
            <div>
              <h5 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-main)', margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={15} color={activeBlockConfig.color} />
                Complete Section Content ({activeItems.length} Points)
              </h5>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activeItems.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: '#f7f6ef',
                      border: '1px solid #dfe2d6',
                      borderRadius: 8,
                      padding: '10px 14px',
                      fontSize: 13,
                      lineHeight: 1.5,
                      color: 'var(--text-main)',
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
                <MessageCircle size={15} color="#718765" /> Actionable Guidance: What to Test, Decide & Validate
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
