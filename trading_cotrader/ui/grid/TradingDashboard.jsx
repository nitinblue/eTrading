import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, TrendingUp, TrendingDown, DollarSign, Activity, AlertTriangle, RefreshCw, Plus, Filter } from 'lucide-react';

// Mock data - Replace with API calls to your backend
const mockPortfolios = [
  {
    id: 'p1',
    name: 'Tastytrade Main',
    portfolio_type: 'real',
    broker: 'tastytrade',
    total_equity: 30527.24,
    cash_balance: 25328.24,
    buying_power: 29155.43,
    total_pnl: 1527.50,
    daily_pnl: 125.30,
    greeks: { delta: -45.2, gamma: 2.3, theta: 85.5, vega: -120.3 },
    positions_count: 8,
    trades_count: 12
  },
  {
    id: 'p2',
    name: '0DTE Strategies',
    portfolio_type: 'what_if',
    broker: null,
    total_equity: 10000.00,
    cash_balance: 10000.00,
    buying_power: 10000.00,
    total_pnl: 0,
    daily_pnl: 0,
    greeks: { delta: 0, gamma: 0, theta: 0, vega: 0 },
    positions_count: 0,
    trades_count: 3
  }
];

const mockTrades = {
  'p1': [
    {
      id: 't1',
      underlying: 'SPY',
      strategy: 'Iron Condor',
      trade_type: 'real',
      trade_status: 'executed',
      entry_price: 2.45,
      current_price: 1.80,
      pnl: 65.00,
      pnl_pct: 26.5,
      greeks: { delta: -5.2, theta: 12.5, vega: -8.3 },
      dte: 18,
      opened_at: '2025-01-20',
      max_profit: 245,
      max_loss: 255
    },
    {
      id: 't2',
      underlying: 'IWM',
      strategy: 'Put Credit Spread',
      trade_type: 'real',
      trade_status: 'executed',
      entry_price: 1.85,
      current_price: 1.20,
      pnl: 65.00,
      pnl_pct: 35.1,
      greeks: { delta: 8.5, theta: 8.2, vega: -5.1 },
      dte: 25,
      opened_at: '2025-01-15',
      max_profit: 185,
      max_loss: 315
    },
    {
      id: 't3',
      underlying: 'QQQ',
      strategy: 'Strangle',
      trade_type: 'real',
      trade_status: 'executed',
      entry_price: 3.20,
      current_price: 3.85,
      pnl: -65.00,
      pnl_pct: -20.3,
      greeks: { delta: -2.1, theta: 15.8, vega: -12.4 },
      dte: 12,
      opened_at: '2025-01-22',
      max_profit: 320,
      max_loss: null
    }
  ],
  'p2': [
    {
      id: 't4',
      underlying: 'SPX',
      strategy: 'Iron Condor',
      trade_type: 'what_if',
      trade_status: 'intent',
      entry_price: 5.50,
      current_price: null,
      pnl: null,
      pnl_pct: null,
      greeks: { delta: 0, theta: 45, vega: -25 },
      dte: 0,
      opened_at: null,
      max_profit: 550,
      max_loss: 450
    }
  ]
};

// Status badge colors
const statusColors = {
  intent: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  evaluated: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  pending: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  executed: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  closed: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  rolled: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
};

const typeColors = {
  real: 'bg-emerald-500/10 text-emerald-400',
  what_if: 'bg-violet-500/10 text-violet-400',
  paper: 'bg-amber-500/10 text-amber-400',
  backtest: 'bg-slate-500/10 text-slate-400'
};

// Format currency
const formatCurrency = (value, decimals = 2) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(value);
};

// Format percentage
const formatPct = (value) => {
  if (value === null || value === undefined) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
};

// Format Greek
const formatGreek = (value, decimals = 1) => {
  if (value === null || value === undefined) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}`;
};

// Portfolio Card Component
const PortfolioCard = ({ portfolio, isExpanded, onToggle, trades }) => {
  const pnlColor = portfolio.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
  const dailyPnlColor = portfolio.daily_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
  
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700/50 overflow-hidden mb-4">
      {/* Portfolio Header */}
      <div 
        className="p-4 cursor-pointer hover:bg-slate-700/30 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isExpanded ? 
              <ChevronDown className="w-5 h-5 text-slate-400" /> : 
              <ChevronRight className="w-5 h-5 text-slate-400" />
            }
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-white">{portfolio.name}</h3>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[portfolio.portfolio_type]}`}>
                  {portfolio.portfolio_type.toUpperCase()}
                </span>
              </div>
              <div className="text-sm text-slate-400 mt-0.5">
                {portfolio.broker || 'Simulated'} • {portfolio.positions_count} positions • {portfolio.trades_count} trades
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-8">
            {/* Equity */}
            <div className="text-right">
              <div className="text-xs text-slate-500 uppercase tracking-wide">Equity</div>
              <div className="text-lg font-mono text-white">{formatCurrency(portfolio.total_equity)}</div>
            </div>
            
            {/* P&L */}
            <div className="text-right">
              <div className="text-xs text-slate-500 uppercase tracking-wide">Total P&L</div>
              <div className={`text-lg font-mono ${pnlColor}`}>{formatCurrency(portfolio.total_pnl)}</div>
            </div>
            
            {/* Daily P&L */}
            <div className="text-right">
              <div className="text-xs text-slate-500 uppercase tracking-wide">Today</div>
              <div className={`text-lg font-mono ${dailyPnlColor}`}>{formatCurrency(portfolio.daily_pnl)}</div>
            </div>
            
            {/* Greeks Summary */}
            <div className="flex gap-4 pl-4 border-l border-slate-700">
              <div className="text-center">
                <div className="text-xs text-slate-500">Δ</div>
                <div className="font-mono text-sm text-slate-300">{formatGreek(portfolio.greeks.delta)}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-slate-500">Θ</div>
                <div className="font-mono text-sm text-emerald-400">{formatGreek(portfolio.greeks.theta)}</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-slate-500">V</div>
                <div className="font-mono text-sm text-slate-300">{formatGreek(portfolio.greeks.vega)}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Trades Grid */}
      {isExpanded && (
        <div className="border-t border-slate-700/50">
          <TradesGrid trades={trades} portfolioType={portfolio.portfolio_type} />
        </div>
      )}
    </div>
  );
};

// Trades Grid Component - Excel-like
const TradesGrid = ({ trades, portfolioType }) => {
  const [selectedTrade, setSelectedTrade] = useState(null);
  
  if (!trades || trades.length === 0) {
    return (
      <div className="p-8 text-center text-slate-500">
        <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p>No trades in this portfolio</p>
        <button className="mt-3 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded text-white text-sm transition-colors">
          + Create {portfolioType === 'what_if' ? 'What-If' : 'New'} Trade
        </button>
      </div>
    );
  }
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-900/50 text-slate-400 text-xs uppercase tracking-wider">
            <th className="px-4 py-3 text-left font-medium">Underlying</th>
            <th className="px-4 py-3 text-left font-medium">Strategy</th>
            <th className="px-4 py-3 text-center font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Entry</th>
            <th className="px-4 py-3 text-right font-medium">Current</th>
            <th className="px-4 py-3 text-right font-medium">P&L</th>
            <th className="px-4 py-3 text-right font-medium">P&L %</th>
            <th className="px-4 py-3 text-center font-medium">DTE</th>
            <th className="px-4 py-3 text-center font-medium">Δ</th>
            <th className="px-4 py-3 text-center font-medium">Θ</th>
            <th className="px-4 py-3 text-right font-medium">Max Profit</th>
            <th className="px-4 py-3 text-right font-medium">Max Loss</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade, idx) => {
            const pnlColor = trade.pnl === null ? 'text-slate-500' : 
                            trade.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
            const isSelected = selectedTrade === trade.id;
            
            return (
              <tr 
                key={trade.id}
                onClick={() => setSelectedTrade(isSelected ? null : trade.id)}
                className={`
                  border-t border-slate-700/30 cursor-pointer transition-colors
                  ${isSelected ? 'bg-violet-500/10' : idx % 2 === 0 ? 'bg-slate-800/30' : 'bg-slate-800/10'}
                  hover:bg-slate-700/30
                `}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">{trade.underlying}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${typeColors[trade.trade_type]}`}>
                      {trade.trade_type === 'what_if' ? 'WI' : 'R'}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-300">{trade.strategy}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`px-2 py-1 rounded text-xs font-medium border ${statusColors[trade.trade_status]}`}>
                    {trade.trade_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">
                  {formatCurrency(trade.entry_price)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-slate-300">
                  {formatCurrency(trade.current_price)}
                </td>
                <td className={`px-4 py-3 text-right font-mono ${pnlColor}`}>
                  {formatCurrency(trade.pnl)}
                </td>
                <td className={`px-4 py-3 text-right font-mono ${pnlColor}`}>
                  {formatPct(trade.pnl_pct)}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`font-mono ${trade.dte <= 7 ? 'text-amber-400' : 'text-slate-300'}`}>
                    {trade.dte}
                  </span>
                </td>
                <td className="px-4 py-3 text-center font-mono text-slate-400">
                  {formatGreek(trade.greeks?.delta)}
                </td>
                <td className="px-4 py-3 text-center font-mono text-emerald-400">
                  {formatGreek(trade.greeks?.theta)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-400">
                  {formatCurrency(trade.max_profit)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-rose-400">
                  {trade.max_loss ? formatCurrency(trade.max_loss) : '∞'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      
      {/* Trade Detail Panel */}
      {selectedTrade && (
        <TradeDetailPanel 
          trade={trades.find(t => t.id === selectedTrade)} 
          onClose={() => setSelectedTrade(null)}
        />
      )}
    </div>
  );
};

// Trade Detail Panel
const TradeDetailPanel = ({ trade, onClose }) => {
  if (!trade) return null;
  
  return (
    <div className="border-t border-slate-700/50 bg-slate-900/50 p-4">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h4 className="text-lg font-semibold text-white">{trade.underlying} - {trade.strategy}</h4>
          <p className="text-sm text-slate-400">Opened: {trade.opened_at || 'Not yet opened'}</p>
        </div>
        <div className="flex gap-2">
          <button className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded text-white text-sm transition-colors">
            Close Trade
          </button>
          <button className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 rounded text-white text-sm transition-colors">
            Roll
          </button>
          <button className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded text-white text-sm transition-colors">
            Adjust
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-4 gap-4">
        {/* P&L Attribution */}
        <div className="bg-slate-800/50 rounded p-3">
          <h5 className="text-xs text-slate-500 uppercase mb-2">P&L Attribution</h5>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Delta P&L</span>
              <span className="font-mono text-emerald-400">+$32.50</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Theta P&L</span>
              <span className="font-mono text-emerald-400">+$45.00</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Vega P&L</span>
              <span className="font-mono text-rose-400">-$12.50</span>
            </div>
            <div className="flex justify-between border-t border-slate-700 pt-1 mt-1">
              <span className="text-slate-300">Total</span>
              <span className="font-mono text-emerald-400 font-semibold">{formatCurrency(trade.pnl)}</span>
            </div>
          </div>
        </div>
        
        {/* Risk Metrics */}
        <div className="bg-slate-800/50 rounded p-3">
          <h5 className="text-xs text-slate-500 uppercase mb-2">Risk</h5>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Max Profit</span>
              <span className="font-mono text-emerald-400">{formatCurrency(trade.max_profit)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Max Loss</span>
              <span className="font-mono text-rose-400">{trade.max_loss ? formatCurrency(trade.max_loss) : '∞'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Risk/Reward</span>
              <span className="font-mono text-slate-300">
                {trade.max_loss ? `1:${(trade.max_profit / trade.max_loss).toFixed(1)}` : 'Undefined'}
              </span>
            </div>
          </div>
        </div>
        
        {/* Greeks */}
        <div className="bg-slate-800/50 rounded p-3">
          <h5 className="text-xs text-slate-500 uppercase mb-2">Greeks</h5>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-slate-500">Delta</span>
              <div className="font-mono text-slate-300">{formatGreek(trade.greeks?.delta)}</div>
            </div>
            <div>
              <span className="text-slate-500">Gamma</span>
              <div className="font-mono text-slate-300">{formatGreek(trade.greeks?.gamma, 2)}</div>
            </div>
            <div>
              <span className="text-slate-500">Theta</span>
              <div className="font-mono text-emerald-400">{formatGreek(trade.greeks?.theta)}</div>
            </div>
            <div>
              <span className="text-slate-500">Vega</span>
              <div className="font-mono text-slate-300">{formatGreek(trade.greeks?.vega)}</div>
            </div>
          </div>
        </div>
        
        {/* Actions */}
        <div className="bg-slate-800/50 rounded p-3">
          <h5 className="text-xs text-slate-500 uppercase mb-2">Exit Rules</h5>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Profit Target</span>
              <span className="font-mono text-slate-300">50%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Stop Loss</span>
              <span className="font-mono text-slate-300">200%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">DTE Exit</span>
              <span className="font-mono text-slate-300">7 days</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Main Dashboard Component
export default function TradingDashboard() {
  const [portfolios, setPortfolios] = useState(mockPortfolios);
  const [trades, setTrades] = useState(mockTrades);
  const [expandedPortfolios, setExpandedPortfolios] = useState(['p1']);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const togglePortfolio = (portfolioId) => {
    setExpandedPortfolios(prev => 
      prev.includes(portfolioId) 
        ? prev.filter(id => id !== portfolioId)
        : [...prev, portfolioId]
    );
  };
  
  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsRefreshing(false);
  };
  
  // Calculate totals
  const totalEquity = portfolios.reduce((sum, p) => sum + p.total_equity, 0);
  const totalPnl = portfolios.reduce((sum, p) => sum + p.total_pnl, 0);
  const totalDailyPnl = portfolios.reduce((sum, p) => sum + p.daily_pnl, 0);
  const totalDelta = portfolios.reduce((sum, p) => sum + p.greeks.delta, 0);
  const totalTheta = portfolios.reduce((sum, p) => sum + p.greeks.theta, 0);
  
  return (
    <div className="min-h-screen bg-slate-900 text-white">
      {/* Header */}
      <header className="bg-slate-800/80 border-b border-slate-700/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Activity className="w-6 h-6 text-violet-400" />
                <h1 className="text-xl font-bold">CoTrader</h1>
              </div>
              <span className="text-slate-500">|</span>
              <span className="text-slate-400 text-sm">Portfolio Dashboard</span>
            </div>
            
            <div className="flex items-center gap-4">
              <button 
                onClick={handleRefresh}
                className={`p-2 rounded hover:bg-slate-700 transition-colors ${isRefreshing ? 'animate-spin' : ''}`}
              >
                <RefreshCw className="w-5 h-5 text-slate-400" />
              </button>
              <button className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors">
                <Plus className="w-4 h-4" />
                New What-If
              </button>
            </div>
          </div>
        </div>
      </header>
      
      {/* Summary Bar */}
      <div className="bg-slate-800/30 border-b border-slate-700/30">
        <div className="max-w-7xl mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <div>
                <span className="text-xs text-slate-500 uppercase tracking-wide">Total Equity</span>
                <div className="text-xl font-mono font-semibold">{formatCurrency(totalEquity)}</div>
              </div>
              <div>
                <span className="text-xs text-slate-500 uppercase tracking-wide">Total P&L</span>
                <div className={`text-xl font-mono font-semibold ${totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {formatCurrency(totalPnl)}
                </div>
              </div>
              <div>
                <span className="text-xs text-slate-500 uppercase tracking-wide">Today</span>
                <div className={`text-xl font-mono font-semibold ${totalDailyPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {formatCurrency(totalDailyPnl)}
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-6 pl-6 border-l border-slate-700">
              <div className="text-center">
                <span className="text-xs text-slate-500">Net Δ</span>
                <div className={`font-mono text-lg ${Math.abs(totalDelta) > 100 ? 'text-amber-400' : 'text-slate-300'}`}>
                  {formatGreek(totalDelta)}
                </div>
              </div>
              <div className="text-center">
                <span className="text-xs text-slate-500">Daily Θ</span>
                <div className="font-mono text-lg text-emerald-400">{formatGreek(totalTheta)}</div>
              </div>
              <div className="flex items-center gap-2">
                {Math.abs(totalDelta) > 100 && (
                  <div className="flex items-center gap-1 px-2 py-1 bg-amber-500/20 rounded text-amber-400 text-xs">
                    <AlertTriangle className="w-3 h-3" />
                    High Delta
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Portfolios */}
        <div className="space-y-4">
          {portfolios.map(portfolio => (
            <PortfolioCard
              key={portfolio.id}
              portfolio={portfolio}
              isExpanded={expandedPortfolios.includes(portfolio.id)}
              onToggle={() => togglePortfolio(portfolio.id)}
              trades={trades[portfolio.id] || []}
            />
          ))}
        </div>
        
        {/* Add Portfolio Button */}
        <button className="w-full mt-4 p-4 border-2 border-dashed border-slate-700 rounded-lg text-slate-500 hover:text-slate-400 hover:border-slate-600 transition-colors flex items-center justify-center gap-2">
          <Plus className="w-5 h-5" />
          Create What-If Portfolio
        </button>
      </main>
      
      {/* Footer */}
      <footer className="border-t border-slate-700/50 bg-slate-800/30 mt-8">
        <div className="max-w-7xl mx-auto px-6 py-4 text-center text-sm text-slate-500">
          <p>CoTrader • Paper Trading Mode • Last sync: {new Date().toLocaleTimeString()}</p>
        </div>
      </footer>
    </div>
  );
}
