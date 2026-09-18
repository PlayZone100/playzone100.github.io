# Temporary Codespace setup

This repository includes a Codespaces configuration. After creating or rebuilding a Codespace:

1. Create the local environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and add an authorized video API endpoint and secret key. Do not commit `.env`.

3. The Codespace installs dependencies automatically and starts the API on port `3000` when `.env` exists.

4. Open the forwarded port from the **PORTS** panel. Set its visibility to **Public** only for temporary testing.

Check the API with:

```text
/api/health
```

GitHub Pages cannot run `server.js`; the page must call the public Codespace URL when the backend is hosted there.
