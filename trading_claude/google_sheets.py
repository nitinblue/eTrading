# ============================================================================
# GOOGLE SHEETS EXPORT
# ============================================================================

from typing import List, Dict
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd


class GoogleSheetsExporter:
    """Export portfolio data to Google Sheets"""
    
    def __init__(self, credentials_file: str):
        """
        Initialize with service account credentials
        
        Args:
            credentials_file: Path to Google service account JSON file
        """
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_file, scope
        )
        self.client = gspread.authorize(creds)
    
    def export_portfolio(self, portfolio_summary: Dict, positions: List[Dict], 
                        trades: List[Dict], spreadsheet_name: str):
        """Export complete portfolio to Google Sheets"""
        
        # Create or open spreadsheet
        try:
            spreadsheet = self.client.open(spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            spreadsheet = self.client.create(spreadsheet_name)
        
        # Export portfolio summary
        self._export_summary(spreadsheet, portfolio_summary)
        
        # Export positions
        self._export_positions(spreadsheet, positions)
        
        # Export trades
        self._export_trades(spreadsheet, trades)
        
        # Export Greeks
        self._export_greeks(spreadsheet, portfolio_summary, positions)
        
        print(f"Exported to Google Sheets: {spreadsheet.url}")
        return spreadsheet.url
    
    def _export_summary(self, spreadsheet, summary: Dict):
        """Export portfolio summary sheet"""
        try:
            worksheet = spreadsheet.worksheet("Portfolio Summary")
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet("Portfolio Summary", 20, 10)
        
        # Prepare data
        data = [
            ["Portfolio Summary", ""],
            ["", ""],
            ["Portfolio Name", summary['name']],
            ["Broker", summary['broker']],
            ["Account ID", summary['account_id']],
            ["", ""],
            ["Cash Balance", f"${summary['cash_balance']:,.2f}"],
            ["Buying Power", f"${summary['buying_power']:,.2f}"],
            ["Total Equity", f"${summary['total_equity']:,.2f}"],
            ["Total P&L", f"${summary['total_pnl']:,.2f}"],
            ["", ""],
            ["Open Positions", summary['positions_count']],
            ["Open Trades", summary['open_trades_count']],
            ["Closed Trades", summary['closed_trades_count']],
            ["", ""],
            ["Portfolio Greeks", ""],
            ["Delta", f"{summary['greeks']['delta']:.2f}"],
            ["Gamma", f"{summary['greeks']['gamma']:.4f}"],
            ["Theta", f"{summary['greeks']['theta']:.2f}"],
            ["Vega", f"{summary['greeks']['vega']:.2f}"],
            ["", ""],
            ["Last Updated", summary['last_updated']]
        ]
        
        worksheet.update('A1', data)
        
        # Format header
        worksheet.format('A1:B1', {
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER'
        })
    
    def _export_positions(self, spreadsheet, positions: List[Dict]):
        """Export positions sheet"""
        try:
            worksheet = spreadsheet.worksheet("Positions")
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet("Positions", 100, 12)
        
        if not positions:
            worksheet.update('A1', [["No positions"]])
            return
        
        # Header
        headers = [
            "Symbol", "Type", "Quantity", "Avg Price", "Current Price", 
            "Market Value", "Unrealized P&L", "P&L %", 
            "Delta", "Gamma", "Theta", "Vega"
        ]
        
        # Data rows
        rows = [headers]
        for pos in positions:
            row = [
                pos['symbol'],
                pos['asset_type'],
                pos['quantity'],
                f"${pos['average_price']:.2f}",
                f"${pos['current_price']:.2f}" if pos['current_price'] else "N/A",
                f"${pos['market_value']:,.2f}",
                f"${pos['unrealized_pnl']:,.2f}",
                f"{pos['pnl_percent']:.2f}%",
                f"{pos['greeks']['delta']:.2f}",
                f"{pos['greeks']['gamma']:.4f}",
                f"{pos['greeks']['theta']:.2f}",
                f"{pos['greeks']['vega']:.2f}"
            ]
            rows.append(row)
        
        worksheet.update('A1', rows)
        
        # Format header
        worksheet.format('A1:L1', {
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
            'textFormat': {'bold': True},
            'horizontalAlignment': 'CENTER'
        })
        
        # Conditional formatting for P&L
        if len(positions) > 0:
            worksheet.format(f'G2:G{len(positions)+1}', {
                'numberFormat': {'type': 'CURRENCY', 'pattern': '$#,##0.00'}
            })
    
    def _export_trades(self, spreadsheet, trades: List[Dict]):
        """Export trades sheet"""
        try:
            worksheet = spreadsheet.worksheet("Trades")
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet("Trades", 100, 10)
        
        if not trades:
            worksheet.update('A1', [["No trades"]])
            return
        
        # Header
        headers = [
            "Trade ID", "Underlying", "Strategy", "Opened", "Closed",
            "Status", "Legs", "Net Cost", "Current P&L", "P&L %"
        ]
        
        # Data rows
        rows = [headers]
        for trade in trades:
            row = [
                trade['trade_id'][:8],  # Shortened ID
                trade['underlying'],
                trade['strategy'],
                trade['opened_at'][:10],  # Date only
                trade['closed_at'][:10] if trade['closed_at'] else "Open",
                "Open" if trade['is_open'] else "Closed",
                trade['legs_count'],
                f"${trade['net_cost']:,.2f}",
                f"${trade['current_pnl']:,.2f}",
                f"{trade['pnl_percent']:.2f}%"
            ]
            rows.append(row)
        
        worksheet.update('A1', rows)
        
        # Format header
        worksheet.format('A1:J1', {
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
            'textFormat': {'bold': True},
            'horizontalAlignment': 'CENTER'
        })
    
    def _export_greeks(self, spreadsheet, summary: Dict, positions: List[Dict]):
        """Export Greeks analysis sheet"""
        try:
            worksheet = spreadsheet.worksheet("Greeks Analysis")
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet("Greeks Analysis", 50, 6)
        
        # Portfolio-level Greeks
        data = [
            ["Portfolio Greeks Summary", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["Greek", "Total", "% of Portfolio", "", "", ""],
            ["Delta", summary['greeks']['delta'], "", "", "", ""],
            ["Gamma", summary['greeks']['gamma'], "", "", "", ""],
            ["Theta", summary['greeks']['theta'], "", "", "", ""],
            ["Vega", summary['greeks']['vega'], "", "", "", ""],
            ["", "", "", "", "", ""],
            ["Position-Level Greeks", "", "", "", "", ""],
            ["", "", "", "", "", ""],
            ["Symbol", "Delta", "Gamma", "Theta", "Vega", "Market Value"]
        ]
        
        # Add position Greeks
        for pos in positions:
            data.append([
                pos['symbol'],
                pos['greeks']['delta'],
                pos['greeks']['gamma'],
                pos['greeks']['theta'],
                pos['greeks']['vega'],
                pos['market_value']
            ])
        
        worksheet.update('A1', data)
        
        # Format headers
        worksheet.format('A1:F1', {
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
            'textFormat': {'bold': True, 'fontSize': 14},
            'horizontalAlignment': 'CENTER'
        })
        
        worksheet.format('A11:F11', {
            'backgroundColor': {'red': 0.4, 'green': 0.7, 'blue': 0.95},
            'textFormat': {'bold': True},
            'horizontalAlignment': 'CENTER'
        })


# ============================================================================
# SIMPLE FLASK WEB UI
# ============================================================================

from flask import Flask, render_template_string, jsonify
import json


class PortfolioWebUI:
    """Simple web UI for portfolio viewing"""
    
    def __init__(self, service: PortfolioService):
        self.service = service
        self.app = Flask(__name__)
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            return render_template_string(self.INDEX_TEMPLATE)
        
        @self.app.route('/api/portfolios')
        def get_portfolios():
            portfolios = self.service.portfolio_repo.get_all()
            return jsonify([{
                'id': p.id,
                'name': p.name,
                'broker': p.broker,
                'total_equity': float(p.total_equity)
            } for p in portfolios])
        
        @self.app.route('/api/portfolio/<portfolio_id>')
        def get_portfolio(portfolio_id):
            summary = self.service.get_portfolio_summary(portfolio_id)
            return jsonify(summary)
        
        @self.app.route('/api/portfolio/<portfolio_id>/positions')
        def get_positions(portfolio_id):
            positions = self.service.get_positions_summary(portfolio_id)
            return jsonify(positions)
        
        @self.app.route('/api/portfolio/<portfolio_id>/trades')
        def get_trades(portfolio_id):
            trades = self.service.get_trades_summary(portfolio_id)
            return jsonify(trades)
        
        @self.app.route('/api/portfolio/<portfolio_id>/sync', methods=['POST'])
        def sync_portfolio(portfolio_id):
            try:
                portfolio = self.service.sync_from_broker(portfolio_id)
                return jsonify({'status': 'success', 'message': 'Portfolio synced'})
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
    
    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the web server"""
        self.app.run(host=host, port=port, debug=debug)
    
    # Simple HTML template
    INDEX_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portfolio Manager</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background: #f5f5f5;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 { color: #333; }
            .metric { 
                display: inline-block; 
                margin: 10px 20px; 
                padding: 15px;
                background: #f9f9f9;
                border-radius: 4px;
            }
            .metric-label { 
                font-size: 12px; 
                color: #666; 
                text-transform: uppercase;
            }
            .metric-value { 
                font-size: 24px; 
                font-weight: bold; 
                color: #333;
            }
            table { 
                width: 100%; 
                border-collapse: collapse; 
                margin-top: 20px;
            }
            th, td { 
                padding: 12px; 
                text-align: left; 
                border-bottom: 1px solid #ddd;
            }
            th { 
                background: #4CAF50; 
                color: white;
            }
            .positive { color: green; }
            .negative { color: red; }
            button {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                cursor: pointer;
                border-radius: 4px;
                font-size: 14px;
            }
            button:hover { background: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Portfolio Manager</h1>
            
            <div id="summary">
                <div class="metric">
                    <div class="metric-label">Total Equity</div>
                    <div class="metric-value" id="total-equity">$0.00</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Total P&L</div>
                    <div class="metric-value" id="total-pnl">$0.00</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Buying Power</div>
                    <div class="metric-value" id="buying-power">$0.00</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Positions</div>
                    <div class="metric-value" id="positions-count">0</div>
                </div>
            </div>
            
            <button onclick="syncPortfolio()">Sync from Broker</button>
            
            <h2>Positions</h2>
            <table id="positions-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Quantity</th>
                        <th>Avg Price</th>
                        <th>Current Price</th>
                        <th>Market Value</th>
                        <th>P&L</th>
                        <th>P&L %</th>
                    </tr>
                </thead>
                <tbody id="positions-body">
                </tbody>
            </table>
            
            <h2>Open Trades</h2>
            <table id="trades-table">
                <thead>
                    <tr>
                        <th>Underlying</th>
                        <th>Strategy</th>
                        <th>Opened</th>
                        <th>Legs</th>
                        <th>Net Cost</th>
                        <th>P&L</th>
                        <th>P&L %</th>
                    </tr>
                </thead>
                <tbody id="trades-body">
                </tbody>
            </table>
        </div>
        
        <script>
            let currentPortfolioId = null;
            
            async function loadPortfolios() {
                const response = await fetch('/api/portfolios');
                const portfolios = await response.json();
                if (portfolios.length > 0) {
                    currentPortfolioId = portfolios[0].id;
                    loadPortfolio(currentPortfolioId);
                }
            }
            
            async function loadPortfolio(portfolioId) {
                const response = await fetch(`/api/portfolio/${portfolioId}`);
                const data = await response.json();
                
                document.getElementById('total-equity').textContent = 
                    `$${data.total_equity.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                document.getElementById('total-pnl').textContent = 
                    `$${data.total_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                document.getElementById('buying-power').textContent = 
                    `$${data.buying_power.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
                document.getElementById('positions-count').textContent = 
                    data.positions_count;
                
                loadPositions(portfolioId);
                loadTrades(portfolioId);
            }
            
            async function loadPositions(portfolioId) {
                const response = await fetch(`/api/portfolio/${portfolioId}/positions`);
                const positions = await response.json();
                
                const tbody = document.getElementById('positions-body');
                tbody.innerHTML = '';
                
                positions.forEach(pos => {
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${pos.symbol}</td>
                        <td>${pos.quantity}</td>
                        <td>$${pos.average_price.toFixed(2)}</td>
                        <td>$${pos.current_price ? pos.current_price.toFixed(2) : 'N/A'}</td>
                        <td>$${pos.market_value.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                            $${pos.unrealized_pnl.toFixed(2)}
                        </td>
                        <td class="${pos.pnl_percent >= 0 ? 'positive' : 'negative'}">
                            ${pos.pnl_percent.toFixed(2)}%
                        </td>
                    `;
                });
            }
            
            async function loadTrades(portfolioId) {
                const response = await fetch(`/api/portfolio/${portfolioId}/trades`);
                const trades = await response.json();
                
                const tbody = document.getElementById('trades-body');
                tbody.innerHTML = '';
                
                trades.filter(t => t.is_open).forEach(trade => {
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${trade.underlying}</td>
                        <td>${trade.strategy}</td>
                        <td>${new Date(trade.opened_at).toLocaleDateString()}</td>
                        <td>${trade.legs_count}</td>
                        <td>$${trade.net_cost.toFixed(2)}</td>
                        <td class="${trade.current_pnl >= 0 ? 'positive' : 'negative'}">
                            $${trade.current_pnl.toFixed(2)}
                        </td>
                        <td class="${trade.pnl_percent >= 0 ? 'positive' : 'negative'}">
                            ${trade.pnl_percent.toFixed(2)}%
                        </td>
                    `;
                });
            }
            
            async function syncPortfolio() {
                if (!currentPortfolioId) return;
                
                const response = await fetch(`/api/portfolio/${currentPortfolioId}/sync`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.status === 'success') {
                    alert('Portfolio synced successfully!');
                    loadPortfolio(currentPortfolioId);
                } else {
                    alert('Sync failed: ' + result.message);
                }
            }
            
            // Load on page load
            loadPortfolios();
        </script>
    </body>
    </html>
    '''


# ============================================================================
# PANDAS DATAFRAME EXPORT
# ============================================================================

class DataFrameExporter:
    """Export portfolio data to Pandas DataFrames for analysis"""
    
    @staticmethod
    def positions_to_df(positions: List[Dict]) -> pd.DataFrame:
        """Convert positions to DataFrame"""
        return pd.DataFrame(positions)
    
    @staticmethod
    def trades_to_df(trades: List[Dict]) -> pd.DataFrame:
        """Convert trades to DataFrame"""
        df = pd.DataFrame(trades)
        if not df.empty:
            df['opened_at'] = pd.to_datetime(df['opened_at'])
            if 'closed_at' in df.columns:
                df['closed_at'] = pd.to_datetime(df['closed_at'])
        return df
    
    @staticmethod
    def export_to_csv(positions: List[Dict], trades: List[Dict], 
                     output_dir: str = '.'):
        """Export to CSV files"""
        pos_df = DataFrameExporter.positions_to_df(positions)
        trades_df = DataFrameExporter.trades_to_df(trades)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        pos_file = f"{output_dir}/positions_{timestamp}.csv"
        trades_file = f"{output_dir}/trades_{timestamp}.csv"
        
        pos_df.to_csv(pos_file, index=False)
        trades_df.to_csv(trades_file, index=False)
        
        return pos_file, trades_file


# Example usage
if __name__ == "__main__":
    # Google Sheets Export Example
    # exporter = GoogleSheetsExporter('path/to/credentials.json')
    # url = exporter.export_portfolio(summary, positions, trades, 'My Portfolio')
    # print(f"View in Google Sheets: {url}")
    
    # Web UI Example
    # ui = PortfolioWebUI(service)
    # ui.run()
    
    # CSV Export Example
    # DataFrameExporter.export_to_csv(positions, trades, './exports')
    
    print("UI and Export modules ready!")