# Muse Bridge

Bridge akun Muse menjadi API yang OpenAI-compatible. Satu akun Muse, satu API key.
Kuota mengikuti subscription asli, bayar via QRIS.

> OpenAI-compatible endpoint: `http://127.0.0.1:8765/v1` (atau `https://muse.mfah.me/v1`).

## Cara kerja

- Request masuk di-queue. Muse agent (sandbox) menjawab via push trigger.
- 1 akun Muse = 1 API key (`api_keys.json`).
- Per-key quota: manual DAN real subscription limit, keduanya bikin 429.
- Admin dashboard di `/admin/` (auth `Bearer admin_secret`): list/create/update/delete key.

## Jalankan

Butuh env: `MUSE_BRIDGE_DIR`, `SMTP_*` (email), `MIDTRANS_SERVER_KEY` (pembayaran),
`PUSH_SECRET_FILE`, `ADMIN_SECRET_FILE`.

```bash
cp .env.example .env
python3 bridge.py
```

## Endpoint

- `POST /v1/chat/completions`, `/v1/models` - OpenAI-compatible.
- `GET /v1/real-quota` - kuota subscription asli akun pemanggil.
- `POST /v1/real-quota` - (Bearer key) report kuota dari tempat akun login.
- `GET /admin/` - dashboard admin (Bearer admin_secret).
- `GET /health` - healthcheck.
