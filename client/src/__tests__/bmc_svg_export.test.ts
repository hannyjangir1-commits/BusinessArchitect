import { describe, expect, it } from 'vitest';
import { buildCompleteBmcSvg } from '../components/RadialBMCInfographic';
import { BMCData } from '../types';

describe('complete BMC SVG export', () => {
  it('includes every block and replaces theme variables with portable colors', () => {
    document.documentElement.style.setProperty('--bg-card', '#fffdf9');
    document.documentElement.style.setProperty('--text-main', '#333333');
    document.documentElement.style.setProperty('--primary-text', '#8a4b2f');
    const source = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    source.setAttribute('viewBox', '0 0 1100 750');
    const sourceRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    sourceRect.setAttribute('fill', 'var(--bg-card)');
    source.appendChild(sourceRect);
    const data: BMCData = {
      customer_segments: ['Students and PCB design teams'], value_propositions: ['Reduce design iteration time'],
      channels: ['Direct sales'], customer_relationships: ['Technical support'], revenue_streams: ['Subscription'],
      key_resources: ['Engineering expertise'], key_activities: ['Validate design rules'],
      key_partnerships: ['PCB manufacturers'], cost_structure: ['Engineering and hosting'],
      actionable_guidance: { key_activities: 'Interview prospective users.' }, assumptions: ['Teams will pay for saved time.']
    };

    const exported = buildCompleteBmcSvg(source, 'PCB Planner', 'MVP', data);
    const serialized = new XMLSerializer().serializeToString(exported);

    expect(exported.getAttribute('height')).not.toBe('750');
    expect(serialized).toContain('Students and PCB design teams');
    expect(serialized).toContain('Interview prospective users.');
    expect(serialized).toContain('Assumptions to validate');
    expect(serialized).not.toContain('var(--');
  });
});
