# Vercel Deployment Notes

Deploy `apps/web` as the Vercel project root.

Required environment variable:

```text
NEXT_PUBLIC_API_BASE_URL=https://<modal-api-url>
```

Do not add provider keys or Backblaze B2 keys to Vercel. All secret-bearing calls go through the Modal-hosted FastAPI backend.
