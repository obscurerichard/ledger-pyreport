#   ledger-pyreport
#   Copyright © 2020  Lee Yingtong Li (RunasSudo)
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

from . import ledger

from datetime import datetime, timedelta
import flask

app = flask.Flask(__name__, template_folder='jinja2')

@app.route('/')
def index():
	date = datetime.now()
	pstart = ledger.financial_year(date)
	
	return flask.render_template('index.html', date=date, pstart=pstart)

@app.route('/trial')
def trial():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	cash = flask.request.args.get('cash', False)
	
	# Get trial balance
	accounts = ledger.trial_balance(date, pstart, cash)
	
	total_dr = sum(a.balance for a in accounts if a.balance > 0)
	total_cr = -sum(a.balance for a in accounts if a.balance < 0)
	
	return flask.render_template('trial.html', date=date, accounts=accounts, total_dr=total_dr, total_cr=total_cr)

@app.route('/balance')
def balance():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	cash = flask.request.args.get('cash', False)
	
	# Get trial balance
	accounts = ledger.trial_balance(date, pstart, cash)
	accounts_map = ledger.make_account_tree(accounts)
	
	# Calculate Profit/Loss
	total_pandl = accounts_map[ledger.config['income_account']].total() + accounts_map[ledger.config['expenses_account']].total()
	
	# Add Current Year Earnings account
	accounts.append(ledger.Account(ledger.config['current_year_earnings'], total_pandl))
	accounts_map = ledger.make_account_tree(accounts)
	
	return flask.render_template('balance.html', date=date, cash=cash, assets=accounts_map.get(ledger.config['assets_account'], ledger.Account('Assets')), liabilities=accounts_map.get(ledger.config['liabilities_account'], ledger.Account('Liabilities')), equity=accounts_map.get(ledger.config['equity_account'], ledger.Account('Equity')))

@app.route('/pandl')
def pandl():
	date_beg = datetime.strptime(flask.request.args['date_beg'], '%Y-%m-%d')
	date_end = datetime.strptime(flask.request.args['date_end'], '%Y-%m-%d')
	cash = flask.request.args.get('cash', False)
	
	# Get P&L
	accounts = ledger.pandl(date_beg, date_end, cash)
	accounts_map = ledger.make_account_tree(accounts)
	
	if date_end == (date_beg.replace(year=date_beg.year + 1) - timedelta(days=1)):
		period = 'year ended {}'.format(date_end.strftime('%d %B %Y'))
	elif date_beg == ledger.financial_year(date_end):
		period = 'financial year to {}'.format(date_end.strftime('%d %B %Y'))
	else:
		period = 'period from {} to {}'.format(date_begin.strftime('%d %B %Y'), date_end.strftime('%d %B %Y'))
	
	return flask.render_template('pandl.html', period=period, income=accounts_map[ledger.config['income_account']], expenses=accounts_map[ledger.config['expenses_account']])

@app.template_filter('a')
def filter_amount(amt):
	if amt > 0:
		return flask.Markup('{:,.2f}&nbsp;'.format(amt).replace(',', '&#8239;')) # Narrow no-break space
	else:
		return flask.Markup('({:,.2f})'.format(-amt).replace(',', '&#8239;'))

@app.template_filter('b')
def filter_amount_positive(amt):
	return flask.Markup('{:,.2f}'.format(amt).replace(',', '&#8239;'))
