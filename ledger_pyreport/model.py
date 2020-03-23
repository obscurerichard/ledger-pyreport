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
import functools

class Ledger:
	def __init__(self, date):
		self.date = date
		
		self.root_account = Account(self, '')
		self.accounts = {}
		self.transactions = []
		
		self.prices = []
	
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
	
	def get_price(self, currency_from, currency_to, date):
		prices = [p for p in self.prices if p[1] == currency_from.name and p[2].currency == currency_to and p[0].date() <= date.date()]
		
		if not prices:
			raise Exception('No price information for {} to {} at {:%Y-%m-%d}'.format(currency_from, currency_to, date))
		
		return max(prices, key=lambda p: p[0])[2]

class Transaction:
	def __init__(self, ledger, id, date, description):
		self.ledger = ledger
		self.id = id
		self.date = date
		self.description = description
		self.postings = []
	
	def __repr__(self):
		return '<Transaction {} "{}">'.format(self.id, self.description)
	
	def describe(self):
		result = ['{:%Y-%m-%d} {}'.format(self.date, self.description)]
		for posting in self.postings:
			result.append('    {}  {}'.format(posting.account.name, posting.amount.tostr(False)))
		return '\n'.join(result)

class Posting:
	def __init__(self, transaction, account, amount):
		self.transaction = transaction
		self.account = account
		self.amount = Amount(amount)
	
	def __repr__(self):
		return '<Posting "{}" {}>'.format(self.account.name, self.amount.tostr(False))
	
	def exchange(self, currency, date):
		if self.amount.currency.name == currency.name and self.amount.currency.is_prefix == currency.is_prefix:
			return Amount(self.amount)
		
		return self.amount.exchange(currency, True) # Cost basis

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
	def is_cost(self):
		return self.is_income or self.is_expense or self.is_equity
	@property
	def is_market(self):
		return self.is_asset or self.is_liability

class Amount:
	def __init__(self, amount, currency=None):
		if isinstance(amount, Amount):
			self.amount = amount.amount
			self.currency = amount.currency
		elif currency is None:
			raise TypeError('currency is required')
		else:
			self.amount = Decimal(amount)
			self.currency = currency
	
	def tostr(self, round=True):
		if self.currency.is_prefix:
			amount_str = ('{}{:.2f}' if round else '{}{}').format(self.currency.name, self.amount)
		else:
			amount_str = ('{:.2f} {}' if round else '{:.2f} {}').format(self.amount, self.currency.name)
		
		if self.currency.price:
			return '{} {{{}}}'.format(amount_str, self.currency.price)
		return amount_str
	
	def __repr__(self):
		return '<Amount {}>'.format(self.tostr(False))
	
	def __str__(self):
		return self.tostr()
	
	def compatible_currency(func):
		@functools.wraps(func)
		def wrapped(self, other):
			if isinstance(other, Amount):
				if other.currency != self.currency:
					raise TypeError('Cannot combine Amounts of currency {} and {}'.format(self.currency.name, other.currency.name))
				other = other.amount
			elif other != 0:
				raise TypeError('Cannot combine Amount with non-zero number')
			return func(self, other)
		return wrapped
	
	def __neg__(self):
		return Amount(-self.amount, self.currency)
	def __abs__(self):
		return Amount(abs(self.amount), self.currency)
	
	def __eq__(self, other):
		if isinstance(other, Amount):
			if self.amount == 0 and other.amount == 0:
				return True
			if other.currency != self.currency:
				return False
			return self.amount == other.amount
		
		if other == 0:
			return self.amount == 0
		
		raise TypeError('Cannot compare Amount with non-zero number')
	@compatible_currency
	def __ne__(self, other):
		return self.amount != other
	@compatible_currency
	def __gt__(self, other):
		return self.amount > other
	@compatible_currency
	def __ge__(self, other):
		return self.amount >= other
	@compatible_currency
	def __lt__(self, other):
		return self.amount < other
	@compatible_currency
	def __le__(self, other):
		return self.amount <= other
	
	@compatible_currency
	def __add__(self, other):
		return Amount(self.amount + other, self.currency)
	@compatible_currency
	def __radd__(self, other):
		return Amount(other + self.amount, self.currency)
	@compatible_currency
	def __sub__(self, other):
		return Amount(self.amount - other, self.currency)
	@compatible_currency
	def __rsub__(self, other):
		return Amount(other - self.amount, self.currency)
	
	def exchange(self, currency, is_cost, price=None):
		if self.currency.name == currency.name and self.currency.is_prefix == currency.is_prefix:
			return Amount(self)
		
		if is_cost and self.currency.price and self.currency.price.currency.name == currency.name and self.currency.price.currency.is_prefix == currency.is_prefix:
			return Amount(self.amount * self.currency.price.amount, currency)
		
		if price:
			return Amount(self.amount * price.amount, currency)
		
		raise TypeError('Cannot exchange {} to {}'.format(self.currency, currency))
	
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
			new_amount = next((a for a in new_amounts if a.currency == amount.currency), None)
		return Balance(new_amounts)
	
	def clean(self):
		return Balance([a for a in self.amounts if a != 0])
	
	def exchange(self, currency, is_cost, date=None, ledger=None):
		result = Amount(0, currency)
		for amount in self.amounts:
			if is_cost or amount.currency.name == currency.name and amount.currency.is_prefix == amount.currency.is_prefix:
				result += amount.exchange(currency, is_cost)
			else:
				result += amount.exchange(currency, is_cost, ledger.get_price(amount.currency, currency, date))
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
				new_amount = next((a for a in new_amounts if a.currency == amount.currency), None)
				if new_amount is None:
					new_amount = Amount(0, amount.currency)
					new_amounts.append(new_amount)
				new_amount.amount += amount.amount
				
				#if new_amount == 0:
				#	new_amounts.remove(new_amount)
		elif isinstance(other, Amount):
			new_amount = next((a for a in new_amounts if a.currency == other.currency), None)
			if new_amount is None:
				new_amount = Amount(0, other.currency)
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

class Currency:
	def __init__(self, name, is_prefix, price=None):
		self.name = name
		self.is_prefix = is_prefix
		self.price = price
	
	def __repr__(self):
		return '<Currency {} ({})>'.format(self.name, 'prefix' if self.is_prefix else 'suffix')
	
	def __eq__(self, other):
		if not isinstance(other, Currency):
			return False
		return self.name == other.name and self.is_prefix == other.is_prefix and self.price == other.price

class TrialBalance:
	def __init__(self, ledger, date, pstart):
		self.ledger = ledger
		self.date = date
		self.pstart = pstart
		
		self.balances = {}
	
	def get_balance(self, account):
		return self.balances.get(account.name, Balance())
	
	def get_total(self, account):
		return self.get_balance(account) + sum((self.get_total(a) for a in account.children), Balance())
