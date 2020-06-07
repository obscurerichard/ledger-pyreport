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
			tb_date.balances[account.name] = tb_date.get_balance(account) + r_pstart[account].postings[0].amount
			if r_pstart[account].postings[1].account.is_income or r_pstart[account].postings[1].account.is_expense:
				tb_date.balances[config['retained_earnings']] = tb_date.get_balance(ledger.get_account(config['retained_earnings'])) - r_pstart[account].postings[0].amount
			elif r_pstart[account].postings[1].account.is_oci:
				tb_date.balances[config['accumulated_oci']] = tb_date.get_balance(ledger.get_account(config['accumulated_oci'])) - r_pstart[account].postings[0].amount
			else:
				tb_date.balances[config['unrealized_gains']] = tb_date.get_balance(ledger.get_account(config['accumulated_oci'])) - r_pstart[account].postings[0].amount
			
			# Reversing entry
			trn_reversal = r_pstart[account].reverse(None, pstart, '<Reversal of Unrealized Gains>')
			ledger.transactions.insert(0, trn_reversal)
			
			tb_date.balances[account.name] = tb_date.get_balance(account) + trn_reversal.postings[0].amount
			tb_date.balances[config['unrealized_gains']] = tb_date.get_balance(ledger.get_account(config['unrealized_gains'])) - trn_reversal.postings[0].amount
		
		if account in r_date:
			tb_date.balances[account.name] = tb_date.get_balance(account) + r_date[account].postings[0].amount
			tb_date.balances[config['unrealized_gains']] = tb_date.get_balance(ledger.get_account(config['unrealized_gains'])) - r_date[account].postings[0].amount
	
	return tb_date

# Adjust (in place) a trial balance for unrealized gains without accumulating OCI
def _add_unrealized_gains(tb, commodity):
	results = {}
	unrealized_gain_account = tb.ledger.get_account(config['unrealized_gains'])
	
	for account in list(tb.ledger.accounts.values()):
		if not account.is_market:
			continue
		
		total_cost = tb.get_balance(account).exchange(commodity, True)
		total_market = tb.get_balance(account).exchange(commodity, False, tb.date, tb.ledger)
		unrealized_gain = total_market - total_cost
		
		if unrealized_gain != 0:
			transaction = Transaction(tb.ledger, None, tb.date, '<Unrealized Gains>')
			transaction.postings.append(Posting(transaction, account, unrealized_gain))
			transaction.postings.append(Posting(transaction, unrealized_gain_account, -unrealized_gain))
			tb.ledger.transactions.append(transaction)
			
			results[account] = transaction
	
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
	# Apply FIFO methodology to match postings
	balance = [] # list of [posting, amount to balance, amount remaining, balancing list of [posting, amount balanced]]
	
	for transaction in account.ledger.transactions[:]:
		if any(p.account == account for p in transaction.postings):
			for posting in transaction.postings[:]:
				if posting.account == account:
					#transaction.postings.remove(posting)
					pass
				else:
					# Try to balance postings
					amount_to_balance = posting.amount.exchange(commodity, True).amount
					
					while amount_to_balance != 0:
						balancing_posting = next((b for b in balance if b[2] != 0 and math.copysign(1, b[2]) != math.copysign(1, amount_to_balance)), None)
						if balancing_posting is None:
							break
						
						if abs(balancing_posting[2]) >= abs(amount_to_balance):
							balancing_posting[3].append([posting, amount_to_balance])
							balancing_posting[2] += amount_to_balance
							amount_to_balance = Decimal(0)
							break
						else:
							balancing_posting[3].append([posting, -balancing_posting[2]])
							amount_to_balance += balancing_posting[2]
							balancing_posting[2] = Decimal(0)
					
					if amount_to_balance != 0:
						# New unbalanced remainder
						balance.append([posting, amount_to_balance, amount_to_balance, []])
			
			transaction.postings = []
	
	# Finalise balanced postings
	for orig_posting, amount_to_balance, amount_remaining, balancing_postings in balance:
		posting = Posting(orig_posting.transaction, orig_posting.account, Amount(amount_to_balance, commodity))
		posting.transaction.postings.append(posting)
		
		for balancing_posting, amount_balanced in balancing_postings:
			posting.transaction.postings.append(Posting(posting.transaction, balancing_posting.account, Amount(amount_balanced, commodity)))
			
			if balancing_posting in balancing_posting.transaction.postings:
				balancing_posting.transaction.postings.remove(balancing_posting)
		
		if amount_remaining != 0:
			if posting.account.is_asset:
				# Cash - charge any unbalanced remainder to Other Income
				posting.transaction.postings.append(Posting(posting.transaction, account.ledger.get_account(config['cash_other_income']), Amount(-amount_remaining, commodity)))
			else:
				# Liabilities, etc. - discard any unbalanced remainder
				posting.amount.amount -= amount_remaining

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
