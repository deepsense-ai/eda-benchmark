.PHONY: help init env test run run-benchmark run-benchmark-all-tasks ui require-task

HARBOR := uv run --project harbor harbor
BENCHMARK_CONFIG := harbor/model-benchmark.yaml
TASK_PATH = tasks/$(TASK)

MODEL ?= openai/gpt-5.5
AGENT ?= opencode
# Important to pass .env, otherwise agents won't be connecting to providers, and it won't be easily seen in logs.
ENV_FILE ?= harbor/.env
RESULTS_DIR ?= results
REPORT ?= 1
JOB_NAME ?=
EXTRA ?=

help:
	@printf '%s\n' \
		'Supported targets:' \
		'  make init' \
		'      Sync Harbor dependencies and create harbor/.env from harbor/.env.template if missing.' \
		'  make env TASK=sales_representatives' \
		'      Start an interactive Docker environment for one task.' \
		'  make test TASK=sales_representatives' \
		'      Run the oracle agent for one task with one attempt and six concurrent trials.' \
		'  make run TASK=sales_representatives MODEL=openai/gpt-5.5' \
		'      Run one model on one task with one attempt and six concurrent trials, then append a job report.' \
		'  make run-benchmark TASK=sales_representatives' \
		'      Run all benchmark models on one task using BENCHMARK_CONFIG n_attempts/n_concurrent_trials, then append a job report.' \
		'  make run-benchmark-all-tasks' \
		'      Run all benchmark models across all valid tasks using BENCHMARK_CONFIG n_attempts/n_concurrent_trials, then append a job report.' \
		'  make ui' \
		'      Open the Harbor UI for results/.' \
		'' \
		'Reportable targets automatically run harbor/job_report.py after successful Harbor runs.' \
		'' \
		'Variables:' \
		'  TASK            Required for env, test, run, and run-benchmark.' \
		'  MODEL           Model for make run. Default: openai/gpt-5.5' \
		'  AGENT           Agent for make run. Default: opencode' \
		'  ENV_FILE        Env file passed to Harbor. Default: harbor/.env' \
		'  RESULTS_DIR     Harbor output directory. Default: results' \
		'  JOB_NAME        Harbor job directory name. Defaults to target-specific timestamped names.' \
		'  REPORT          Set REPORT=0 to skip automatic job reports. Default: 1' \
		'  EXTRA           Additional Harbor CLI flags appended to run commands.' \
		'                  Example benchmark override: EXTRA='"'"'-k 2 -n 3'"'"'' \
		'                  Do not pass --jobs-dir or --job-name through EXTRA; use RESULTS_DIR and JOB_NAME.'

# Install Harbor dependencies and create the local env file once.
init:
	uv sync --project harbor
	test -f $(ENV_FILE) || cp harbor/.env.template $(ENV_FILE)

# Shared guard for commands that operate on a single task directory.
require-task:
	@if [ -z "$(TASK)" ]; then \
		echo 'TASK is required. Example: make run TASK=sales_representatives'; \
		exit 2; \
	fi
	@if [ ! -d "$(TASK_PATH)" ]; then \
		echo 'Task directory not found: $(TASK_PATH)'; \
		exit 2; \
	fi

# Open an interactive Docker environment with task files, solution, and tests mounted.
env: require-task
	$(HARBOR) task start-env -p $(TASK_PATH) -e docker -a -i $(EXTRA)

# Run the task's reference solution through Harbor's oracle agent.
test: require-task
	$(HARBOR) run -p $(TASK_PATH) -a oracle --debug --env-file $(ENV_FILE) -o $(RESULTS_DIR) -k 1 -n 1 $(EXTRA)

# Run one model/agent pair on one task.
run: require-task
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="run-$(TASK)-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -p $(TASK_PATH) -m $(MODEL) -a $(AGENT) --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" -k 1 -n 1 $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Run every agent/model entry from BENCHMARK_CONFIG on one task.
run-benchmark: require-task
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="benchmark-$(TASK)-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -c $(BENCHMARK_CONFIG) -p $(TASK_PATH) --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Run every agent/model entry from BENCHMARK_CONFIG across all valid tasks.
run-benchmark-all-tasks:
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="benchmark-all-tasks-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -c $(BENCHMARK_CONFIG) -p tasks --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Browse Harbor job results in the local web UI.
ui:
	$(HARBOR) view $(RESULTS_DIR) --jobs
