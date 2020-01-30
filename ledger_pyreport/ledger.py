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
import subprocess
import yaml

# Load config
with open('config.yml', 'r') as f:
	config = yaml.safe_load(f)

class Account:
	def __init__(self, name, balance):
		self.name = name
		self.balance = balance
		
		self.parent = None
		self.children = []
	
	@property
	def name_parts(self):
		return self.name.split(':')
	
	def total(self):
		result = self.balance
		for child in self.children:
			result += child.total()
		return result

def run_ledger(*args):
	proc = subprocess.Popen(['ledger', '--args-only', '--file', config['ledger_file'], '-X', config['report_currency'], '--unround'] + config['ledger_args'] + list(args), encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout, stderr = proc.communicate()
	
	if stderr:
		raise Exception(stderr)
	
	return stdout

def run_ledger_date(date, *args):
	return run_ledger('--end', (date + timedelta(days=1)).strftime('%Y-%m-%d'), *args)

BALANCE_FORMAT = '%(quoted(display_total)),%(quoted(account))\n'

def parse_balance(output):
	reader = csv.reader(output.splitlines())
	
	accounts = []
	
	# Parse balance lines
	for row in reader:
		balance = row[0]
		if balance.startswith(config['report_currency']):
			balance = balance[1:]
		accounts.append(Account(row[1], Decimal(balance)))
	
	return accounts

def make_account_tree(accounts):
	accounts_map = {}
	
	for account in accounts:
		accounts_map[account.name] = account
		
		for i in range(1, len(account.name_parts)):
			parent_name = ':'.join(account.name_parts[:i])
			if parent_name not in accounts_map:
				accounts_map[parent_name] = Account(parent_name, Decimal(0))
	
	for account in accounts_map.values():
		if len(account.name_parts) > 1:
			account.parent = accounts_map[':'.join(account.name_parts[:-1])]
			account.parent.children.append(account)
	
	return accounts_map

# Return a regex for an account and its children
def aregex(account):
	return '^{0}:|^{0}$'.format(account)

def financial_year(date):
	pstart = date.replace(day=1, month=7)
	if pstart > date:
		pstart = pstart.replace(year=pstart.year - 1)
	return pstart

# Calculate Unrealized Gains
def unrealized_gains(date):
	accounts_cost = parse_balance(run_ledger_date(date, 'balance', '--balance-format', BALANCE_FORMAT, '--no-total', '--flat', '--cost', aregex(config['assets_account']), aregex(config['liabilities_account'])))
	accounts_current = parse_balance(run_ledger_date(date, 'balance', '--balance-format', BALANCE_FORMAT, '--no-total', '--flat', '--market', aregex(config['assets_account']), aregex(config['liabilities_account'])))
	total_cost = sum(a.balance for a in accounts_cost)
	total_current = sum(a.balance for a in accounts_current)
	unrealized_gains = total_current - total_cost
	
	return unrealized_gains

# Get account balances at date
def get_accounts(date):
	# Calculate Unrealized Gains
	unrealized_gains_amt = unrealized_gains(date)
	
	# Get account balances
	accounts = parse_balance(run_ledger_date(date, 'balance', '--balance-format', BALANCE_FORMAT, '--no-total', '--flat', '--cost', aregex(config['income_account']), aregex(config['expenses_account'])))
	accounts += parse_balance(run_ledger_date(date, 'balance', '--balance-format', BALANCE_FORMAT, '--no-total', '--flat', '--market', aregex(config['assets_account']), aregex(config['liabilities_account']), aregex(config['equity_account'])))
	
	# Add Unrealized Gains
	accounts.append(Account(config['unrealized_gains'], -unrealized_gains_amt))
	accounts.sort(key=lambda a: a.name)
	
	return accounts

# Calculate trial balance
def trial_balance(date, pstart):
	# Get balances at period start
	accounts_pstart = get_accounts(pstart - timedelta(days=1))
	accounts_map_pstart = make_account_tree(accounts_pstart)
	
	# Get balances at date
	accounts = get_accounts(date)
	
	# Adjust Retained Earnings
	total_pandl = Decimal(0)
	if config['income_account'] in accounts_map_pstart:
		total_pandl = accounts_map_pstart[config['income_account']].total()
	if config['expenses_account'] in accounts_map_pstart:
		total_pandl += accounts_map_pstart[config['expenses_account']].total()
	
	next(a for a in accounts if a.name == config['retained_earnings']).balance += total_pandl
	
	# Adjust income/expense accounts
	for account in accounts:
		if account.name == config['income_account'] or account.name.startswith(config['income_account'] + ':') or account.name == config['expenses_account'] or account.name.startswith(config['expenses_account'] + ':'):
			if account.name in accounts_map_pstart:
				account.balance -= accounts_map_pstart[account.name].balance
	
	return accounts
