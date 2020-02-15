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

from . import accounting
from . import ledger

from datetime import datetime, timedelta
from decimal import Decimal
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
	compare = int(flask.request.args['compare'])
	#cash = flask.request.args.get('cash', False)
	
	if compare == 0:
		# Get trial balance
		trial_balance = ledger.trial_balance(date, pstart)
		
		total_dr = Decimal(0)
		total_cr = Decimal(0)
		
		for account in trial_balance.accounts.values():
			balance = trial_balance.get_balance(account.name)
			if balance > 0:
				total_dr += balance
			else:
				total_cr -= balance
		
		return flask.render_template('trial.html', date=date, trial_balance=trial_balance, total_dr=total_dr, total_cr=total_cr)
	else:
		# Get multiple trial balances for comparison
		dates = [date.replace(year=date.year - i) for i in range(0, compare + 1)]
		pstarts = [pstart.replace(year=pstart.year - i) for i in range(0, compare + 1)]
		
		trial_balances = [ledger.trial_balance(d, p) for d, p in zip(dates, pstarts)]
		
		# Delete accounts with always zero balances
		accounts = list(trial_balances[0].accounts.values())
		for account in accounts[:]:
			if all(t.get_balance(account.name) == 0 for t in trial_balances):
				accounts.remove(account)
		
		return flask.render_template('trial_multiple.html', dates=dates, trial_balances=trial_balances, accounts=accounts)

@app.route('/balance')
def balance():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	compare = int(flask.request.args['compare'])
	#cash = flask.request.args.get('cash', False)
	
	dates = [date.replace(year=date.year - i) for i in range(0, compare + 1)]
	pstarts = [pstart.replace(year=pstart.year - i) for i in range(0, compare + 1)]
	
	balance_sheets = [accounting.balance_sheet(d, p) for d, p in zip(dates, pstarts)]
	
	# Delete accounts with always zero balances
	accounts = list(balance_sheets[0].accounts.values())
	for account in accounts[:]:
		if all(b.get_balance(account.name) == 0 and b.get_total(account.name) == 0 for b in balance_sheets):
			accounts.remove(account)
	
	return flask.render_template('balance.html', dates=dates, balance_sheets=balance_sheets, accounts=accounts, config=ledger.config)

@app.route('/pandl')
def pandl():
	date_beg = datetime.strptime(flask.request.args['date_beg'], '%Y-%m-%d')
	date_end = datetime.strptime(flask.request.args['date_end'], '%Y-%m-%d')
	compare = int(flask.request.args['compare'])
	#cash = flask.request.args.get('cash', False)
	
	dates_beg = [date_beg.replace(year=date_beg.year - i) for i in range(0, compare + 1)]
	dates_end = [date_end.replace(year=date_end.year - i) for i in range(0, compare + 1)]
	
	pandls = [ledger.trial_balance(de, db) for de, db in zip(dates_end, dates_beg)]
	
	# Delete accounts with always zero balances
	accounts = list(pandls[0].accounts.values())
	for account in accounts[:]:
		if all(p.get_balance(account.name) == 0 and p.get_total(account.name) == 0 for p in pandls):
			accounts.remove(account)
	
	if date_end == (date_beg.replace(year=date_beg.year + 1) - timedelta(days=1)):
		period = 'year ended {}'.format(date_end.strftime('%d %B %Y'))
	elif date_beg == ledger.financial_year(date_end):
		period = 'financial year to {}'.format(date_end.strftime('%d %B %Y'))
	else:
		period = 'period from {} to {}'.format(date_beg.strftime('%d %B %Y'), date_end.strftime('%d %B %Y'))
	
	return flask.render_template('pandl.html', period=period, dates_end=dates_end, pandls=pandls, accounts=accounts, config=ledger.config)

@app.template_filter('a')
def filter_amount(amt):
	if amt < 0.005 and amt >= -0.005:
		return flask.Markup('0.00&nbsp;')
	elif amt > 0:
		return flask.Markup('{:,.2f}&nbsp;'.format(amt).replace(',', '&#8239;')) # Narrow no-break space
	else:
		return flask.Markup('({:,.2f})'.format(-amt).replace(',', '&#8239;'))

@app.template_filter('b')
def filter_amount_positive(amt):
	return flask.Markup('{:,.2f}'.format(amt).replace(',', '&#8239;'))
