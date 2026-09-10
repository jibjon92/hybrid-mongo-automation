# Enterprise Hybrid-Cloud MongoDB Disaster Recovery & Automated S3 Pipeline

![Ansible](https://img.shields.io/badge/Ansible-E50000?style=for-the-badge&logo=ansible&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![AWS S3](https://img.shields.io/badge/Amazon_S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Red_Hat_Enterprise_Linux-EE0000?style=for-the-badge&logo=redhat&logoColor=white)

An automated, production-grade hybrid-cloud disaster recovery (DR) and backup pipeline for MongoDB replica sets. Managed end-to-end via **Ansible**, orchestrated with **systemd timers**, executed with **Python (`boto3`)** and **MongoDB Database Tools**, and backed up offsite to **Amazon S3** with **Ansible Vault AES-256** credential encryption.

---

## 📋 Table of Contents
1. [Architecture & Topology](#-architecture--topology)
2. [Key Features](#-key-features)
3. [Repository Structure](#-repository-structure)
4. [Prerequisites & IAM Requirements](#-prerequisites--iam-requirements)
5. [Deployment Guide](#-deployment-guide)
6. [Operational Runbooks](#-operational-runbooks)
   - [Runbook 1: Backup Operations & Verification](#runbook-1-backup-operations--verification)
   - [Runbook 2: Disaster Recovery & Restore Procedure](#runbook-2-disaster-recovery--restore-procedure)
   - [Runbook 3: Security Hardening & Credential Rotation](#runbook-3-security-hardening--credential-rotation)
7. [Validation & Test Results](#-validation--test-results)
8. [Troubleshooting & Edge Cases](#-troubleshooting--edge-cases)

---

## 📐 Architecture & Topology

The environment consists of a 3-node MongoDB Replica Set (`rs0`) deployed across an on-premises local network and AWS Cloud to ensure high availability and geo-redundancy.


```text
                        +----------------------------------+
                        |       ANSIBLE CONTROL NODE       |
                        |  - Playbooks & Encrypted Vault   |
                        |  - Manages Deployment via SSH    |
                        +----------------------------------+
                                         |
                    +--------------------+--------------------+
                    | Ansible Deploy                          | Ansible Deploy
                    v                                         v
+---------------------------------------+   +---------------------------------------+
|          LOCAL PRIMARY NODE           |   |       LOCAL SECONDARY (mongo1)        |
|  - IP: 192.168.211.130                |   |  - IP: 192.168.211.129                |
|  - Role: Primary (Read/Write)         |   |  - Role: Backup Executor              |
|  - Data Store & Target for DR         |   |  - Systemd Timer (02:00 AM)           |
+---------------------------------------+   +---------------------------------------+
       ^                                                |
       | Replicates Data                                | Streams Compressed
       v                                                | Archive over TLS
+---------------------------------------+               v
|           AWS EC2 SECONDARY           |   +---------------------------------------+
|  - Region: eu-west-1                  |   |               AMAZON S3               |
|  - Role: Secondary/Tie-breaker        |   |  - Offsite Backup Bucket              |
|  - Geo-Redundant Node                 |   |  - Encrypted Storage                  |
+---------------------------------------+   +---------------------------------------+
```


### Cluster Specifications

| Host / Node Name | IP Address / Location | Mongo Role | Deployment Function | OS / Specs |
| :--- | :--- | :--- | :--- | :--- |
| **Control Node** | Local LAN | N/A | Ansible Orchestration & IaC Master | RHEL 9 / 2 vCPU, 4GB |
| **Primary Node** | `192.168.211.130` | `PRIMARY` | Active Application Read/Write Target | RHEL 9 / 2 vCPU, 4GB |
| **mongo1** | `192.168.211.129` | `SECONDARY` | Backup Executor (Runs systemd & S3 scripts) | RHEL 9 / 2 vCPU, 4GB |
| **AWS EC2 Node** | `AWS eu-west-1` | `SECONDARY` | Offsite Replica & Quorum Tie-Breaker | Amazon Linux 2023 / t3.medium |
| **AWS S3** | `s3://<backup-bucket>` | N/A | Immutable Offsite Backup Storage | AWS Cloud Storage |

---

## 📁 Repository Structure

```text
hybrid-mongo-automation/
├── site.yml                  # Master Ansible orchestration playbook
├── deploy_backup.yml         # Targeted playbook for backup & DR pipeline
├── backup_to_s3.py           # Automated backup script (executes mongodump & S3 upload)
├── restore_from_s3.py        # Disaster recovery restore script (S3 download & mongorestore)
├── vars/
│   └── vault.yml             # AES-256 encrypted variables (AWS credentials)
├── .gitignore                # Git exclusion rules (.vault_pass, temp files, keys)
├── README.md                 # Production architecture documentation and runbooks
├── mongo-backup.service      # Systemd service unit configuration
└── mongo-backup.timer        # Systemd timer unit configuration
```

---

## 🔑 Prerequisites & IAM Requirements

### System Requirements
1. **Ansible Control Node:** Python 3.9+, Ansible 2.14+, `ansible-vault`.
2. **Target Node (`mongo1`):** Python 3.9+, `pip3 install boto3`, `mongodb-database-tools` (`mongodump`, `mongorestore`).
3. **Network Connectivity:** Unrestricted SSH access from Control Node to target hosts; MongoDB port `27017` open across nodes; HTTPS (port 443) outbound to AWS S3 endpoints.

### Minimum AWS IAM Policy
The AWS IAM user or execution role requires the following minimum policy for S3 operations:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "MongoDBBackupS3Permissions",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-mongo-backup-bucket-name",
                "arn:aws:s3:::your-mongo-backup-bucket-name/*"
            ]
        }
    ]
}
````


🚀 
Step 1: Setup Vault Credentials

    On the Ansible Control Node inside ~/hybrid-mongo-automation:
    Bash

    ansible-vault create vars/vault.yml

    Define the following variables inside the encrypted editor:
    YAML

    vault_aws_access_key_id: "AKIAYOURACTUALAWSKEY"
    vault_aws_secret_access_key: "YourActualSecretAccessKeyString"

    Configure your vault password file for automated execution:
    Bash

    echo "YourVaultPassword" > ~/.vault_pass
    chmod 600 ~/.vault_pass

Step 2: Execute Ansible Deployment Playbook

Run the Ansible playbook targeting mongo1 to deploy dependencies, scripts, and systemd timers:
Bash

ansible-playbook deploy_backup.yml --vault-password-file ~/.vault_pass

📖 Operational Runbooks
Runbook 1: Backup Operations & Verification
Trigger a Manual Backup

To execute an immediate backup on demand without waiting for the scheduled 02:00 AM window:
Bash

ssh ec2-user@192.168.211.129
sudo systemctl start mongo-backup.service

Monitor Backup Systemd Logs

Inspect real-time service logs via journalctl:
Bash

sudo journalctl -u mongo-backup.service -f --no-pager

Verify Systemd Timer Status
Bash

systemctl status mongo-backup.timer
systemctl list-timers mongo-backup.timer

Runbook 2: Disaster Recovery & Restore Procedure

    ⚠️ CRITICAL REQUIREMENT: mongorestore writes MUST always target the Primary node (192.168.211.130). Executing restore commands against a Secondary node (127.0.0.1 on mongo1) will result in a NotWritablePrimary error.

Step 1: Prepare Restore Script on Execution Host

Ensure restore_from_s3.py exists on mongo1 (or Control Node):
Bash

ssh ec2-user@192.168.211.129
chmod +x ~/restore_from_s3.py

Step 2: Execute Disaster Recovery Restore

Set the S3 bucket variables and pass MONGO_URI pointing directly to the Primary IP (192.168.211.130):
Bash

export S3_BUCKET_NAME="your-mongo-backup-bucket-name"
export AWS_REGION="eu-west-1"
export MONGO_URI="mongodb://192.168.211.130:27017"

python3 ~/restore_from_s3.py

Step 3: Validate Restored Data on Primary Node

Query the Primary node directly to verify collection records and document integrity:
Bash

mongosh "mongodb://192.168.211.130:27017/portfolio" --eval "db.demo.find()"

Expected Verification Output:
JavaScript

[
  {
    _id: ObjectId("66e01a2b8f3c4a123456789a"),
    cluster: "rs0-hybrid",
    status: "replicated",
    timestamp: ISODate("2026-09-10T10:00:00.000Z")
  }
]

Runbook 3: Security Hardening & Credential Rotation

    Edit the encrypted vault file on the Control Node:
    Bash

    ansible-vault edit vars/vault.yml --vault-password-file ~/.vault_pass

    Update vault_aws_access_key_id and vault_aws_secret_access_key.

    Redeploy the configuration to update systemd service environment variables:
    Bash

    ansible-playbook deploy_backup.yml --vault-password-file ~/.vault_pass

🧪 Validation & Test Results

    Automated Scheduled Backup: Systemd timer activated mongo-backup.service at scheduled 02:00 AM. Compressed .gz archives successfully landed in S3 under backups/.

    Secondary Node S3 Stream: Confirmed that mongodump ran against local secondary instance (127.0.0.1:27017 on mongo1) without affecting write throughput on Primary 192.168.211.130.

    Primary Recovery Testing: Disastrous data corruption was simulated, followed by execution of restore_from_s3.py. The script identified the newest snapshot, fetched it from S3, and performed a full --drop restore to 192.168.211.130. Full data consistency was validated via mongosh.

❓ Troubleshooting & Edge Cases
1. NotWritablePrimary Error during Restore

    Cause: mongorestore was executed against 127.0.0.1 on a Secondary node (mongo1).

    Fix: Export MONGO_URI="mongodb://192.168.211.130:27017" to route restore write traffic directly to the Primary instance.

2. Systemd Backup Missed Schedule

    Cause: Host server was powered off at 02:00 AM.

    Fix: Timer uses Persistent=true. Systemd automatically triggers missed executions on startup.

3. S3 403 Forbidden / AccessDenied

    Cause: Missing IAM permissions or incorrect bucket name in vars/vault.yml.

    Fix: Verify s3:PutObject and s3:ListBucket IAM policies and test bucket access using AWS CLI.
