# Ask Mary — Operations Runbook

> For humans. Copy-paste the commands. No surprises.

---

## What Costs Money While Running

| Service | Running cost | How to stop |
|---------|-------------|-------------|
| **Cloud SQL (Postgres)** | **~$7-12/day** — this is the big one | Stop the instance |
| Cloud Run (min-instances=1) | ~$0.50-1.00/day | Set min-instances to 0 |
| Cloud Storage (GCS bucket) | ~$0.02/GB/month | Leave it, negligible |
| Artifact Registry (Docker images) | ~$0.10/GB/month | Leave it, negligible |

Cloud SQL charges for the instance **being on**, not per query. Even if nobody uses it, it costs ~$7-12/day on `db-f1-micro`.

---

## After the Demo: Pause Everything

Run these two commands. Idle cost drops to essentially **$0/month**.

```bash
# 1. Stop Cloud SQL instance (biggest cost saver)
gcloud sql instances patch ask-mary-db \
  --activation-policy=NEVER \
  --project=ask-mary-486802

# 2. Scale Cloud Run to zero (no idle instances)
gcloud run services update ask-mary \
  --region=us-west2 \
  --min-instances=0 \
  --project=ask-mary-486802
```

That's it. Storage (GCS bucket + Artifact Registry) costs pennies and can stay.

---

## Bring It Back Up

When you're ready to demo again or do more development:

```bash
# 1. Restart Cloud SQL (takes ~1-2 minutes to come online)
gcloud sql instances patch ask-mary-db \
  --activation-policy=ALWAYS \
  --project=ask-mary-486802

# 2. Cloud Run — no action needed
#    It auto-scales from 0 on the next incoming request.
#    First request after cold start takes ~5-10 seconds.
```

Verify it's working:
```bash
curl https://ask-mary-1030626458480.us-west2.run.app/health
# Should return: {"status": "ok"}
```

---

## Delete Everything (Nuclear Option)

Only if you're completely done with the project and want to stop all charges permanently. **This is irreversible** — database data will be lost.

```bash
# Delete Cloud Run service
gcloud run services delete ask-mary \
  --region=us-west2 \
  --project=ask-mary-486802

# Delete Cloud SQL instance (destroys all data)
gcloud sql instances delete ask-mary-db \
  --project=ask-mary-486802

# Delete Docker images from Artifact Registry
gcloud artifacts repositories delete ask-mary \
  --location=us-west2 \
  --project=ask-mary-486802

# Delete GCS audio bucket (optional)
gcloud storage rm --recursive gs://ask-mary-audio
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| Check if Cloud SQL is running | `gcloud sql instances describe ask-mary-db --project=ask-mary-486802 --format="value(state)"` |
| Check Cloud Run status | `gcloud run services describe ask-mary --region=us-west2 --project=ask-mary-486802 --format="value(status.url)"` |
| View Cloud Run logs | `gcloud run services logs read ask-mary --region=us-west2 --project=ask-mary-486802 --limit=50` |
| Redeploy latest code | `gcloud builds submit --config=cloudbuild.yaml --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)` |
| Health check | `curl https://ask-mary-1030626458480.us-west2.run.app/health` |
