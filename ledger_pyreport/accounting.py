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

import csv
from decimal import Decimal

from .model import *

def trial_balance(ledger, date, pstart):
	tb = TrialBalance(ledger, date, pstart)
	
	for transaction in ledger.transactions:
		if transaction.date > date:
			continue
		
		for posting in transaction.postings:
			if (posting.account.is_income or posting.account.is_expense) and transaction.date < pstart:
				tb.balances[config['retained_earnings']] = tb.get_balance(ledger.get_account(config['retained_earnings'])) + posting.amount
			else:
				tb.balances[posting.account.name] = tb.get_balance(posting.account) + posting.amount
	
	return tb

def add_unrealized_gains(tb, currency):
	for account in list(tb.ledger.accounts.values()):
		if not account.is_market:
			continue
		
		total_cost = tb.get_balance(account).exchange(currency, True)
		total_market = tb.get_balance(account).exchange(currency, False, tb.date, tb.ledger)
		unrealized_gain = total_market - total_cost
		
		if unrealized_gain != 0:
			transaction = Transaction(tb.ledger, None, tb.date, '<Unrealized Gains>')
			transaction.postings.append(Posting(transaction, account, unrealized_gain))
			transaction.postings.append(Posting(transaction, tb.ledger.get_account(config['unrealized_gains']), -unrealized_gain))
			tb.ledger.transactions.append(transaction)
	
	return trial_balance(tb.ledger, tb.date, tb.pstart)

def balance_sheet(tb):
	# Calculate Profit/Loss
	total_pandl = tb.get_total(tb.ledger.get_account(config['income_account'])) + tb.get_total(tb.ledger.get_account(config['expenses_account']))
	
	# Add Current Year Earnings account
	tb.balances[config['current_year_earnings']] = tb.get_balance(tb.ledger.get_account(config['current_year_earnings'])) + total_pandl
	
	return tb
