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
import re
import subprocess
import yaml

# Load config
with open('config.yml', 'r') as f:
	config = yaml.safe_load(f)

# Helper commands to run Ledger

def run_ledger(*args):
	proc = subprocess.Popen(['ledger', '--args-only', '--file', config['ledger_file'], '-X', config['report_currency'], '--unround'] + config['ledger_args'] + list(args), encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = proc.communicate()
	
	if stderr:
		raise Exception(stderr)
	
	return stdout

def run_ledger_date(date, *args):
	return run_ledger('--end', (date + timedelta(days=1)).strftime('%Y-%m-%d'), *args)

# General financial logic

def financial_year(date):
	pstart = date.replace(day=1, month=7)
	if pstart > date:
		pstart = pstart.replace(year=pstart.year - 1)
	return pstart

# Ledger logic

class Account:
	def __init__(self, name):
		if not isinstance(name, str):
			raise Exception('Account name must be a string')
		
		self.name = name
		
		self.parent = None
		self.children = []
	
	def __repr__(self):
		return '<Account "{}">'.format(self.name)
	
	@property
	def bits(self):
		return self.name.split(':')
	
	def matches(self, needle):
		if self.name == needle or self.name.startswith(needle + ':'):
			return True
		return False
	
	def insert_into_tree(self, accounts):
		if ':' in self.name:
			parent_name = self.name[:self.name.rindex(':')]
			if parent_name not in accounts:
				parent = Account(parent_name)
				accounts[parent_name] = parent
				parent.insert_into_tree(accounts)
			
			self.parent = accounts[parent_name]
			if self not in self.parent.children:
				self.parent.children.append(self)
	
	@property
	def is_asset(self):
		return self.matches(config['assets_account'])
	@property
	def is_liability(self):
		return self.matches(config['liabilities_account'])
	@property
	def is_equity(self):
		return self.matches(config['equity_account'])
	@property
	def is_income(self):
		return self.matches(config['income_account'])
	@property
	def is_expense(self):
		return self.matches(config['expenses_account'])
	
	#def get_balance(self, date, is_market=None):
	#	if is_market is None:
	#		if self.is_income or self.is_expense:
	#			basis = '--cost'
	#		else:
	#			basis = '--market'
	#	elif is_market == True:
	#		basis = '--market'
	#	else:
	#		basis = '--cost'
	#	
	#	output = run_ledger_date(date, 'balance', '--balance-format', '%(display_total)', '--no-total', '--flat', '--empty', basis, '--limit', 'account=~/^{}$/'.format(re.escape(self.name).replace('/', '\\/')))
	#	
	#	return parse_amount(output)

class Snapshot:
	def __init__(self):
		self.accounts = {}
		self.balances = {}
	
	def get_account(self, account_name):
		if account_name not in self.accounts:
			account = Account(account_name)
			self.accounts[account_name] = account
			account.insert_into_tree(self.accounts)
		
		return self.accounts[account_name]
	
	def set_balance(self, account_name, balance):
		if account_name not in self.accounts:
			account = Account(account_name)
			self.accounts[account_name] = account
			account.insert_into_tree(self.accounts)
		
		if account_name not in self.balances:
			self.balances[account_name] = Decimal(0)
		
		self.balances[account_name] = balance
	
	def get_balance(self, account_name):
		if account_name not in self.accounts:
			self.set_balance(account_name, Decimal(0))
		
		if account_name not in self.balances:
			self.balances[account_name] = Decimal(0)
		
		return self.balances[account_name]
	
	def get_total(self, account_name):
		return self.get_balance(account_name) + sum(self.get_total(c.name) for c in self.accounts[account_name].children)

def parse_amount(amount):
	if amount == '' or amount == '0':
		return Decimal(0)
	if not amount.startswith(config['report_currency']):
		raise Exception('Unexpected currency returned by ledger: {}'.format(amount))
	return Decimal(amount[len(config['report_currency']):])

def get_accounts():
	output = run_ledger('balance', '--balance-format', '%(account)\n', '--no-total', '--flat', '--empty')
	account_names = output.rstrip('\n').split('\n')
	
	accounts = {n: Account(n) for n in account_names}
	
	for account in list(accounts.values()):
		account.insert_into_tree(accounts)
	
	return accounts

# Raw Ledger output, unlikely to balance
def get_raw_snapshot(date, basis=None):
	snapshot = Snapshot()
	
	# Get balances from Ledger
	output = (
		run_ledger_date(date, 'balance', '--balance-format', '%(quoted(account)),%(quoted(display_total))\n', '--no-total', '--flat', '--empty', basis if basis is not None else '--market', config['assets_account'], config['liabilities_account'], config['equity_account']) +
		run_ledger_date(date, 'balance', '--balance-format', '%(quoted(account)),%(quoted(display_total))\n', '--no-total', '--flat', '--empty', basis if basis is not None else '--cost', config['income_account'], config['expenses_account'])
	)
	reader = csv.reader(output.splitlines())
	for row in reader:
		snapshot.set_balance(row[0], parse_amount(row[1]))
	
	return snapshot

# Ledger output, adjusted for Unrealized Gains
def get_snapshot(date):
	snapshot_cost = get_raw_snapshot(date, '--cost')
	snapshot = get_raw_snapshot(date)
	
	market_total = Decimal(0)
	cost_total = Decimal(0)
	
	# Calculate unrealized gains
	for account in snapshot.accounts.values():
		if account.is_asset or account.is_liability:
			market_total += snapshot.get_balance(account.name)
			cost_total += snapshot_cost.get_balance(account.name)
	
	# Add Unrealized Gains account
	unrealized_gains_amt = market_total - cost_total
	snapshot.set_balance(config['unrealized_gains'], snapshot.get_balance(config['unrealized_gains']) - unrealized_gains_amt)
	
	return snapshot

# Ledger output, simulating closing of books
def trial_balance(date, pstart):
	# Get balances at period start
	snapshot_pstart = get_snapshot(pstart)
	
	# Get balances at date
	snapshot = get_snapshot(date)
	
	# Calculate Retained Earnings, and adjust income/expense accounts
	total_pandl = Decimal(0)
	for account in snapshot_pstart.accounts.values():
		if account.is_income or account.is_expense:
			total_pandl += snapshot_pstart.get_balance(account.name)
	
	# Add Retained Earnings account
	snapshot.set_balance(config['retained_earnings'], snapshot.get_balance(config['retained_earnings']) + total_pandl)
	
	# Adjust income/expense accounts
	for account in snapshot.accounts.values():
		if account.is_income or account.is_expense:
			snapshot.set_balance(account.name, snapshot.get_balance(account.name) - snapshot_pstart.get_balance(account.name))
	
	return snapshot
