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
	
	# Get trial balance
	accounts = ledger.trial_balance(date, pstart)
	
	total_dr = sum(a.balance for a in accounts if a.balance > 0)
	total_cr = -sum(a.balance for a in accounts if a.balance < 0)
	
	return flask.render_template('trial.html', date=date, accounts=accounts, total_dr=total_dr, total_cr=total_cr)

@app.route('/balance')
def balance():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	
	# Get trial balance
	accounts = ledger.trial_balance(date, pstart)
	accounts_map = ledger.make_account_tree(accounts)
	
	# Calculate Profit/Loss
	total_pandl = accounts_map[ledger.config['income_account']].total() + accounts_map[ledger.config['expenses_account']].total()
	
	# Add Current Year Earnings account
	accounts.append(ledger.Account(ledger.config['current_year_earnings'], total_pandl))
	accounts_map = ledger.make_account_tree(accounts)
	
	return flask.render_template('balance.html', date=date, assets=accounts_map[ledger.config['assets_account']], liabilities=accounts_map[ledger.config['liabilities_account']], equity=accounts_map[ledger.config['equity_account']])

@app.route('/pandl')
def pandl():
	date_beg = datetime.strptime(flask.request.args['date_beg'], '%Y-%m-%d')
	date_end = datetime.strptime(flask.request.args['date_end'], '%Y-%m-%d')
	
	# Get P&L
	accounts = ledger.parse_balance(ledger.run_ledger('--begin', date_beg.strftime('%Y-%m-%d'), '--end', (date_end + timedelta(days=1)).strftime('%Y-%m-%d'), 'balance', '--balance-format', ledger.BALANCE_FORMAT, '--no-total', '--flat', '--cost', ledger.aregex(ledger.config['income_account']), ledger.aregex(ledger.config['expenses_account'])))
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
