# Load .env if present
ifneq (,$(wildcard .env))
include .env
export
endif

.PHONY: smoke smoke-hf smoke-cf smoke-clean

smoke: smoke-hf smoke-cf
@echo "=== ALL CHECKS PASSED ==="

smoke-hf:
@bash scripts/smoke.sh hf

smoke-cf:
@bash scripts/smoke.sh cf

smoke-clean:
@rm -rf .smoke
@echo "Cleaned .smoke/"
