.PHONY: help init env test run run-benchmark run-benchmark-all-tasks ui require-task require-litellm

HARBOR := uv run --project harbor harbor
TASK_PATH = tasks/$(TASK)

MODEL ?= openai/gpt-5.5
AGENT ?= opencode
# Important to pass .env, otherwise agents won't be connecting to providers, and it won't be easily seen in logs.
ENV_FILE ?= harbor/.env
RESULTS_DIR ?= results
REPORT ?= 1
JOB_NAME ?=
EXTRA ?=

# LITELLM=1 sends claude-code, codex and antigravity-cli through a LiteLLM proxy with one
# virtual key. The key stays in ENV_FILE as LITELLM_API_KEY: the --ae values below carry only
# the ${LITELLM_API_KEY} template, which Harbor resolves after loading ENV_FILE and takes
# before the provider keys from ENV_FILE. The proxy address is read from ENV_FILE too.
LITELLM ?= 0
LITELLM_PROXY_URL ?= $(shell sed -n 's/^LITELLM_PROXY_URL=//p' $(ENV_FILE) 2>/dev/null | tail -n 1 | tr -d "\"' " | sed 's:/*$$::')
LITELLM_AE = \
	--ae 'ANTHROPIC_API_KEY=$${LITELLM_API_KEY}' --ae 'ANTHROPIC_BASE_URL=$(LITELLM_PROXY_URL)' \
	--ae 'OPENAI_API_KEY=$${LITELLM_API_KEY}' --ae 'OPENAI_BASE_URL=$(LITELLM_PROXY_URL)/v1' \
	--ae 'GEMINI_API_KEY=$${LITELLM_API_KEY}' --ae 'GOOGLE_GEMINI_BASE_URL=$(LITELLM_PROXY_URL)'
ifeq ($(LITELLM),1)
PROVIDER_AE = $(LITELLM_AE)
# Proxy model names differ from the provider ones (e.g. claude-code takes them without prefix).
BENCHMARK_CONFIG ?= harbor/model-benchmark-litellm.yaml
else
PROVIDER_AE =
endif
BENCHMARK_CONFIG ?= harbor/model-benchmark.yaml

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
		'  LITELLM         Set LITELLM=1 to run claude-code, codex and antigravity-cli through a LiteLLM proxy' \
		'                  for run, run-benchmark and run-benchmark-all-tasks. Needs LITELLM_API_KEY (the virtual' \
		'                  key) and LITELLM_PROXY_URL in ENV_FILE; the provider keys there are then not used.' \
		'                  Model names must be the proxy ones; claude-code takes them without prefix.' \
		'                  Example: make run TASK=x LITELLM=1 AGENT=claude-code MODEL=claude-sonnet-5-5' \
		'  LITELLM_PROXY_URL  Proxy address without /v1. Default: LITELLM_PROXY_URL from ENV_FILE' \
		'  BENCHMARK_CONFIG   Benchmark agents and models. Default: harbor/model-benchmark.yaml,' \
		'                  with LITELLM=1 harbor/model-benchmark-litellm.yaml' \
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

# With LITELLM=1, check that ENV_FILE has what the --ae templates and base URLs need.
require-litellm:
ifeq ($(LITELLM),1)
	@if [ -z "$(LITELLM_PROXY_URL)" ]; then \
		echo 'LITELLM=1 needs LITELLM_PROXY_URL in $(ENV_FILE), e.g. LITELLM_PROXY_URL=https://litellm.example.com'; \
		exit 2; \
	fi
	@if ! grep -qE '^LITELLM_API_KEY=.+' $(ENV_FILE) 2>/dev/null; then \
		echo 'LITELLM=1 needs LITELLM_API_KEY (the LiteLLM virtual key) in $(ENV_FILE)'; \
		exit 2; \
	fi
endif

# Open an interactive Docker environment with task files, solution, and tests mounted.
env: require-task
	$(HARBOR) task start-env -p $(TASK_PATH) -e docker -a -i $(EXTRA)

# Run the task's reference solution through Harbor's oracle agent.
test: require-task
	$(HARBOR) run -p $(TASK_PATH) -a oracle --debug --env-file $(ENV_FILE) -o $(RESULTS_DIR) -k 1 -n 1 $(EXTRA)

# Run one model/agent pair on one task.
run: require-task require-litellm
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="run-$(TASK)-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -p $(TASK_PATH) -m $(MODEL) -a $(AGENT) --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" -k 1 -n 1 $(PROVIDER_AE) $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Run every agent/model entry from BENCHMARK_CONFIG on one task.
run-benchmark: require-task require-litellm
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="benchmark-$(TASK)-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -c $(BENCHMARK_CONFIG) -p $(TASK_PATH) --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" $(PROVIDER_AE) $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Run every agent/model entry from BENCHMARK_CONFIG across all valid tasks.
run-benchmark-all-tasks: require-litellm
	set -e; \
	job_name="$(JOB_NAME)"; \
	if [ -z "$$job_name" ]; then job_name="benchmark-all-tasks-$$(date +%Y%m%d-%H%M%S)"; fi; \
	$(HARBOR) run -c $(BENCHMARK_CONFIG) -p tasks --env-file $(ENV_FILE) --jobs-dir $(RESULTS_DIR) --job-name "$$job_name" $(PROVIDER_AE) $(EXTRA); \
	if [ "$(REPORT)" != "0" ]; then uv run --project harbor python harbor/job_report.py "$(RESULTS_DIR)/$$job_name"; fi

# Browse Harbor job results in the local web UI.
ui:
	$(HARBOR) view $(RESULTS_DIR) --jobs
