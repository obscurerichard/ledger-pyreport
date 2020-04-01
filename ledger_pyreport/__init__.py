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
from .config import config
from .model import *

from datetime import datetime, timedelta
from decimal import Decimal
import flask
import itertools

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
	cash = flask.request.args.get('cash', False)
	
	report_currency = Currency(*config['report_currency'])
	
	if compare == 0:
		# Get trial balance
		l = ledger.raw_transactions_at_date(date)
		if cash:
			l = accounting.ledger_to_cash(l, report_currency)
		trial_balance = accounting.trial_balance(l, date, pstart)
		
		trial_balance = accounting.add_unrealized_gains(trial_balance, report_currency)
		
		total_dr = Amount(0, report_currency)
		total_cr = Amount(0, report_currency)
		
		for account in l.accounts.values():
			# Display in "cost basis" as we have already accounted for unrealised gains
			balance = trial_balance.get_balance(account).exchange(report_currency, True)
			if balance > 0:
				total_dr += balance
			else:
				total_cr -= balance
		
		return flask.render_template('trial.html', date=date, pstart=pstart, trial_balance=trial_balance, accounts=sorted(l.accounts.values(), key=lambda a: a.name), total_dr=total_dr, total_cr=total_cr, report_currency=report_currency)
	else:
		# Get multiple trial balances for comparison
		dates = [date.replace(year=date.year - i) for i in range(0, compare + 1)]
		pstarts = [pstart.replace(year=pstart.year - i) for i in range(0, compare + 1)]
		
		l = ledger.raw_transactions_at_date(date)
		if cash:
			l = accounting.ledger_to_cash(l, report_currency)
		trial_balances = [accounting.add_unrealized_gains(accounting.trial_balance(l, d, p), report_currency) for d, p in zip(dates, pstarts)]
		
		# Delete accounts with always zero balances
		accounts = sorted(l.accounts.values(), key=lambda a: a.name)
		for account in accounts[:]:
			if all(t.get_balance(account).exchange(report_currency, True).near_zero for t in trial_balances):
				accounts.remove(account)
		
		return flask.render_template('trial_multiple.html', trial_balances=trial_balances, accounts=accounts, report_currency=report_currency, cash=cash)

@app.route('/balance')
def balance():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	compare = int(flask.request.args['compare'])
	cash = flask.request.args.get('cash', False)
	
	dates = [date.replace(year=date.year - i) for i in range(0, compare + 1)]
	pstarts = [pstart.replace(year=pstart.year - i) for i in range(0, compare + 1)]
	
	report_currency = Currency(*config['report_currency'])
	l = ledger.raw_transactions_at_date(date)
	if cash:
		l = accounting.ledger_to_cash(l, report_currency)
	balance_sheets = [accounting.balance_sheet(accounting.add_unrealized_gains(accounting.trial_balance(l, d, p), report_currency)) for d, p in zip(dates, pstarts)]
	
	# Delete accounts with always zero balances
	accounts = list(l.accounts.values())
	for account in accounts[:]:
		if all(b.get_balance(account).exchange(report_currency, True).near_zero and b.get_total(account).exchange(report_currency, True).near_zero for b in balance_sheets):
			accounts.remove(account)
	
	return flask.render_template('balance.html', ledger=l, balance_sheets=balance_sheets, accounts=accounts, config=config, report_currency=report_currency, cash=cash)

def describe_period(date_end, date_beg):
	if date_end == (date_beg.replace(year=date_beg.year + 1) - timedelta(days=1)):
		return 'year ended {}'.format(date_end.strftime('%d %B %Y'))
	elif date_beg == ledger.financial_year(date_end):
		return 'financial year to {}'.format(date_end.strftime('%d %B %Y'))
	else:
		return 'period from {} to {}'.format(date_beg.strftime('%d %B %Y'), date_end.strftime('%d %B %Y'))

@app.route('/pandl')
def pandl():
	date_beg = datetime.strptime(flask.request.args['date_beg'], '%Y-%m-%d')
	date_end = datetime.strptime(flask.request.args['date_end'], '%Y-%m-%d')
	compare = int(flask.request.args['compare'])
	cash = flask.request.args.get('cash', False)
	
	dates_beg = [date_beg.replace(year=date_beg.year - i) for i in range(0, compare + 1)]
	dates_end = [date_end.replace(year=date_end.year - i) for i in range(0, compare + 1)]
	
	report_currency = Currency(*config['report_currency'])
	l = ledger.raw_transactions_at_date(date_end)
	if cash:
		l = accounting.ledger_to_cash(l, report_currency)
	pandls = [accounting.trial_balance(l, de, db) for de, db in zip(dates_end, dates_beg)]
	
	# Delete accounts with always zero balances
	accounts = list(l.accounts.values())
	for account in accounts[:]:
		if all(p.get_balance(account) == 0 and p.get_total(account) == 0 for p in pandls):
			accounts.remove(account)
	
	return flask.render_template('pandl.html', period=describe_period(date_end, date_beg), ledger=l, pandls=pandls, accounts=accounts, config=config, report_currency=report_currency, cash=cash)

@app.route('/transactions')
def transactions():
	date_beg = datetime.strptime(flask.request.args['date_beg'], '%Y-%m-%d')
	date_end = datetime.strptime(flask.request.args['date_end'], '%Y-%m-%d')
	account = flask.request.args.get('account', None)
	cash = flask.request.args.get('cash', False)
	commodity = flask.request.args.get('commodity', False)
	
	report_currency = Currency(*config['report_currency'])
	
	# General ledger
	l = ledger.raw_transactions_at_date(date_end)
	if cash:
		l = accounting.ledger_to_cash(l, report_currency)
	
	# Unrealized gains
	l = accounting.add_unrealized_gains(accounting.trial_balance(l, date_end, date_beg), report_currency).ledger
	
	if not account:
		# General Ledger
		transactions = [t for t in l.transactions if t.date <= date_end and t.date >= date_beg]
		
		total_dr = sum((p.amount for t in transactions for p in t.postings if p.amount > 0), Balance()).exchange(report_currency, True)
		total_cr = sum((p.amount for t in transactions for p in t.postings if p.amount < 0), Balance()).exchange(report_currency, True)
		
		return flask.render_template('transactions.html', date_beg=date_beg, date_end=date_end, period=describe_period(date_end, date_beg), account=None, ledger=l, transactions=transactions, total_dr=total_dr, total_cr=total_cr, report_currency=report_currency, cash=cash)
	elif commodity:
		# Account Transactions with commodity detail
		account = l.get_account(account)
		transactions = [t for t in l.transactions if t.date <= date_end and t.date >= date_beg and any(p.account == account for p in t.postings)]
		
		opening_balance = accounting.trial_balance(l, date_beg - timedelta(days=1), date_beg).get_balance(account).clean()
		closing_balance = accounting.trial_balance(l, date_end, date_beg).get_balance(account).clean()
		
		def matching_posting(transaction, amount):
			return next((p for p in transaction.postings if p.account == account and p.amount.currency == amount.currency), None)
		
		return flask.render_template('transactions_commodity.html', date_beg=date_beg, date_end=date_end, period=describe_period(date_end, date_beg), account=account, ledger=l, transactions=transactions, opening_balance=opening_balance, closing_balance=closing_balance, report_currency=report_currency, cash=cash, timedelta=timedelta, matching_posting=matching_posting)
	else:
		# Account Transactions
		account = l.get_account(account)
		transactions = [t for t in l.transactions if t.date <= date_end and t.date >= date_beg and any(p.account == account for p in t.postings)]
		
		opening_balance = accounting.trial_balance(l, date_beg - timedelta(days=1), date_beg).get_balance(account).exchange(report_currency, True)
		closing_balance = accounting.trial_balance(l, date_end, date_beg).get_balance(account).exchange(report_currency, True)
		
		return flask.render_template('transactions.html', date_beg=date_beg, date_end=date_end, period=describe_period(date_end, date_beg), account=account, ledger=l, transactions=transactions, opening_balance=opening_balance, closing_balance=closing_balance, report_currency=report_currency, cash=cash, timedelta=timedelta)

@app.route('/transaction')
def transaction():
	tid = flask.request.args['tid']
	cash = flask.request.args.get('cash', False)
	commodity = flask.request.args.get('commodity', False)
	
	report_currency = Currency(*config['report_currency'])
	
	# General ledger
	l = ledger.raw_transactions_at_date(None)
	if cash:
		l = accounting.ledger_to_cash(l, report_currency)
	
	transaction = next((t for t in l.transactions if str(t.id) == tid))
	
	if commodity:
		total_dr = sum((p.amount for p in transaction.postings if p.amount > 0), Balance()).clean()
		total_cr = sum((p.amount for p in transaction.postings if p.amount < 0), Balance()).clean()
		totals = itertools.zip_longest(total_dr.amounts, total_cr.amounts)
		return flask.render_template('transaction_commodity.html', ledger=l, transaction=transaction, totals=totals, total_dr=total_dr.exchange(report_currency, True), total_cr=total_cr.exchange(report_currency, True), report_currency=report_currency, cash=cash)
	else:
		total_dr = sum((p.amount for p in transaction.postings if p.amount > 0), Balance()).exchange(report_currency, True)
		total_cr = sum((p.amount for p in transaction.postings if p.amount < 0), Balance()).exchange(report_currency, True)
		return flask.render_template('transaction.html', ledger=l, transaction=transaction, total_dr=total_dr, total_cr=total_cr, report_currency=report_currency, cash=cash)

# Template filters

@app.template_filter('a')
def filter_amount(amt, link=None):
	if amt.near_zero:
		amt_str = '0.00'
		is_pos = True
	elif amt >= 0:
		amt_str = '{:,.2f}'.format(amt.amount).replace(',', '&#8239;') # Narrow no-break space
		is_pos = True
	else:
		amt_str = '{:,.2f}'.format(-amt.amount).replace(',', '&#8239;')
		is_pos = False
	
	if link:
		if is_pos:
			return flask.Markup('<a href="{}"><span title="{}">{}</span></a>&nbsp;'.format(link, amt.tostr(False), amt_str))
		else:
			return flask.Markup('<a href="{}"><span title="{}">({})</span></a>'.format(link, amt.tostr(False), amt_str))
	else:
		if is_pos:
			return flask.Markup('<span title="{}">{}</span>&nbsp;'.format(amt.tostr(False), amt_str))
		else:
			return flask.Markup('<span title="{}">({})</span>'.format(amt.tostr(False), amt_str))

@app.template_filter('b')
def filter_amount_positive(amt):
	return flask.Markup('<span title="{}">{:,.2f}</span>'.format(amt.tostr(False), amt.amount).replace(',', '&#8239;'))

@app.template_filter('bc')
def filter_currency_positive(amt):
	if amt.currency.is_prefix:
		return flask.Markup('<span title="{}">{}{:,.2f}</span>'.format(amt.tostr(False), amt.currency.name, amt.amount).replace(',', '&#8239;'))
	else:
		return flask.Markup('<span title="{}">{:,.2f} {}</span>'.format(amt.tostr(False), amt.amount, amt.currency.name).replace(',', '&#8239;'))

@app.template_filter('bt')
def filter_currency_table_positive(amt, show_price, link=None):
	result = []
	if amt.currency.is_prefix:
		amt_str = filter_currency_positive(amt)
		cur_str = ''
	else:
		amt_str = '{:,.2f}'.format(amt.amount).replace(',', '&#8239;')
		cur_str = amt.currency.name
	
	amt_full = amt.tostr(False)
	
	result.append('<td style="text-align: right;"><a href="{}"><span title="{}">{}</span></a></td>'.format(link, amt_full, amt_str) if link else '<td style="text-align: right;"><span title="{}">{}</span></td>'.format(amt_full, amt_str))
	result.append('<td><span title="{}">{}</span></td>'.format(amt_full, cur_str))
	
	if show_price:
		if amt.currency.price:
			result.append('<td><span title="{}">{{{}}}</span></td>'.format(amt_full, filter_currency_positive(amt.currency.price)))
		else:
			result.append('<td></td>')
	
	return flask.Markup(''.join(result))

# Debug views

@app.route('/debug/noncash_transactions')
def debug_noncash_transactions():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	account = flask.request.args.get('account')
	
	report_currency = Currency(*config['report_currency'])
	
	l = ledger.raw_transactions_at_date(date)
	account = l.get_account(account)
	
	transactions = [t for t in l.transactions if any(p.account == account for p in t.postings)]
	
	accounting.account_to_cash(account, report_currency)
	
	return flask.render_template('debug_noncash_transactions.html', date=date, pstart=pstart, period=describe_period(date, pstart), account=account, ledger=l, transactions=transactions, report_currency=report_currency)

@app.route('/debug/imbalances')
def debug_imbalances():
	date = datetime.strptime(flask.request.args['date'], '%Y-%m-%d')
	pstart = datetime.strptime(flask.request.args['pstart'], '%Y-%m-%d')
	cash = flask.request.args.get('cash', False)
	
	report_currency = Currency(*config['report_currency'])
	
	l = ledger.raw_transactions_at_date(date)
	if cash:
		l = accounting.ledger_to_cash(l, report_currency)
	
	transactions = [t for t in l.transactions if t.date <= date and t.date >= pstart and not sum((p.amount for p in t.postings), Balance()).exchange(report_currency, True).near_zero]
	
	total_dr = sum((p.amount for t in transactions for p in t.postings if p.amount > 0), Balance()).exchange(report_currency, True)
	total_cr = sum((p.amount for t in transactions for p in t.postings if p.amount < 0), Balance()).exchange(report_currency, True)
	
	return flask.render_template('transactions.html', date=date, pstart=pstart, period=describe_period(date, pstart), account=None, ledger=l, transactions=transactions, total_dr=total_dr, total_cr=total_cr, report_currency=report_currency, cash=cash)
