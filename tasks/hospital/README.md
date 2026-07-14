# deepsense/hospital

The agent analyzes a hospital compensation registry
(`hospital_compensation_registry.csv`) containing insurance claims and
patients with no claims, and must return the set of 3 patient IDs most likely
to be deceased (see [instruction.md](instruction.md)). The signal is
relational: a deceased patient's `emergency_contact_patient_id` points to a
family-loss claim (bereavement compensation, life event claim, family support
adjustment), and the patient has no record dated after that claim.
