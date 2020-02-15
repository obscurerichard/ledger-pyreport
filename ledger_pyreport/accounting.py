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

from . import ledger

# Generate balance sheet

def balance_sheet(date, pstart):
	# Get trial balance
	trial_balance = ledger.trial_balance(date, pstart)
	
	# Calculate Profit/Loss
	total_pandl = trial_balance.get_total(ledger.config['income_account']) + trial_balance.get_total(ledger.config['expenses_account'])
	
	# Add Current Year Earnings account
	trial_balance.set_balance(ledger.config['current_year_earnings'], trial_balance.get_balance(ledger.config['current_year_earnings']) + total_pandl)
	
	return trial_balance
