.PHONY: run
run:
	poetry run text-relay

.PHONY: kill-port
kill-port:
	@port=$$(awk -F= '/^[[:space:]]*PORT[[:space:]]*=/ { gsub(/[[:space:]"\047]/, "", $$2); print $$2; exit }' .env); \
	if [ -z "$$port" ]; then echo "PORT is not set in .env" >&2; exit 1; fi; \
	pids=$$(lsof -nP -tiTCP:$$port -sTCP:LISTEN); \
	if [ -z "$$pids" ]; then echo "No listener found on port $$port"; else echo "Killing listener(s) on port $$port: $$pids"; kill $$pids; fi
