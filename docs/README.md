# FundInv Solo — Documentation

## Index

| Document | Description |
|----------|-------------|
| [Architecture](./architecture.md) | System design overview, data flow, technology decisions |
| [Setup Guide](./setup.md) | Detailed environment configuration, database setup, deployment |
| [API Reference](./api.md) | Complete endpoint listing with methods, parameters, and responses |
| [Database Schema](./database.md) | ERD diagram, table descriptions, relationships, seed data |
| [Flows — Investor](./flows/investor.md) | Onboarding, wallet top-up, deposit/withdrawal, fund investing, trading |
| [Flows — Manager](./flows/manager.md) | Fund creation, investor assignment, trade execution, fund management |
| [Flows — Admin](./flows/admin.md) | User management, fund flow approval, reconciliation, fund targeting |
| [Flows — Operations](./flows/operations.md) | Fund flow processing: approve, complete, reject |
| [Flows — System](./flows/system.md) | Authentication, Stripe webhooks, email notifications, scheduled jobs |

---

## Quick Reference

### Start the Project

```bash
# One command
bash bin/run.sh

# Or manually
cd Server && uvicorn main:app --reload --port 8000 &
cd Client && npm run dev
```

### Seed Users

| Email | Password | Role |
|-------|----------|------|
| `admin@fundinv.com` | `admin123` | Admin |
| `manager@fundinv.com` | `admin123` | Manager |
| `operations@fundinv.com` | `admin123` | Operations |
| `investor@fundinv.com` | `investor123` | Investor |
| `alice@example.com` | `investor123` | Investor |

### API Base URL

- Backend: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`
