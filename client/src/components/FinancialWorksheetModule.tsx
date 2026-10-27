import React, { useState, useEffect } from 'react';
import { Project, FinancialWorksheet, StartupCostItem, FixedCostItem, VariableCostItem, RevenueModelConfig } from '../types';
import { api } from '../services/api';
import {
  DollarSign, Calculator, Plus, Trash2, CheckCircle2,
  AlertCircle, RefreshCw, Save, Info, ArrowUpRight, TrendingDown
} from 'lucide-react';

interface Props {
  project: Project;
}

export const FinancialWorksheetModule: React.FC<Props> = ({ project }) => {
  const [worksheet, setWorksheet] = useState<FinancialWorksheet | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load existing worksheet or initialize default
  useEffect(() => {
    let isMounted = true;
    const fetchWorksheet = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.financials.get(project.id);
        if (isMounted) setWorksheet(data);
      } catch (err: any) {
        if (isMounted) setError(err.message || 'Failed to load financial worksheet.');
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    fetchWorksheet();
    return () => { isMounted = false; };
  }, [project.id]);

  // Client-side pure deterministic calculations for instant recalculation upon keystroke
  const calculatedMetrics = React.useMemo(() => {
    if (!worksheet) return null;

    const totalStartup = (worksheet.startup_costs || []).reduce((acc, it) => acc + (Number(it.amount) || 0), 0);

    let monthlyFixed = 0;
    (worksheet.fixed_costs || []).forEach(it => {
      const amt = Number(it.monthly_amount) || 0;
      const freq = (it.frequency || 'monthly').toLowerCase();
      if (freq === 'annual' || freq === 'yearly') monthlyFixed += amt / 12;
      else if (freq === 'quarterly') monthlyFixed += amt / 3;
      else if (freq === 'weekly') monthlyFixed += amt * 4.333;
      else monthlyFixed += amt;
    });

    const unitVariable = (worksheet.variable_costs || []).reduce((acc, it) => acc + (Number(it.unit_cost) || 0), 0);
    const price = Number(worksheet.revenue_model?.price_per_unit) || 0;
    const unitMargin = Math.round((price - unitVariable) * 100) / 100;
    const marginRatio = price > 0 ? Math.round(((unitMargin / price) * 100) * 100) / 100 : 0;

    let breakevenUnits: number | null = null;
    let breakevenRevenue: number | null = null;
    if (unitMargin > 0 && monthlyFixed > 0) {
      breakevenUnits = Math.ceil(monthlyFixed / unitMargin);
      breakevenRevenue = Math.round((breakevenUnits * price) * 100) / 100;
    }

    const cash = Number(worksheet.cash_available) || 0;
    const monthlyBurn = Math.round(monthlyFixed * 100) / 100;
    let runwayMonths: number | null = null;
    if (monthlyBurn > 0 && cash > 0) {
      runwayMonths = Math.round((cash / monthlyBurn) * 10) / 10;
    }

    return {
      totalStartup,
      monthlyFixed: Math.round(monthlyFixed * 100) / 100,
      unitVariable: Math.round(unitVariable * 100) / 100,
      unitMargin,
      marginRatio,
      breakevenUnits,
      breakevenRevenue,
      monthlyBurn,
      runwayMonths
    };
  }, [worksheet]);

  // Save handler
  const handleSave = async () => {
    if (!worksheet) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.financials.update(project.id, {
        currency: worksheet.currency,
        startup_costs: worksheet.startup_costs,
        fixed_costs: worksheet.fixed_costs,
        variable_costs: worksheet.variable_costs,
        revenue_model: worksheet.revenue_model,
        cash_available: worksheet.cash_available
      });
      setWorksheet(updated);
      setSaveNotice('Financial worksheet saved successfully.');
      setTimeout(() => setSaveNotice(null), 3500);
    } catch (err: any) {
      setError(err.message || 'Failed to save worksheet.');
    } finally {
      setIsSaving(false);
    }
  };

  // Row manipulation helpers
  const addStartupRow = () => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      startup_costs: [
        ...worksheet.startup_costs,
        { category: 'equipment', item: 'New equipment or license', amount: 100, is_confirmed: false }
      ]
    });
  };

  const removeStartupRow = (idx: number) => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      startup_costs: worksheet.startup_costs.filter((_, i) => i !== idx)
    });
  };

  const addFixedRow = () => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      fixed_costs: [
        ...worksheet.fixed_costs,
        { category: 'software', item: 'Software / subscription', monthly_amount: 50, frequency: 'monthly' }
      ]
    });
  };

  const removeFixedRow = (idx: number) => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      fixed_costs: worksheet.fixed_costs.filter((_, i) => i !== idx)
    });
  };

  const addVariableRow = () => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      variable_costs: [
        ...worksheet.variable_costs,
        { item: 'Direct unit expense', unit_cost: 5 }
      ]
    });
  };

  const removeVariableRow = (idx: number) => {
    if (!worksheet) return;
    setWorksheet({
      ...worksheet,
      variable_costs: worksheet.variable_costs.filter((_, i) => i !== idx)
    });
  };

  if (isLoading) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px auto', color: 'var(--primary-color)' }} />
        <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading financial model and formulas…</p>
      </div>
    );
  }

  if (!worksheet || !calculatedMetrics) {
    return (
      <div className="card" style={{ padding: 24, textAlign: 'center' }}>
        <AlertCircle size={28} color="#ef4444" style={{ margin: '0 auto 12px auto' }} />
        <p style={{ color: '#ef4444' }}>{error || 'Unable to load financial worksheet.'}</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div className="module-header-card">
        <div className="module-title-area">
          <div className="module-icon-large">
            <DollarSign size={22} />
          </div>
          <div className="module-titles">
            <h2>Financial Worksheet & Unit Economics</h2>
            <p>Deterministic mathematical model — visible formulas, break-even volume, and cash runway</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {saveNotice && (
            <span style={{ fontSize: 12, fontWeight: 600, color: '#10b981', display: 'flex', alignItems: 'center', gap: 4 }}>
              <CheckCircle2 size={14} /> {saveNotice}
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            {isSaving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
            <span>{isSaving ? 'Saving…' : 'Save Worksheet'}</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Formula Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: 14
      }}>
        {/* Startup Cost Card */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Total Startup Capital
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--text-main)' }}>
            ${calculatedMetrics.totalStartup.toLocaleString()}
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
            Formula: Sum of all initial equipment, legal, and setup expenses
          </span>
        </div>

        {/* Monthly Fixed Burn Card */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Monthly Fixed Operating Cost
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--text-main)' }}>
            ${calculatedMetrics.monthlyFixed.toLocaleString()}<span style={{ fontSize: 13, color: 'var(--text-muted)' }}>/mo</span>
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
            Formula: Sum of annualized, monthly, and recurring overhead
          </span>
        </div>

        {/* Unit Contribution Margin Card */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Unit Contribution Margin
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: calculatedMetrics.unitMargin > 0 ? '#10b981' : '#ef4444' }}>
            ${calculatedMetrics.unitMargin.toFixed(2)}
            <span style={{ fontSize: 13, color: 'var(--text-muted)', marginLeft: 6 }}>
              ({calculatedMetrics.marginRatio}%)
            </span>
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
            Formula: Price per unit ($ {worksheet.revenue_model?.price_per_unit || 0}) − Variable cost ($ {calculatedMetrics.unitVariable})
          </span>
        </div>

        {/* Break-Even Units Card */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Break-Even Volume
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--text-main)' }}>
            {calculatedMetrics.breakevenUnits !== null ? `${calculatedMetrics.breakevenUnits.toLocaleString()} units` : 'N/A'}
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
            Formula: Fixed costs ($ {calculatedMetrics.monthlyFixed}) ÷ Unit margin ($ {calculatedMetrics.unitMargin})
          </span>
        </div>

        {/* Runway Card */}
        <div className="card" style={{ padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>
            Cash Runway
          </div>
          <div style={{ fontSize: 24, fontWeight: 900, color: calculatedMetrics.runwayMonths && calculatedMetrics.runwayMonths < 3 ? '#ef4444' : '#10b981' }}>
            {calculatedMetrics.runwayMonths !== null ? `${calculatedMetrics.runwayMonths} mos` : 'Profitable / No burn'}
          </div>
          <span style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginTop: 4 }}>
            Formula: Cash available ($ {worksheet.cash_available}) ÷ Monthly burn ($ {calculatedMetrics.monthlyBurn})
          </span>
        </div>
      </div>

      {/* Revenue & Pricing Model Config */}
      <div className="card" style={{ padding: 20 }}>
        <h4 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Calculator size={16} color="var(--primary-color)" /> Revenue & Unit Pricing Model
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          <div>
            <label style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Pricing Structure
            </label>
            <select
              value={worksheet.revenue_model?.model_type || 'per_unit'}
              onChange={e => setWorksheet({
                ...worksheet,
                revenue_model: { ...worksheet.revenue_model, model_type: e.target.value }
              })}
              style={{
                width: '100%',
                padding: '7px 10px',
                fontSize: 12.5,
                borderRadius: 6,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)'
              }}
            >
              <option value="per_unit">Per Unit / Fixed Product Price</option>
              <option value="subscription">Monthly Recurring Subscription</option>
              <option value="service_fee">Hourly / Service Fee</option>
              <option value="custom">Custom Contract</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Selling Price per Unit ($)
            </label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={worksheet.revenue_model?.price_per_unit || 0}
              onChange={e => setWorksheet({
                ...worksheet,
                revenue_model: { ...worksheet.revenue_model, price_per_unit: parseFloat(e.target.value) || 0 }
              })}
              style={{
                width: '100%',
                padding: '7px 10px',
                fontSize: 12.5,
                borderRadius: 6,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)'
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
              Available Cash on Hand ($)
            </label>
            <input
              type="number"
              min="0"
              step="100"
              value={worksheet.cash_available || 0}
              onChange={e => setWorksheet({
                ...worksheet,
                cash_available: parseFloat(e.target.value) || 0
              })}
              style={{
                width: '100%',
                padding: '7px 10px',
                fontSize: 12.5,
                borderRadius: 6,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-card)',
                color: 'var(--text-main)'
              }}
            />
          </div>
        </div>
      </div>

      {/* Tables Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 20 }}>
        {/* Startup Costs Table */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: 0 }}>Startup Costs</h4>
            <button
              onClick={addStartupRow}
              style={{
                padding: '4px 8px',
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4
              }}
            >
              <Plus size={12} /> Add Item
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {worksheet.startup_costs.map((it, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="text"
                  value={it.item}
                  onChange={e => {
                    const next = [...worksheet.startup_costs];
                    next[idx].item = e.target.value;
                    setWorksheet({ ...worksheet, startup_costs: next });
                  }}
                  placeholder="Cost description"
                  style={{ flex: 2, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={it.amount}
                  onChange={e => {
                    const next = [...worksheet.startup_costs];
                    next[idx].amount = parseFloat(e.target.value) || 0;
                    setWorksheet({ ...worksheet, startup_costs: next });
                  }}
                  style={{ width: 90, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <button
                  onClick={() => {
                    const next = [...worksheet.startup_costs];
                    next[idx].is_confirmed = !next[idx].is_confirmed;
                    setWorksheet({ ...worksheet, startup_costs: next });
                  }}
                  style={{
                    padding: '4px 6px',
                    fontSize: 10,
                    fontWeight: 600,
                    borderRadius: 4,
                    border: 'none',
                    background: it.is_confirmed ? '#10b981' : '#6b7280',
                    color: '#fff',
                    cursor: 'pointer'
                  }}
                  title="Toggle estimate vs confirmed"
                >
                  {it.is_confirmed ? 'Confirmed' : 'Estimate'}
                </button>
                <button
                  onClick={() => removeStartupRow(idx)}
                  style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', padding: 2 }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Fixed Monthly Costs Table */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: 0 }}>Monthly Fixed Operating Overhead</h4>
            <button
              onClick={addFixedRow}
              style={{
                padding: '4px 8px',
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4
              }}
            >
              <Plus size={12} /> Add Overhead
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {worksheet.fixed_costs.map((it, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="text"
                  value={it.item}
                  onChange={e => {
                    const next = [...worksheet.fixed_costs];
                    next[idx].item = e.target.value;
                    setWorksheet({ ...worksheet, fixed_costs: next });
                  }}
                  placeholder="Rent, server, salary..."
                  style={{ flex: 2, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={it.monthly_amount}
                  onChange={e => {
                    const next = [...worksheet.fixed_costs];
                    next[idx].monthly_amount = parseFloat(e.target.value) || 0;
                    setWorksheet({ ...worksheet, fixed_costs: next });
                  }}
                  style={{ width: 90, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <select
                  value={it.frequency || 'monthly'}
                  onChange={e => {
                    const next = [...worksheet.fixed_costs];
                    next[idx].frequency = e.target.value;
                    setWorksheet({ ...worksheet, fixed_costs: next });
                  }}
                  style={{ width: 85, padding: '5px 4px', fontSize: 11, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                >
                  <option value="monthly">Monthly</option>
                  <option value="annual">Annual</option>
                  <option value="quarterly">Quarterly</option>
                  <option value="weekly">Weekly</option>
                </select>
                <button
                  onClick={() => removeFixedRow(idx)}
                  style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', padding: 2 }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Variable Unit Costs Table */}
        <div className="card" style={{ padding: 18, gridColumn: '1 / -1' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div>
              <h4 style={{ fontSize: 13.5, fontWeight: 700, margin: 0 }}>Unit Variable Costs</h4>
              <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                Expenses incurred strictly per customer, order, or unit delivered (e.g. payment fees, materials, hosting compute)
              </span>
            </div>
            <button
              onClick={addVariableRow}
              style={{
                padding: '4px 8px',
                fontSize: 11.5,
                fontWeight: 600,
                borderRadius: 4,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-main)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4
              }}
            >
              <Plus size={12} /> Add Variable Expense
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
            {worksheet.variable_costs.map((it, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'var(--bg-subtle)', padding: 8, borderRadius: 6, border: '1px solid var(--border-color)' }}>
                <input
                  type="text"
                  value={it.item}
                  onChange={e => {
                    const next = [...worksheet.variable_costs];
                    next[idx].item = e.target.value;
                    setWorksheet({ ...worksheet, variable_costs: next });
                  }}
                  placeholder="Expense item"
                  style={{ flex: 2, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={it.unit_cost}
                  onChange={e => {
                    const next = [...worksheet.variable_costs];
                    next[idx].unit_cost = parseFloat(e.target.value) || 0;
                    setWorksheet({ ...worksheet, variable_costs: next });
                  }}
                  style={{ width: 80, padding: '5px 8px', fontSize: 12, borderRadius: 4, border: '1px solid var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-main)' }}
                />
                <button
                  onClick={() => removeVariableRow(idx)}
                  style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', padding: 2 }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
