

## Node-free UI option (Zip 0002)

This zip includes a **static UI** served by FastAPI at the root path.
You can run ONLY the backend and use the app at http://127.0.0.1:8000 without installing Node/npm.

- Static files live in `backend/web/`
- Charts provided by Chart.js via CDN

### Run
```bash
cd backend
./run.sh
# open http://127.0.0.1:8000
```

### Optional: Install Node for the React dev app
If you prefer the React/Vite frontend, install Node (macOS/Homebrew):
```bash
brew install node@20
# ensure PATH contains /opt/homebrew/opt/node@20/bin
```
Then:
```bash
cd frontend
npm install
npm run dev
```
