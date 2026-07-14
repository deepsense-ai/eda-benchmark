# deepsense/cleaning-service

The agent computes monthly payroll for a cleaning company from three messy
files: `timesheet.csv` (duplicated rows, malformed employee IDs, invalid
dates, zero-hour entries, broken task lists), `tasks.csv` (per-task completion
bonuses), and `employees.csv` (the PESEL registry). Billing periods start on
the weekday inherited from the dataset's earliest record, so rows must be
assigned to billing months rather than calendar months. The answer is a dict
mapping each PESEL to its list of integer monthly salaries in billing-month
order (see [instruction.md](instruction.md)).
