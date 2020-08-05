# ledger-pyreport

ledger-pyreport is a lightweight Flask webapp for generating interactive and printable accounting reports from [ledger-cli](https://www.ledger-cli.org/) data.

## Reports

* Trial balance, and comparative trial balance
* Balance sheet, and comparative balance sheet
* Income statement, and comparative income statement
* Cash flow statement, and comparative cash flow statement (direct and indirect methods)
* General ledger
* Account transactions, with or without itemisation of commodities
* Transaction detail, with or without itemisation of commodities

## Features

* Correctly values:
	* assets/liabilities at fair market value (cf. [AASB](https://www.aasb.gov.au/admin/file/content105/c9/AASB9_12-14_COMPdec17_01-19.pdf)/[IFRS 9](http://eifrs.ifrs.org/eifrs/bnstandards/en/IFRS9.pdf) ¶4.1.4, [AASB 121](https://www.aasb.gov.au/admin/file/content105/c9/AASB121_08-15_COMPfeb16_01-19.pdf)/[IAS 21](http://eifrs.ifrs.org/eifrs/bnstandards/en/IAS21.pdf) ¶23) or historical cost (cf. [AASB 102](https://www.aasb.gov.au/admin/file/content105/c9/AASB102_07-15_COMPdec16_01-19.pdf)/[IAS 2](http://eifrs.ifrs.org/eifrs/bnstandards/en/IAS2.pdf) ¶9), as applicable
	* income/expenses at historical cost (cf. [AASB 121](https://www.aasb.gov.au/admin/file/content105/c9/AASB121_08-15_COMPfeb16_01-19.pdf)/[IAS 21](http://eifrs.ifrs.org/eifrs/bnstandards/en/IAS21.pdf) ¶21)
* Correctly computes unrealised gains ([even when Ledger does not](https://yingtongli.me/blog/2020/03/31/ledger-gains.html))
* Accounts for both profit and loss, and other comprehensive income
* Simulates annual closing of books, with presentation of income/expenses on the balance sheet as retained earnings and current year earnings
* ~~Can simulate cash basis accounting, using FIFO methodology to recode transactions involving liabilities and non-cash assets~~ (Very buggy so disabled for now)
* Can separately report specified categories of income and expense, reporting per-category net profit
* Extensible through custom programming hooks

## Background, demo and screenshots

See [https://yingtongli.me/blog/2020/03/31/ledger-pyreport.html](https://yingtongli.me/blog/2020/03/31/ledger-pyreport.html) for further discussion.

## Usage

Install the dependencies from PyPI, optionally in a virtual environment: (Commands presented for Linux/Mac)

```
virtualenv -p python3 venv
. venv/bin/activate
pip3 install -r requirements.txt
```

Copy *config.example.yml* to *config.yml* (or set the *LEDGER_PYREPORT_CONFIG* environment variable to the path to the config file). Edit as required, in particular setting the path of the Ledger journal file, reporting currency and any required Ledger arguments.

Run as per a usual Flask app, for example:

```
FLASK_APP=ledger_pyreport python3 -m flask run
```

## Notes on Ledger setup

ledger-pyreport expects each of assets, liabilities, equity, income and expenses to be setup in Ledger as a separate top-level account. These accounts should contain a zero balance, with all transactions in child accounts.

Additionally, ledger-pyreport expects the next level of assets and liabilities to be categories of asset and liability (e.g. *Assets:Current*, *Liabilities:Non-current*). These, too, should contain a zero balance.

Ledger-pyreport by default observes the convention that positive amounts in Ledger represent debits, and negative amounts in Ledger represent credits.

A commodity which has *any* price data in Ledger (including those specified through `@` or `@@`, or explicitly through `P`) will be regarded as a commodity measured at fair market value, and automatically revalued accordingly. A commodity which has *no* price data in Ledger (i.e. lot prices through `{…}` or `{{…}}` only) will be regarded as a commodity measured at historical cost, and will not be subsequently revalued.

In accordance with accrual accounting, unrealised gains are charged to the Unrealized Gains income/expense account shown in *config.yml* in the period in which they occur. Subsequent realisations of those gains should be charged against the Unrealized Gains account within the Ledger journal. Alternatively, if charged to a different account (e.g. a realised Capital Gains income account), note that the Unrealized Gains account will contain a *contra* balance corresponding to previous years gains which are now realised.

## Comparative statements

ledger-pyreport can be used to produce comparative statements, for example ‘compare *n* years’ or ‘compare *n* months’.

The dates in the ‘date’ and ‘period start’ fields represent the most recent period. These two fields are then advanced backwards in increments of the specified time interval to determine dates for the preceding periods.

However, if the interval is set to ‘months’, and the ‘date’ is the last day of a calendar month, then preceding dates will also be set to the last day of each preceding calendar month.

Example 1: Setting a date of 2019-10-31 and period start of 2019-07-01 with ‘compare *n* years’ will generate *year to date* comparisons as at 31 October of each year. To generate year end comparisons, set a date of 2020-06-30 with period start 2019-07-01.

Example 2: Setting a date of 2019-10-31 and period start of 2019-07-01 with ‘compare *n* months’ will compare the *overlapping* 4-month periods Jul–Oct, Jun–Sep, May–Aug, etc. To instead compare calendar months, set a date of 2019-10-31 with period start 2019-10-01.

## Caution on standards compliance

ledger-pyreport is developed with reference to the [AASB Australian Accounting Standards](https://www.aasb.gov.au/Pronouncements/Current-standards.aspx) and [IFRS International Financial Reporting Standards](https://www.ifrs.org/issued-standards/list-of-standards/), and we prefer compliance with those standards whenever practical. (We do not specifically consider United States FASB GAAP compliance.)

However, strict compliance with AASB/IFRS is not always practical, and ledger-pyreport departs from AASB/IFRS in a number of material ways – for example, the statement of cash flows generated by ledger-pyreport does not show the detailed subclassifications required by AASB/IFRS, nor does ledger-pyreport produce a statement of changes in equity. In both cases, the background information required to produce the reports accurately is beyond the scope of ledger-pyreport.

Other aspects of AASB/IFRS requirements are the user's responsibility – for example, the selection of an appropriate chart of accounts and appropriate recognition of transactions in those accounts.
