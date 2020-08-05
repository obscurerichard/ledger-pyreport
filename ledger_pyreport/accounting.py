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
from datetime import timedelta
from decimal import Decimal
import math

from .model import *

# Generate a trial balance
# Perform closing of books based on specified dates
def trial_balance_raw(ledger, date, pstart, label=None):
	tb = TrialBalance(ledger, date, pstart, label=label)
	
	for transaction in ledger.transactions:
		if transaction.date > date:
			continue
		
		for posting in transaction.postings:
			if (posting.account.is_income or posting.account.is_expense) and transaction.date < pstart:
				tb.balances[config['retained_earnings']] = tb.get_balance(ledger.get_account(config['retained_earnings'])) + posting.amount
			elif posting.account.is_oci and transaction.date < pstart:
				tb.balances[config['accumulated_oci']] = tb.get_balance(ledger.get_account(config['retained_earnings'])) + posting.amount
			else:
				tb.balances[posting.account.name] = tb.get_balance(posting.account) + posting.amount
	
	return tb

# Trial balance with unrealized gains and OCI
def trial_balance(ledger, date, pstart, commodity, label=None):
	tb_date, r_date = _add_unrealized_gains(trial_balance_raw(ledger, date, pstart, label=label), commodity)
	tb_pstart, r_pstart = _add_unrealized_gains(trial_balance_raw(ledger, pstart - timedelta(days=1), pstart), commodity)
	
	for account in set(list(r_date.keys()) + list(r_pstart.keys())):
		if account in r_pstart:
			for trn in r_pstart[account]:
				# Update/accumulate trial balances
				tb_date.balances[account.name] = tb_date.get_balance(account) + trn.postings[0].amount
				
				if trn.postings[1].account.is_income or trn.postings[1].account.is_expense:
					tb_date.balances[config['retained_earnings']] = tb_date.get_balance(ledger.get_account(config['retained_earnings'])) - trn.postings[0].amount
				elif trn.postings[1].account.is_oci:
					tb_date.balances[config['accumulated_oci']] = tb_date.get_balance(ledger.get_account(config['accumulated_oci'])) - trn.postings[0].amount
				else:
					tb_date.balances[trn.postings[1].account.name] = tb_date.get_balance(trn.postings[1].account) - trn.postings[0].amount
				
				# Reversing entry
				trn_reversal = trn.reverse(None, pstart, '<Reversal of {}>'.format(trn.description[1:-1]))
				ledger.transactions.insert(0, trn_reversal)
				
				tb_date.balances[account.name] = tb_date.get_balance(account) + trn_reversal.postings[0].amount
				tb_date.balances[trn_reversal.postings[1].account.name] = tb_date.get_balance(trn_reversal.postings[1].account) - trn_reversal.postings[0].amount
		
		if account in r_date:
			for trn in r_date[account]:
				# Update trial balances
				tb_date.balances[account.name] = tb_date.get_balance(account) + trn.postings[0].amount
				tb_date.balances[trn.postings[1].account.name] = tb_date.get_balance(trn.postings[1].account) - trn.postings[0].amount
	
	return tb_date

# Adjust (in place) a trial balance for unrealized gains without accumulating OCI
def _add_unrealized_gains(tb, commodity):
	results = {}
	unrealized_gain_account = tb.ledger.get_account(config['unrealized_gains'][0])
	unrealized_loss_account = tb.ledger.get_account(config['unrealized_gains'][1])
	
	for account in list(tb.ledger.accounts.values()):
		if not account.is_market:
			continue
		
		unrealized_gain = Amount(0, commodity)
		unrealized_loss = Amount(0, commodity)
		
		for amount in tb.get_balance(account).amounts:
			amt_cost = amount.exchange(commodity, True)
			amt_market = amount.exchange(commodity, False, date=tb.date, ledger=tb.ledger)
			amt_gain = amt_market - amt_cost
			
			if amt_gain > 0:
				unrealized_gain += amt_gain
			if amt_gain < 0:
				unrealized_loss += amt_gain
		
		if unrealized_gain != 0:
			transaction = Transaction(tb.ledger, None, tb.date, '<Unrealized Gains>')
			transaction.postings.append(Posting(transaction, account, unrealized_gain))
			transaction.postings.append(Posting(transaction, unrealized_gain_account, -unrealized_gain))
			tb.ledger.transactions.append(transaction)
			
			results[account] = results.get(account, []) + [transaction]
		
		if unrealized_loss != 0:
			transaction = Transaction(tb.ledger, None, tb.date, '<Unrealized Losses>')
			transaction.postings.append(Posting(transaction, account, unrealized_loss))
			transaction.postings.append(Posting(transaction, unrealized_loss_account, -unrealized_loss))
			tb.ledger.transactions.append(transaction)
			
			results[account] = results.get(account, []) + [transaction]
	
	return tb, results

# Adjust (in place) a trial balance to include a Current Year Earnings account
# Suitable for display on a balance sheet
def balance_sheet(tb):
	# Calculate Profit/Loss
	total_pandl = tb.get_total(tb.ledger.get_account(config['income_account'])) + tb.get_total(tb.ledger.get_account(config['expenses_account']))
	
	# Add Current Year Earnings account
	tb.balances[config['current_year_earnings']] = tb.get_balance(tb.ledger.get_account(config['current_year_earnings'])) + total_pandl
	
	# Calculate OCI
	total_oci = tb.get_total(tb.ledger.get_account(config['oci_account']))
	
	# Add Current Year OCI account
	tb.balances[config['current_year_oci']] = tb.get_balance(tb.ledger.get_account(config['current_year_oci'])) + total_oci
	
	return tb

def account_to_cash(account, commodity):
	raise Exception('Not implemented')

# Adjust (in place) a ledger to convert accounting to a cash basis
def ledger_to_cash(ledger, commodity):
	for account in list(ledger.accounts.values()):
		if not (account.is_cash or account.is_income or account.is_expense or account.is_equity):
			account_to_cash(account, commodity)
	
	return ledger

# Summarise related transactions
def account_flows(ledger, date, pstart, accounts, related, label=None):
	transactions = [t for t in ledger.transactions if any(p.account in accounts for p in t.postings) and t.date <= date and t.date >= pstart]
	
	tb = TrialBalance(ledger, date, pstart, label=label)
	
	for transaction in transactions:
		for posting in transaction.postings:
			if (posting.account in accounts) is related:
				continue
			
			tb.balances[posting.account.name] = tb.get_balance(posting.account) - posting.amount
	
	return tb
