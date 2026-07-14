# deepsense/tax-fraud-detection

The agent plays a tax auditor: given a company registry (`companies.csv`) and invoice records
(`invoices.csv`), it must return the set of 10 company IDs most likely to be
fraudulent (see [instruction.md](instruction.md)). The dataset hides three
fraud patterns: Benford's-law violations among active sellers, phantom
buyer-only shell companies, and invoice laundering through unregistered
EIN-formatted "charity" recipients.
