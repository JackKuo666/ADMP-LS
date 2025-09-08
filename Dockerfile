# =========================
# Simple Python 3.12 environment
# =========================
FROM python:3.12-slim-bullseye AS final
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Create user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Copy application code
COPY --chown=user client/  $HOME/app/client/
COPY --chown=user servers/ $HOME/app/servers/

# Create independent virtual environments for each service
RUN python -m venv $HOME/venvs/client \
  && python -m venv $HOME/venvs/retrieve \
  && python -m venv $HOME/venvs/review

# Install client dependencies
RUN $HOME/venvs/client/bin/pip install --no-cache-dir -U pip \
  && $HOME/venvs/client/bin/pip install --no-cache-dir -r $HOME/app/client/requirements.txt

# Install Retrieve dependencies
RUN $HOME/venvs/retrieve/bin/pip install --no-cache-dir -U pip \
  && $HOME/venvs/retrieve/bin/pip install --no-cache-dir -r $HOME/app/servers/Retrieve/requirements.txt \
  && $HOME/venvs/retrieve/bin/pip install --no-cache-dir -U crawl4ai \
  && $HOME/venvs/retrieve/bin/crawl4ai-setup || true \
  && $HOME/venvs/retrieve/bin/crawl4ai-doctor || true

# Install Review dependencies
RUN $HOME/venvs/review/bin/pip install --no-cache-dir -U pip \
  && $HOME/venvs/review/bin/pip install --no-cache-dir -r $HOME/app/servers/Review/requirements.txt

# Generate startup script
RUN mkdir -p $HOME/app \
  && cat <<'EOF' > $HOME/app/start.sh
#!/bin/bash
set -e
cd "$HOME/app"

start_service() {
  local name="$1"
  local dir="$2"
  local py="$3"
  (
    cd "$dir"
    while true; do
      echo "[startup] Starting $name (Python 3.12)…"
      set +e
      "$py" main.py
      exit_code=$?
      set -e
      if [ $exit_code -eq 0 ]; then
        echo "[$name] exited normally"
        break
      else
        echo "[$name] crashed with code $exit_code, restarting in 10s..."
        sleep 10
      fi
    done
  ) &
}

if [ -d "servers/Retrieve" ]; then
  start_service "Retrieve" "servers/Retrieve" "$HOME/venvs/retrieve/bin/python"
fi

if [ -d "servers/Review" ]; then
  start_service "Review" "servers/Review" "$HOME/venvs/review/bin/python"
fi

# Wait for backend services to start
sleep 5

# Start frontend Streamlit
echo "[startup] Starting Streamlit client (Python 3.12)…"
cd "$HOME/app/client"
export PORT="${PORT:-7860}"
exec "$HOME/venvs/client/bin/python" -m streamlit run app.py --server.port="$PORT" --server.address=0.0.0.0
EOF

RUN chmod +x $HOME/app/start.sh

EXPOSE 7860
CMD ["/bin/bash", "/home/user/app/start.sh"]