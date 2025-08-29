# Jira Reporting (0043)

## Setup
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env  # then edit JIRA_API_TOKEN

## Run
chmod +x backend/run.sh
./backend/run.sh
