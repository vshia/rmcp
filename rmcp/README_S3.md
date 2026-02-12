# S3 Service Account Setup (No MFA Required)

This guide creates a programmatic IAM user with S3 access that is **not** subject to MFA enforcement.

The MFA deny policy is applied via the `logista-prod-users` IAM group. By keeping this service account out of that group, it can authenticate with access keys alone.

## Prerequisites

- AWS CLI configured with admin credentials (with MFA session active)
- Your AWS account ID: `526261729362`

## Step 1: Create the IAM User

```bash
aws iam create-user \
  --user-name logista-prod-s3-service \
  --path /service-accounts/ \
  --tags Key=Project,Value=Logista Key=Environment,Value=prod Key=ManagedBy,Value=manual Key=Purpose,Value="S3 programmatic access"
```

## Step 2: Create the IAM Policy

Choose the buckets this account should access. Your current buckets are:

| Bucket | Purpose |
|--------|---------|
| `logista-response` | Main project bucket |
| `logista-prod-staging-private` | Staging client private files |
| `logista-prod-staging-public` | Staging client public assets |
| `logista-prod-fsdr-private` | FSDR client private files |
| `logista-prod-fsdr-public` | FSDR client public assets |
| `logista-prod-static` | Static deployment artifacts |
| `logista-prod-static-latest` | Latest static assets |

### Option A: Access to all logista buckets

```bash
aws iam create-policy \
  --policy-name logista-prod-s3-service-access \
  --description "S3 access for service account - all logista buckets" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowS3BucketAccess",
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectVersion"
        ],
        "Resource": [
          "arn:aws:s3:::logista-*",
          "arn:aws:s3:::logista-*/*"
        ]
      }
    ]
  }'
```

### Option B: Access to a specific bucket only

Replace `BUCKET_NAME` with the bucket from the table above:

```bash
aws iam create-policy \
  --policy-name logista-prod-s3-service-access \
  --description "S3 access for service account - specific bucket" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowS3BucketAccess",
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetObjectVersion"
        ],
        "Resource": [
          "arn:aws:s3:::BUCKET_NAME",
          "arn:aws:s3:::BUCKET_NAME/*"
        ]
      }
    ]
  }'
```

## Step 3: Attach the Policy to the User

```bash
aws iam attach-user-policy \
  --user-name logista-prod-s3-service \
  --policy-arn arn:aws:iam::526261729362:policy/logista-prod-s3-service-access
```

## Step 4: Create Access Keys

```bash
aws iam create-access-key \
  --user-name logista-prod-s3-service
```

Save the `AccessKeyId` and `SecretAccessKey` from the output. The secret is only shown once.

## Step 5: Verify It Works

```bash
# Configure a named profile with the new credentials
aws configure --profile logista-ai-test

# Test access (replace with your bucket name)
aws s3 ls s3://logista-ai-test --profile logista-ai-test
```

## Important Notes

- **Do NOT add this user to the `logista-prod-users` group** — that group enforces MFA and will block programmatic access.
- Store the access keys securely (e.g., AWS Secrets Manager, environment variables in a CI system, etc.). Never commit them to source control.
- Rotate the access keys periodically. AWS recommends every 90 days:

```bash
# Create new key
aws iam create-access-key --user-name logista-prod-s3-service

# Update your application with the new key, then delete the old one
aws iam delete-access-key \
  --user-name logista-prod-s3-service \
  --access-key-id OLD_ACCESS_KEY_ID
```

## Cleanup

To remove the service account:

```bash
# Delete access keys first
aws iam list-access-keys --user-name logista-prod-s3-service
aws iam delete-access-key \
  --user-name logista-prod-s3-service \
  --access-key-id ACCESS_KEY_ID

# Detach policy
aws iam detach-user-policy \
  --user-name logista-prod-s3-service \
  --policy-arn arn:aws:iam::526261729362:policy/logista-prod-s3-service-access

# Delete policy
aws iam delete-policy \
  --policy-arn arn:aws:iam::526261729362:policy/logista-prod-s3-service-access

# Delete user
aws iam delete-user --user-name logista-prod-s3-service
```
