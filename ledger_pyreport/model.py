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

from .config import config

from decimal import Decimal
from enum import Enum
import functools

class Ledger:
	def __init__(self, date):
		self.date = date
		
		self.root_account = Account(self, '')
		self.accounts = {}
		self.transactions = []
		
		self.commodities = {}
		self.prices = []
	
	def clone(self):
		result = Ledger(self.date)
		result.root_account = self.root_account
		result.accounts = self.accounts
		result.transactions = self.transactions[:]
		result.prices = self.prices
		return result
	
	def get_account(self, name):
		if name == '':
			return self.root_account
		
		if name in self.accounts:
			return self.accounts[name]
		
		account = Account(self, name)
		if account.parent:
			account.parent.children.append(account)
		self.accounts[name] = account
		
		return account
	
	def get_commodity(self, name):
		return self.commodities[name]
	
	def get_price(self, commodity_from, commodity_to, date):
		prices = [p for p in self.prices if p[1] == commodity_from.name and p[2].commodity == commodity_to and p[0].date() <= date.date()]
		
		if not prices:
			raise Exception('No price information for {} to {} at {:%Y-%m-%d}'.format(commodity_from, commodity_to, date))
		
		return max(prices, key=lambda p: p[0])[2]

class Transaction:
	def __init__(self, ledger, id, date, description, code=None):
		self.ledger = ledger
		self.id = id
		self.date = date
		self.description = description
		self.code = code
		
		self.postings = []
	
	def __repr__(self):
		return '<Transaction {} "{}">'.format(self.id, self.description)
	
	def describe(self):
		result = ['{:%Y-%m-%d} {}'.format(self.date, self.description)]
		for posting in self.postings:
			result.append('    {}  {}'.format(posting.account.name, posting.amount.tostr(False)))
		return '\n'.join(result)
	
	@property
	def has_comment_detail(self):
		return any(p.comment for p in self.postings)

class Posting:
	class State(Enum):
		UNCLEARED = 0
		CLEARED = 1
		PENDING = 2
	
	def __init__(self, transaction, account, amount, comment=None, state=State.UNCLEARED):
		self.transaction = transaction
		self.account = account
		self.amount = Amount(amount)
		self.comment = comment
		self.state = state
	
	def __repr__(self):
		return '<Posting "{}" {}>'.format(self.account.name, self.amount.tostr(False))
	
	def exchange(self, commodity, date):
		if self.amount.commodity.name == commodity.name:
			return Amount(self.amount)
		
		return self.amount.exchange(commodity, True) # Cost basis

class Account:
	def __init__(self, ledger, name):
		self.ledger = ledger
		self.name = name
		
		self.children = []
	
	def __repr__(self):
		return '<Account {}>'.format(self.name)
	
	@property
	def bits(self):
		return self.name.split(':')
	
	@property
	def parent(self):
		if self.name == '':
			return None
		return self.ledger.get_account(':'.join(self.bits[:-1]))
	
	def matches(self, part):
		if self.name == part or self.name.startswith(part + ':'):
			return True
		return False
	
	@property
	def is_income(self):
		return self.matches(config['income_account'])
	@property
	def is_expense(self):
		return self.matches(config['expenses_account'])
	@property
	def is_equity(self):
		return self.matches(config['equity_account'])
	@property
	def is_asset(self):
		return self.matches(config['assets_account'])
	@property
	def is_liability(self):
		return self.matches(config['liabilities_account'])
	@property
	def is_cash(self):
		# Is this a cash asset?
		return any(self.matches(a) for a in config['cash_asset_accounts'])
	@property
	def is_oci(self):
		return self.matches(config['oci_account'])
	
	@property
	def is_cost(self):
		return self.is_income or self.is_expense or self.is_equity
	@property
	def is_market(self):
		return self.is_asset or self.is_liability

class Amount:
	def __init__(self, amount, commodity=None):
		if isinstance(amount, Amount):
			self.amount = amount.amount
			self.commodity = amount.commodity
		elif commodity is None:
			raise TypeError('commodity is required')
		else:
			self.amount = Decimal(amount)
			self.commodity = commodity
	
	def tostr(self, round=True):
		if self.commodity.is_prefix:
			amount_str = ('{}{:.2f}' if round else '{}{}').format(self.commodity.name, self.amount)
		else:
			amount_str = ('{:.2f} {}' if round else '{} {}').format(self.amount, self.commodity.name)
		
		if self.commodity.price:
			return '{} {{{}}}'.format(amount_str, self.commodity.price.tostr(round))
		return amount_str
	
	def __repr__(self):
		return '<Amount {}>'.format(self.tostr(False))
	
	def __str__(self):
		return self.tostr()
	
	def compatible_commodity(func):
		@functools.wraps(func)
		def wrapped(self, other):
			if isinstance(other, Amount):
				if other.commodity != self.commodity:
					raise TypeError('Cannot combine Amounts of commodity {} and {}'.format(self.commodity.name, other.commodity.name))
				other = other.amount
			elif other != 0:
				raise TypeError('Cannot combine Amount with non-zero number')
			return func(self, other)
		return wrapped
	
	def __neg__(self):
		return Amount(-self.amount, self.commodity)
	def __abs__(self):
		return Amount(abs(self.amount), self.commodity)
	
	def __eq__(self, other):
		if isinstance(other, Amount):
			if self.amount == 0 and other.amount == 0:
				return True
			if other.commodity != self.commodity:
				return False
			return self.amount == other.amount
		
		if other == 0:
			return self.amount == 0
		
		raise TypeError('Cannot compare Amount with non-zero number')
	@compatible_commodity
	def __ne__(self, other):
		return self.amount != other
	@compatible_commodity
	def __gt__(self, other):
		return self.amount > other
	@compatible_commodity
	def __ge__(self, other):
		return self.amount >= other
	@compatible_commodity
	def __lt__(self, other):
		return self.amount < other
	@compatible_commodity
	def __le__(self, other):
		return self.amount <= other
	
	@compatible_commodity
	def __add__(self, other):
		return Amount(self.amount + other, self.commodity)
	@compatible_commodity
	def __radd__(self, other):
		return Amount(other + self.amount, self.commodity)
	@compatible_commodity
	def __sub__(self, other):
		return Amount(self.amount - other, self.commodity)
	@compatible_commodity
	def __rsub__(self, other):
		return Amount(other - self.amount, self.commodity)
	
	def exchange(self, commodity, is_cost, price=None):
		if self.commodity.name == commodity.name:
			return Amount(self)
		
		if is_cost and self.commodity.price and self.commodity.price.commodity.name == commodity.name:
			return Amount(self.amount * self.commodity.price.amount, commodity)
		
		if price:
			return Amount(self.amount * price.amount, commodity)
		
		raise TypeError('Cannot exchange {} to {}'.format(self.commodity, commodity))
	
	@property
	def near_zero(self):
		if abs(self.amount) < 0.005:
			return True
		return False

class Balance:
	def __init__(self, amounts=None):
		self.amounts = amounts or []
	
	def tidy(self):
		new_amounts = []
		for amount in self.amounts:
			new_amount = next((a for a in new_amounts if a.commodity == amount.commodity), None)
		return Balance(new_amounts)
	
	def clean(self):
		return Balance([a for a in self.amounts if a != 0])
	
	def exchange(self, commodity, is_cost, date=None, ledger=None):
		result = Amount(0, commodity)
		for amount in self.amounts:
			if is_cost or amount.commodity.name == commodity.name:
				result += amount.exchange(commodity, is_cost)
			else:
				if any(p[1] == amount.commodity.name for p in ledger.prices):
					# This commodity has price information
					# Measured at fair value
					result += amount.exchange(commodity, is_cost, ledger.get_price(amount.commodity, commodity, date))
				else:
					# This commodity has no price information
					# Measured at historical cost
					result += amount.exchange(commodity, True)
		return result
	
	def __neg__(self):
		return Balance([-a for a in self.amounts])
	
	def __eq__(self, other):
		if isinstance(other, Balance):
			raise Exception('NYI')
		elif isinstance(other, Amount):
			raise Exception('NYI')
		elif other == 0:
			return all(a == 0 for a in self.amounts)
		else:
			raise TypeError('Cannot compare Balance with non-zero number')
	
	def __add__(self, other):
		new_amounts = [Amount(a) for a in self.amounts]
		
		if isinstance(other, Balance):
			for amount in other.amounts:
				new_amount = next((a for a in new_amounts if a.commodity == amount.commodity), None)
				if new_amount is None:
					new_amount = Amount(0, amount.commodity)
					new_amounts.append(new_amount)
				new_amount.amount += amount.amount
				
				#if new_amount == 0:
				#	new_amounts.remove(new_amount)
		elif isinstance(other, Amount):
			new_amount = next((a for a in new_amounts if a.commodity == other.commodity), None)
			if new_amount is None:
				new_amount = Amount(0, other.commodity)
				new_amounts.append(new_amount)
			new_amount.amount += other.amount
			
			#if new_amount == 0:
			#	new_amounts.remove(new_amount)
		elif other == 0:
			pass
		else:
			raise Exception('NYI')
		
		return Balance(new_amounts)
	
	def __sub__(self, other):
		return self + (-other)

class Commodity:
	def __init__(self, name, is_prefix, price=None):
		self.name = name
		self.is_prefix = is_prefix
		self.price = price
	
	def __repr__(self):
		return '<Commodity {} ({})>'.format(self.name, 'prefix' if self.is_prefix else 'suffix')
	
	def __eq__(self, other):
		if not isinstance(other, Commodity):
			return False
		return self.name == other.name and self.price == other.price
	
	def strip_price(self):
		return Commodity(self.name, self.is_prefix)

class TrialBalance:
	def __init__(self, ledger, date, pstart, label=None):
		self.ledger = ledger
		self.date = date
		self.pstart = pstart
		self.label = label
		
		self.balances = {}
	
	def get_balance(self, account):
		return self.balances.get(account.name, Balance())
	
	def get_total(self, account):
		return self.get_balance(account) + sum((self.get_total(a) for a in account.children), Balance())
