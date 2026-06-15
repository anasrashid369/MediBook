# MediBook — HIPAA-Inspired Secure Patient Appointment System

> Healthcare data breaches cost an average of $10.9M per incident.
> MediBook is built on the principle that security is not a feature —
> it is the foundation. Every architectural decision is documented
> and justifiable to a compliance auditor.

---

## The Problem

A small private clinic was managing patient appointments through
WhatsApp messages and a paper diary. After reading about hospital
ransomware attacks, the clinic owner needed a web system that was
not just functional — but provably secure, auditable, and designed
to protect sensitive patient data at every layer.

## The Solution

A security-first web application where patients book appointments
through a clean frontend, data flows through a hardened multi-layer
architecture, every access is logged, and no credentials exist
anywhere in the codebase.

---

## Live Architecture

```
Patient Browser
      ↓
[WAF] — blocks SQL injection, XSS, common attacks at edge
      ↓
[ALB] — Application Load Balancer (public, 2 AZs)
      ↓
[EC2 + Nginx] — serves frontend (public subnet)
      ↓
[API Gateway] — REST API /appointments endpoint
      ↓
[Lambda] — business logic (validates, processes, stores)
      ↓
[Secrets Manager] — credentials retrieved at runtime, never hardcoded
      ↓
[DynamoDB] — appointment storage (encrypted at rest, PITR enabled)
      ↓
[SNS] — sends confirmation email to patient
      ↓
[CloudTrail] — every API call logged for compliance audit
[CloudWatch] — alarms on errors, duration, 4XX/5XX rates
```

---

## Security Architecture

### Network Security

| Decision | What It Prevents |
|---|---|
| Custom VPC — no default VPC used | Eliminates shared default network risk |
| EC2 in public subnet, Lambda has no public access | Minimizes attack surface on business logic |
| ALB SG: accepts 80/443 from internet | Only entry point to the system |
| EC2 SG: accepts port 80 from ALB SG only | EC2 never directly reachable from internet |
| EC2 SG: accepts port 22 from specific IP only | SSH locked to admin IP, not open to world |
| Lambda SG: no inbound rules | Lambda unreachable from network directly |
| Two public subnets across 2 AZs | High availability, no single point of failure |

### Application Security

| Decision | What It Prevents |
|---|---|
| WAF Core Rule Set enabled | Blocks OWASP Top 10 attacks |
| WAF SQL injection rule set enabled | Blocks database injection attacks |
| WAF attached to ALB | Attacks blocked before reaching EC2 |
| Input validation in Lambda (server-side) | Cannot be bypassed like client-side only |
| Email regex validation | Malformed data rejected |
| Phone numeric validation | Injection via phone field blocked |
| Past date validation | Invalid booking data rejected |

### Data Security

| Decision | What It Prevents |
|---|---|
| DynamoDB encryption at rest | Data unreadable if storage compromised |
| DynamoDB PITR enabled | Restore to any second in last 35 days |
| Secrets Manager for all credentials | Zero hardcoded secrets in codebase |
| Secrets retrieved at Lambda runtime | Credentials never in environment variables |
| No raw errors exposed in API responses | Internal architecture not leaked to attackers |

### Compliance and Auditability

| Decision | What It Enables |
|---|---|
| CloudTrail enabled | Every AWS API call logged permanently |
| MediBook-AuditLog DynamoDB table | Application-level audit trail |
| Every booking writes an audit entry | Can answer: who booked what and when |
| CloudWatch alarms on errors and 5XX | Immediate notification of system issues |

### IAM Security

Lambda role permissions — least privilege:

```
CAN:  dynamodb:PutItem on MediBook-Appointments
CAN:  dynamodb:GetItem on MediBook-Appointments
CAN:  dynamodb:PutItem on MediBook-AuditLog
CAN:  secretsmanager:GetSecretValue on medibook/db-config
CAN:  sns:Publish on MediBook-Confirmations
CAN:  logs:CreateLogGroup, CreateLogStream, PutLogEvents

CANNOT: Delete DynamoDB tables
CANNOT: List S3 buckets
CANNOT: Create IAM roles
CANNOT: Access any other AWS service
```

---

## WAF SQL Injection Test

Sent a simulated SQL injection attack to verify WAF blocks it:

```bash
curl -X POST https://ALB_DNS/appointments \
  -d "patient_name=Anas' OR '1'='1"
```

**Result: HTTP 403 Forbidden**
WAF blocked the attack before it reached EC2 or the database.
Screenshot of the 403 response is in `/images/waf-block.png`.

---

## Project Structure

```
medibook/
├── cloudformation/
│   └── template.yaml          # Full IaC — VPC, IAM, DynamoDB, SNS, Secrets
├── lambda/
│   └── appointment_processor/
│       └── lambda_function.py # Booking processor — validation, storage, alerts
├── frontend/
│   └── index.html             # Patient booking UI — HTML/CSS/JS
├── security/
│   └── security-audit.md      # Full security decision log
├── images/
│   ├── architecture.png       # System architecture diagram
│   ├── waf-block.png          # WAF blocking SQL injection
│   ├── appointment-form.png   # Live booking form
│   ├── confirmation-email.png # SNS confirmation email
│   └── dynamodb-records.png   # DynamoDB appointment records
└── README.md
```

---

## AWS Services Used

| Service | Role | Why This Service |
|---|---|---|
| VPC | Network isolation | Custom network, no shared defaults |
| EC2 + Nginx | Frontend hosting | Full control, free tier eligible |
| ALB | Load balancing + SSL termination | HA across 2 AZs, WAF attachment point |
| WAF | Edge security | Managed rule sets, zero config attacks blocked |
| API Gateway | REST API | Managed, scalable, no server needed |
| Lambda | Business logic | Serverless, least privilege, scales to zero |
| DynamoDB | Data storage | Serverless, encrypted, PITR, free tier |
| Secrets Manager | Credential storage | Zero hardcoded secrets anywhere |
| SNS | Patient notifications | Managed pub/sub, email delivery |
| CloudTrail | Compliance logging | Every API call audited |
| CloudWatch | Observability | Alarms, logs, metrics in one place |
| IAM | Access control | Least privilege on every resource |
| CloudFormation | Infrastructure as Code | Entire stack in one command |

---

## Patient Booking Flow

```
1. Patient opens http://ALB_DNS in browser
2. WAF scans the request — allows clean traffic
3. ALB routes to EC2 Nginx — serves index.html
4. Patient fills form: name, email, phone, date, time, doctor, reason
5. JavaScript validates fields client-side
6. fetch() sends POST to API Gateway /appointments
7. API Gateway triggers Lambda
8. Lambda validates all fields server-side (second layer)
9. Lambda retrieves config from Secrets Manager
10. Lambda writes appointment to DynamoDB (status: CONFIRMED)
11. Lambda writes audit entry to MediBook-AuditLog
12. Lambda publishes confirmation to SNS
13. Patient receives confirmation email within 60 seconds
14. Lambda returns appointment_id and details to frontend
15. Frontend shows confirmation screen with reference ID
16. CloudTrail logs the entire API call
```

---

## What I Would Add With a Production Budget

| Feature | Service | Why |
|---|---|---|
| HTTPS | AWS Certificate Manager | Encrypt data in transit |
| Patient authentication | Amazon Cognito | Patients log in, view own appointments |
| KMS customer-managed keys | AWS KMS | Full control over encryption keys |
| DDoS protection | AWS Shield Standard | Always-on DDoS mitigation |
| VPC Flow Logs | VPC | Log all network traffic for forensics |
| Threat detection | Amazon GuardDuty | ML-based threat detection |
| Compliance rules | AWS Config | Continuous compliance monitoring |
| Auto scaling | EC2 Auto Scaling Group | Handle traffic spikes automatically |
| Multi-region DR | Route 53 + Global Tables | Zero downtime across region failures |
| CI/CD pipeline | CodePipeline + CodeDeploy | Automated deployments on git push |

---

## Lessons Learned

- WAF must be attached to the ALB — not the API Gateway — to protect
  the entire ingress layer including the frontend itself
- CORS headers must be returned by Lambda on EVERY response including
  errors, otherwise the browser silently blocks the response
- OPTIONS preflight must be handled in Lambda before any other logic
  otherwise browser fetch() fails before the real request is sent
- Security groups are stateful — return traffic is automatically
  allowed without an explicit outbound rule
- Secrets Manager keys are case-sensitive — tableName is not
  the same as table_name in JSON parsing

---

## Author

**Muhammad Anas Rashid**
AWS Certified Solutions Architect Associate (SAA-C03)

*Project 2 of 3 in my AWS Portfolio*
*Project 1: RetailSync — Serverless Inventory Pipeline*
*Project 3: ShopReady — Multi-Region Disaster Recovery (Coming Soon)*
