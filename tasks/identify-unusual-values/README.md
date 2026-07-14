# deepsense/identify-unusual-values

The agent performs a rule-heavy, multi-stage outlier analysis on a synthetic
stroke dataset (`synthetic_stroke_data.csv`): discard physically impossible
values, apply 3·IQR outlier detection with a stroke-association exception for
glucose (including a conditional log2 re-check), build a normalized
`risk_proxy` feature, flag multivariate outliers via Mahalanobis distance
against a chi-square critical value, and add categorical impossibilities
(smoking children, working children, studying toddlers). The answer is the
list of all outlier row indices mapped back to the original file order (see
[instruction.md](instruction.md)).
