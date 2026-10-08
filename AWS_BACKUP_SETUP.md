# AWS S3 Backup Setup - Complete Guide

## Step 1: Create S3 Bucket

### Via AWS CLI
```bash
aws s3 mb s3://sourcing-engine-backups-$(date +%s) --region us-east-1
```

### Via AWS Web Console
1. Go to: https://s3.console.aws.amazon.com/s3
2. Click **Create Bucket**
3. **Bucket name**: `sourcing-engine-backups-YOURNAME` (must be globally unique, lowercase, no underscores)
4. **Region**: `us-east-1` (or your preferred region)
5. **Block Public Access**: Keep default (checked)
6. Click **Create**

**Save the bucket name** - you'll need it for `.env`

---

## Step 2: Create IAM User with S3 Permissions

### Via AWS Web Console

#### 2a. Create User
1. Go to: https://console.aws.amazon.com/iam/
2. Click **Users** → **Create user**
3. **User name**: `sourcing-engine-backup`
4. Click **Next**

#### 2b. Set Permissions
1. Click **Attach policies directly**
2. Click **Create inline policy**
3. Click **JSON** tab and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::sourcing-engine-backups-YOURNAME/*"
    }
  ]
}
```

**Replace `sourcing-engine-backups-YOURNAME` with your actual bucket name**

4. Click **Review policy**
5. **Policy name**: `sourcing-engine-s3-backup`
6. Click **Create policy**
7. Click **Next** → **Create user**

#### 2c. Create Access Keys
1. Click the user `sourcing-engine-backup`
2. Go to **Security credentials** tab
3. Click **Create access key**
4. Select **Command Line Interface (CLI)**
5. Check **I understand...** box
6. Click **Next** → **Create access key**
7. **Copy and save both:**
   - Access Key ID
   - Secret Access Key
   - ⚠️ This is the ONLY time you can see the secret key!

---

## Step 3: Configure Local Environment

### 3a. Copy .env.example
```bash
cd /path/to/sourcing-engine
cp .env.example .env
```

### 3b. Edit .env with Your Credentials
```bash
# On Linux/Mac:
nano .env

# On Windows:
notepad .env
```

Fill in:
```env
S3_BUCKET=sourcing-engine-backups-YOURNAME
S3_PREFIX=sourcing-engine-backups
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Replace with your actual values from Step 2c**

### 3c. Protect .env (Never commit to git)
```bash
# Add to .gitignore (already there):
echo ".env" >> .gitignore

# Verify it won't be tracked:
git status
```

---

## Step 4: Test Backup & Restore

### 4a. Manual Backup
```bash
docker compose --profile backup run --rm backup backup
```

**Expected output:**
```
✓ Backed up to s3://sourcing-engine-backups-YOURNAME/sourcing-engine-backups/2026-10-08T22:15:30.123456Z/rate_library.csv
✓ Updated s3://sourcing-engine-backups-YOURNAME/sourcing-engine-backups/latest/rate_library.csv
```

### 4b. Verify in AWS Console
1. Go to: https://s3.console.aws.amazon.com/s3
2. Click your bucket
3. You should see folders:
   - `sourcing-engine-backups/latest/` → contains `rate_library.csv`
   - `sourcing-engine-backups/2026-10-08T22:15:30.123456Z/` → timestamped backup

### 4c. Test Restore
1. Delete or modify local `rate_library.csv`
2. Run restore:
```bash
docker compose --profile backup run --rm backup restore
```

**Expected output:**
```
✓ Restored from s3://sourcing-engine-backups-YOURNAME/sourcing-engine-backups/latest/rate_library.csv
  Saved to /data/rate_library.csv
```

3. Verify file is restored:
```bash
cat rate_library.csv
```

---

## Step 5: Automate Daily Backups

### Option A: Cron (Linux/Mac)

#### 5a. Install cron job
```bash
crontab -e
```

Add this line (runs daily at 2 AM):
```cron
0 2 * * * cd /path/to/sourcing-engine && docker compose --profile backup run --rm backup backup >> /tmp/sourcing-engine-backup.log 2>&1
```

**Replace `/path/to/sourcing-engine` with your actual directory**

#### 5b. Verify cron job
```bash
crontab -l
```

You should see the job listed.

#### 5c. Check logs
```bash
tail -f /tmp/sourcing-engine-backup.log
```

---

### Option B: Kubernetes CronJob (for production)

#### 5b. Create secret for AWS credentials
```bash
kubectl create secret generic aws-credentials \
  --from-literal=access-key-id=AKIAIOSFODNN7EXAMPLE \
  --from-literal=secret-access-key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
  -n sourcing-engine
```

#### 5c. Apply CronJob manifest
```bash
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sourcing-engine-backup
  namespace: sourcing-engine
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: sourcing-engine
          containers:
          - name: backup
            image: benjam90/sourcing-engine:latest
            command: ["python", "backup.py", "backup"]
            env:
            - name: S3_BUCKET
              value: "sourcing-engine-backups-YOURNAME"
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: access-key-id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aws-credentials
                  key: secret-access-key
            volumeMounts:
            - name: rate-data
              mountPath: /data
          volumes:
          - name: rate-data
            persistentVolumeClaim:
              claimName: sourcing-engine-data
          restartPolicy: OnFailure
EOF
```

#### 5d. Verify CronJob
```bash
kubectl get cronjob -n sourcing-engine
kubectl get jobs -n sourcing-engine  # Check for completed backup jobs
```

---

## Step 6: Production Deployment Checklist

- [ ] S3 bucket created
- [ ] IAM user created with S3 permissions
- [ ] Access keys generated and saved securely
- [ ] `.env` file configured with credentials
- [ ] `.env` added to `.gitignore` (never commit)
- [ ] Manual backup tested successfully
- [ ] Manual restore tested successfully
- [ ] Cron job created (Linux/Mac) OR CronJob deployed (Kubernetes)
- [ ] First automated backup completed and verified
- [ ] Rate library updates are being backed up

---

## Troubleshooting

### Backup fails: "NoCredentialsError"
**Solution:**
```bash
# Check .env file exists and has correct format
cat .env

# Verify credentials are set in environment
docker compose --profile backup run --rm backup bash -c 'echo "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID"'
```

### Backup fails: "InvalidBucketName"
**Solution:**
- Bucket names must be 3–63 characters
- Must be lowercase, numbers, hyphens only (no underscores)
- Must be globally unique across all AWS accounts

**Example valid names:**
- `sourcing-engine-backups-prod`
- `backup-se-company-2024`

### Backup fails: "Access Denied"
**Solution:**
1. Verify IAM user has correct policy attached
2. Check policy uses correct bucket name
3. Regenerate access keys if old ones are compromised

### Cron job not running
**Solution:**
```bash
# Check if cron daemon is running
ps aux | grep cron

# Check cron logs
sudo tail -f /var/log/syslog | grep CRON

# Verify cron job syntax
crontab -l
```

### S3 bucket access from GitHub Actions
If you want GitHub Actions to also backup (e.g., after successful build):

1. Add AWS secrets to GitHub:
   - Go to https://github.com/DEmusaer/sourcing-engine/settings/secrets/actions
   - Add: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

2. Update `.github/workflows/build.yml` to include backup step:

```yaml
- name: Backup to S3
  if: success()
  env:
    S3_BUCKET: sourcing-engine-backups-YOURNAME
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: docker compose --profile backup run --rm backup backup
```

---

## Cost Estimate (AWS)

- **S3 Storage**: ~$0.02/month for ~100 backups per month (5MB each)
- **Data Transfer**: Free (within AWS region)
- **API Calls**: <$0.01/month
- **Total**: ~$0.05–0.10/month

Free tier includes 5GB storage and 20K API calls/month.

---

## Security Best Practices

1. ✓ **Never commit `.env` to git** - use `.gitignore`
2. ✓ **Use IAM user** - not root AWS credentials
3. ✓ **Limit permissions** - only allow S3 access, not EC2/RDS/etc.
4. ✓ **Rotate keys regularly** - every 90 days recommended
5. ✓ **Use versioning** - S3 versioning enabled for extra safety
6. ✓ **Encrypt in transit** - S3 uses TLS by default
7. ✓ **Enable MFA** - on AWS root account only

---

## Next Steps

1. Create S3 bucket (Step 1)
2. Create IAM user (Step 2)
3. Configure `.env` (Step 3)
4. Test backup & restore (Step 4)
5. Set up cron or Kubernetes (Step 5)
6. Verify first automated backup (Step 6)
