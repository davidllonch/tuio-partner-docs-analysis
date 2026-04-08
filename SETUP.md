# KYC/KYB App — Setup Guide

## First-time deployment on the server

### 1. Transfer files to the server

From your local machine:
```bash
scp -P 2222 -r ./kyc-app agentellonch@42labs.es:~/
```

### 2. SSH into the server
```bash
ssh -p 2222 agentellonch@42labs.es
cd ~/kyc-app
```

### 3. Create the root .env file
```bash
cp .env.example .env
nano .env
# Set: DB_PASSWORD=<a strong random password>
```

### 4. Create the backend .env file
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Fill in these values:
| Variable | Value |
|----------|-------|
| `JWT_SECRET_KEY` | A random 32+ character string |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (sk-ant-...) |
| `OPENAI_API_KEY` | Your OpenAI API key (sk-...) |
| `RESEND_API_KEY` | Your Resend API key (re_...) |
| `EMAIL_FROM_ADDRESS` | e.g. `kyc@tuio.com` (must be verified in Resend) |

### 5. Run the deploy script
```bash
bash deploy.sh
```

This will:
- Create the Docker network if needed
- Build all Docker images
- Start the PostgreSQL database
- Run database migrations automatically
- Start all services

### 6. Create the first analyst account
```bash
docker compose exec backend python create_analyst.py "analyst@tuio.com" "Analyst Name" "your-password"
```

### 7. Verify it's running
- Partner form: https://partnerdocs.tuio.com
- Analyst login: https://partnerdocs.tuio.com/login

---

## Updating the app (after code changes)

```bash
ssh -p 2222 agentellonch@42labs.es
cd ~/kyc-app
git pull  # if using git, otherwise re-upload changed files
bash deploy.sh
```

---

## Useful commands

```bash
# View live logs
docker compose logs -f backend
docker compose logs -f frontend

# Restart a single service
docker compose restart backend

# Stop everything
docker compose down

# Stop and delete ALL data (careful!)
docker compose down -v

# Run a one-off command in the backend container
docker compose exec backend python create_analyst.py email name password

# Check running containers
docker compose ps
```

---

## DNS setup

Add a DNS A record:
```
partnerdocs.tuio.com  →  <public IP of 42labs.es>
```

Traefik will automatically obtain an SSL certificate from Let's Encrypt once the DNS record is pointing to the server.

---

## Before going live checklist

- [ ] DNS record created for `partnerdocs.tuio.com`
- [ ] `EMAIL_FROM_ADDRESS` domain verified in Resend dashboard
- [ ] Test partner form: submit with a PDF + image → check that `legal@tuio.com` receives the email
- [ ] Test analyst login → dashboard → view submission → download document
- [ ] Test re-analyse function from analyst dashboard
- [ ] Confirm Docker group access for `agentellonch` (needed to run Docker commands)
