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

# Generate a trial balance
# Perform closing of books based on specified dates
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

# Adjust (in place) a trial balance for unrealized gains
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

# Adjust (in place) a trial balance to include a Current Year Earnings account
# Suitable for display on a balance sheet
def balance_sheet(tb):
	# Calculate Profit/Loss
	total_pandl = tb.get_total(tb.ledger.get_account(config['income_account'])) + tb.get_total(tb.ledger.get_account(config['expenses_account']))
	
	# Add Current Year Earnings account
	tb.balances[config['current_year_earnings']] = tb.get_balance(tb.ledger.get_account(config['current_year_earnings'])) + total_pandl
	
	return tb

# Adjust (in place) a ledger to convert accounting to a cash basis
def cash_basis(ledger, currency):
	for transaction in ledger.transactions:
		non_cash_postings = [p for p in transaction.postings if not (p.account.is_cash or p.account.is_income or p.account.is_expense or p.account.is_equity)]
		
		if non_cash_postings:
			# We have liabilities or non-cash assets which need to be excluded
			
			cash_postings = [p for p in transaction.postings if p.account.is_income or p.account.is_expense or p.account.is_equity]
			cash_total = sum((p.amount for p in cash_postings), Balance()).exchange(currency, True).amount
			
			if cash_postings:
				for posting in non_cash_postings:
					posting_amount = posting.amount.exchange(currency, True).amount
					for posting_xfer in cash_postings:
						posting_xfer_amount = posting_xfer.amount.exchange(currency, True).amount
						transaction.postings.append(Posting(transaction, posting_xfer.account, Amount(posting_amount * posting_xfer_amount / cash_total, currency)))
					
					transaction.postings.remove(posting)
			else:
				for posting in non_cash_postings:
					posting.account = ledger.get_account(config['cash_other_income'])
	
	return ledger
