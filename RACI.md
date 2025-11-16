# RACI Matrix - Responsibility Assignment

**Version:** 1.0
**Status:** Pre-Production (P1 - Required before production)
**Last Updated:** 2025-11-16
**Owner:** Engineering Manager / CTO

---

## Table of Contents

1. [Overview](#overview)
2. [RACI Definitions](#raci-definitions)
3. [Team Structure](#team-structure)
4. [Development & Engineering](#development--engineering)
5. [Operations & SRE](#operations--sre)
6. [Trading & Risk](#trading--risk)
7. [Incident Response](#incident-response)
8. [Security & Compliance](#security--compliance)
9. [Decision-Making Authority](#decision-making-authority)
10. [Escalation Matrix](#escalation-matrix)

---

## Overview

### Purpose

This RACI (Responsible, Accountable, Consulted, Informed) matrix defines clear ownership and accountability for all operational activities in the Algo-Trade system.

### Benefits

- **Clear ownership** - No confusion about who does what
- **Faster decisions** - Know who has authority
- **Better accountability** - Track who is responsible
- **Reduced conflicts** - Defined consultation paths
- **Improved communication** - Know who to inform

### Document Scope

This matrix covers:
- Development and deployment
- Operations and maintenance
- Incident response
- Security and compliance
- Trading decisions
- Risk management

---

## RACI Definitions

| Letter | Role | Description |
|--------|------|-------------|
| **R** | **Responsible** | Does the work to complete the task |
| **A** | **Accountable** | Ultimately answerable for completion (only ONE per task) |
| **C** | **Consulted** | Provides input, two-way communication |
| **I** | **Informed** | Kept up-to-date, one-way communication |

### Rules

1. **Every task MUST have exactly ONE Accountable (A)** - No exceptions
2. **Responsible (R) must have Accountable (A)** - Someone oversees the work
3. **Consulted (C) is two-way** - Input is sought and considered
4. **Informed (I) is one-way** - Notification only, no input required
5. **Too many Cs slows decisions** - Limit consultation to essential stakeholders

---

## Team Structure

### Current Roles (Pre-Production)

| Role | Name | Primary Responsibility | Contact |
|------|------|----------------------|---------|
| **CTO** | TBD | Overall technical direction, production approval | cto@company.com |
| **Engineering Manager** | TBD | Development team, sprint planning, code quality | eng-mgr@company.com |
| **Senior Engineer** | TBD | Architecture, code reviews, technical decisions | senior@company.com |
| **Software Engineer** | TBD | Feature development, bug fixes, testing | dev@company.com |
| **DevOps/SRE** | TBD | Infrastructure, deployments, monitoring | devops@company.com |
| **Risk Officer** | TBD | Risk limits, kill-switches, trading approval | risk@company.com |
| **Quantitative Analyst** | TBD | Strategy design, backtesting, research | quant@company.com |
| **Trading Operations** | TBD | IBKR setup, order monitoring, daily operations | trading-ops@company.com |
| **Security Engineer** | TBD | Secrets management, security audits, compliance | security@company.com |
| **Product Manager** | TBD | Requirements, prioritization, stakeholder communication | pm@company.com |
| **Data Engineer** | TBD | Data quality, ingestion, storage | data-eng@company.com |

### Future Roles (Production)

Additional roles needed for production:
- **On-Call Engineer** (rotation)
- **Incident Commander** (rotation)
- **Compliance Officer**
- **DBA** (if using dedicated database)
- **Network Engineer** (for production infrastructure)

---

## Development & Engineering

### Code Development

| Task | CTO | Eng Mgr | Senior Eng | Software Eng | DevOps | Risk | Quant | Product |
|------|-----|---------|-----------|--------------|--------|------|-------|---------|
| **Feature Requirements** | I | C | C | R | I | C | C | **A** |
| **Technical Design** | C | I | **A** | R/C | C | I | C | I |
| **Code Implementation** | I | I | C | **A**/R | I | I | I | I |
| **Code Review** | I | I | **A**/R | R | I | I | I | I |
| **Unit Testing** | I | I | C | **A**/R | I | I | I | I |
| **Integration Testing** | I | C | C | **A**/R | R | I | I | I |
| **Documentation** | I | C | C | **A**/R | C | I | I | I |

**Notes:**
- Software Engineer is **A** (Accountable) for their own code
- Senior Engineer is **A** for code reviews
- Product Manager is **A** for requirements
- Testing is **shared responsibility** between Dev and QA

### Strategy Development

| Task | CTO | Eng Mgr | Senior Eng | Software Eng | DevOps | Risk | Quant | Product |
|------|-----|---------|-----------|--------------|--------|------|-------|---------|
| **Strategy Design** | I | I | C | C | I | C | **A**/R | C |
| **Backtesting** | I | I | C | R | I | C | **A**/R | I |
| **Parameter Tuning** | I | I | C | I | I | C | **A**/R | I |
| **Risk Validation** | I | I | I | I | I | **A**/R | C | I |
| **Production Approval** | **A** | C | C | I | C | R/C | C | C |

**Notes:**
- Quant team **owns** strategy design and backtesting
- Risk Officer **owns** risk validation
- CTO has **final approval** for production

### Deployment

| Task | CTO | Eng Mgr | Senior Eng | Software Eng | DevOps | Risk | Quant | Product |
|------|-----|---------|-----------|--------------|--------|------|-------|---------|
| **Staging Deployment** | I | I | C | R | **A**/R | I | I | I |
| **Production Deployment** | C | C | C | R | **A**/R | C | I | I |
| **Rollback Decision** | C | I | C | I | **A**/R | C | I | I |
| **Post-Deploy Verification** | I | I | C | R | **A**/R | I | I | I |

**Notes:**
- DevOps/SRE **owns** all deployments
- CTO must be **consulted** for production deployments
- Risk Officer must be **consulted** for production deployments

---

## Operations & SRE

### Daily Operations

| Task | CTO | Eng Mgr | DevOps | On-Call | Risk | Trading Ops | Data Eng |
|------|-----|---------|--------|---------|------|-------------|----------|
| **System Startup** | I | I | C | **A**/R | I | I | I |
| **System Shutdown** | I | I | C | **A**/R | C | I | I |
| **Health Monitoring** | I | I | C | **A**/R | I | I | I |
| **Log Review** | I | I | C | **A**/R | I | I | I |
| **Alert Response** | I | I | C | **A**/R | I | I | I |
| **Performance Tuning** | I | I | **A**/R | R | I | I | C |
| **Capacity Planning** | C | C | **A**/R | C | I | I | C |

**Notes:**
- On-Call Engineer is **A** for daily operations
- DevOps is **A** for performance and capacity

### Monitoring & Alerting

| Task | CTO | Eng Mgr | DevOps | On-Call | Risk | Trading Ops | Data Eng |
|------|-----|---------|--------|---------|------|-------------|----------|
| **Alert Configuration** | I | C | **A**/R | C | C | C | I |
| **Dashboard Creation** | I | I | **A**/R | C | C | C | C |
| **Metrics Definition** | I | C | R | I | C | C | **A**/C |
| **SLA Definition** | C | C | C | I | C | C | **A**/R |
| **Alert Triage** | I | I | C | **A**/R | I | I | I |

**Notes:**
- DevOps **owns** monitoring infrastructure
- Data Engineering **owns** metrics definitions

### Backup & Recovery

| Task | CTO | Eng Mgr | DevOps | On-Call | DBA | Data Eng |
|------|-----|---------|--------|---------|-----|----------|
| **Backup Strategy** | C | C | **A**/R | I | C | C |
| **Daily Backups** | I | I | C | R | **A**/R | C |
| **Backup Verification** | I | I | C | R | **A**/R | I |
| **Recovery Testing** | C | C | **A**/R | R | R | C |
| **Disaster Recovery** | **A** | C | R | R | R | C |

**Notes:**
- DBA **owns** daily backups (if using database)
- DevOps **owns** backup strategy and recovery
- CTO is **accountable** for disaster recovery

---

## Trading & Risk

### Pre-Trading

| Task | CTO | Risk | Quant | Trading Ops | DevOps | Software Eng |
|------|-----|------|-------|-------------|--------|--------------|
| **IBKR Account Setup** | I | C | I | **A**/R | I | I |
| **Credentials Management** | C | C | I | R | **A**/R | I |
| **Risk Limits Configuration** | C | **A**/R | C | R | I | I |
| **Pre-Live Testing** | C | C | C | R | C | **A**/R |
| **Go-Live Approval** | **A** | R/C | C | C | C | I |

**Notes:**
- Trading Ops **owns** IBKR setup
- Risk Officer **owns** risk limits
- CTO has **final approval** for go-live

### Live Trading

| Task | CTO | Risk | Quant | Trading Ops | DevOps | On-Call |
|------|-----|------|-------|-------------|--------|---------|
| **Daily Trading Start** | I | C | I | **A**/R | C | R |
| **Position Monitoring** | I | C | I | **A**/R | I | C |
| **PnL Monitoring** | I | **A**/C | C | R | I | C |
| **Risk Limit Monitoring** | I | **A**/R | C | C | I | C |
| **Kill-Switch Override** | **A** | R/C | C | I | I | I |
| **Daily Trading Stop** | I | C | I | **A**/R | C | R |

**Notes:**
- Trading Ops **owns** daily trading operations
- Risk Officer **owns** risk monitoring
- CTO has **final authority** on kill-switch overrides

### Risk Management

| Task | CTO | Risk | Quant | Trading Ops | Compliance |
|------|-----|------|-------|-------------|------------|
| **Risk Parameter Definition** | C | **A**/R | C | I | C |
| **Drawdown Limits** | C | **A**/R | C | I | C |
| **Position Limits** | C | **A**/R | C | I | C |
| **Exposure Limits** | C | **A**/R | C | I | C |
| **Kill-Switch Thresholds** | C | **A**/R | C | I | C |
| **Risk Reporting** | I | **A**/R | I | I | C |
| **Risk Exception Approval** | **A** | R/C | C | I | C |

**Notes:**
- Risk Officer **owns** all risk parameters
- CTO approves **risk exceptions**

---

## Incident Response

### Incident Management

| Task | CTO | Eng Mgr | DevOps | On-Call | Risk | Senior Eng |
|------|-----|---------|--------|---------|------|------------|
| **Alert Acknowledgment** | I | I | I | **A**/R | I | I |
| **Incident Commander** | I | I | C | **A**/R | C | C |
| **Technical Investigation** | I | I | C | R | I | **A**/R |
| **Fix Implementation** | I | I | C | R | I | **A**/R |
| **Communication to Stakeholders** | I | **A**/R | I | R | I | I |
| **Post-Incident Review** | C | **A**/R | C | R | C | R |

**Notes:**
- On-Call is **Incident Commander** (accountable for response)
- Senior Engineer **owns** technical investigation
- Engineering Manager **owns** communication and PIR

### Incident Severity Response

| Severity | Incident Commander | Accountable | Must Consult | Must Inform |
|----------|-------------------|-------------|--------------|-------------|
| **P0 (Critical)** | On-Call Engineer | CTO | Risk Officer, Senior Eng | All stakeholders |
| **P1 (High)** | On-Call Engineer | Eng Manager | Senior Eng, DevOps | CTO, Risk Officer |
| **P2 (Medium)** | On-Call Engineer | On-Call | DevOps | Eng Manager |
| **P3 (Low)** | Developer | Developer | Senior Eng | Eng Manager |

**Notes:**
- P0 incidents require **CTO** as accountable
- P0/P1 incidents require **Risk Officer** consultation
- All incidents require **post-incident review**

---

## Security & Compliance

### Security Operations

| Task | CTO | Security Eng | DevOps | Software Eng | Compliance |
|------|-----|-------------|--------|--------------|------------|
| **Secrets Management** | C | **A**/R | R | I | C |
| **Vault Setup** | C | **A**/R | R | I | I |
| **Credential Rotation** | I | **A**/R | R | I | C |
| **Security Audit** | C | **A**/R | C | I | C |
| **Vulnerability Scanning** | I | **A**/R | C | I | I |
| **Penetration Testing** | C | **A**/R | I | I | C |
| **Security Incident Response** | **A** | R | R | I | R |

**Notes:**
- Security Engineer **owns** all security operations
- CTO is **accountable** for security incidents
- DevOps **implements** security measures

### Compliance

| Task | CTO | Security Eng | Compliance | Risk | Legal |
|------|-----|-------------|------------|------|-------|
| **Compliance Policy** | C | C | **A**/R | C | C |
| **Regulatory Reporting** | I | I | **A**/R | R | C |
| **Audit Logging** | C | **A**/R | C | I | C |
| **Compliance Audit** | C | C | **A**/R | C | C |
| **SOC 2 Certification** | C | R | **A**/R | I | C |
| **FINRA Compliance** | C | I | **A**/R | R | C |

**Notes:**
- Compliance Officer **owns** all compliance activities
- Security Engineer **owns** audit logging
- Legal is **consulted** on regulatory matters

---

## Decision-Making Authority

### Authority Levels

| Decision Type | Authority | Must Consult | Examples |
|--------------|-----------|--------------|----------|
| **Level 1: Operational** | On-Call Engineer | DevOps, Senior Eng | Restart service, adjust logs, minor config |
| **Level 2: Tactical** | Engineering Manager | CTO, Risk Officer | Deploy to staging, change sprint priorities |
| **Level 3: Strategic** | CTO | Risk, Legal, Compliance | Go-live decision, major architecture change |
| **Level 4: Trading** | Risk Officer | CTO, Compliance | Risk limits, kill-switch override, trading halt |
| **Level 5: Business** | CEO | CTO, Risk, Legal | Budget, headcount, strategic direction |

### Decision Matrix

| Decision | Authority | Consulted | Informed | Approval Required |
|----------|-----------|-----------|----------|-------------------|
| **Code merge to main** | Senior Engineer | Software Engineer | Eng Manager | No |
| **Deploy to staging** | DevOps | Senior Engineer | Eng Manager | No |
| **Deploy to production** | DevOps | CTO, Risk Officer | All | Yes (CTO) |
| **Change risk limits** | Risk Officer | CTO, Quant | Compliance | Yes (CTO) |
| **Kill-switch override** | CTO | Risk Officer | All stakeholders | Yes (Risk) |
| **Start live trading** | CTO | Risk, Compliance, Legal | All stakeholders | Yes (All) |
| **Emergency halt** | On-Call / Risk | CTO | All stakeholders | No (post-facto approval) |
| **Rotate credentials** | Security Engineer | DevOps | CTO | No |
| **Security incident** | CTO | Security, Legal, Compliance | Board | Yes (Legal for external) |

---

## Escalation Matrix

### Escalation Paths

```
Issue Detected
    ↓
On-Call Engineer (L1)
  ├─ Can resolve? → Resolve & Document
  └─ Cannot resolve in 30 min? → Escalate to L2
      ↓
Senior Engineer (L2)
  ├─ Can resolve? → Resolve & Document
  └─ Cannot resolve in 1 hour? → Escalate to L3
      ↓
Engineering Manager + Risk Officer (L3)
  ├─ Can resolve? → Resolve & Document
  └─ Major impact / > 2 hours? → Escalate to L4
      ↓
CTO (L4)
  ├─ Can resolve? → Resolve & Document
  └─ Legal / PR / Board impact? → Escalate to L5
      ↓
CEO + Board (L5)
```

### Escalation Criteria

| Trigger | Escalation Level | Notify |
|---------|-----------------|--------|
| **Alert fired** | L1 (On-Call) | DevOps |
| **Can't resolve in 30 min** | L2 (Senior Eng) | Eng Manager |
| **Trading halted** | L3 (Eng Mgr + Risk) | CTO |
| **Kill-switch triggered** | L3 (Eng Mgr + Risk) | CTO |
| **Security breach** | L4 (CTO) | Legal, Compliance |
| **Incident > 2 hours** | L4 (CTO) | All stakeholders |
| **Major financial loss** | L5 (CEO) | Board |
| **Regulatory reporting** | L5 (CEO) | Board, Legal |

---

## Communication & Reporting

### Regular Reports

| Report | Frequency | Owner | Audience | Format |
|--------|-----------|-------|----------|--------|
| **Daily Operations** | Daily | Trading Ops | Risk Officer, Eng Manager | Email |
| **Weekly Performance** | Weekly | Quant Team | CTO, Risk Officer | Dashboard |
| **Sprint Review** | Bi-weekly | Eng Manager | CTO, Product | Meeting |
| **Monthly Risk Review** | Monthly | Risk Officer | CTO, Board | Report |
| **Quarterly Security Audit** | Quarterly | Security Engineer | CTO, Compliance | Report |
| **Annual Compliance** | Annual | Compliance | Board, Regulators | Formal Report |

### Meetings

| Meeting | Frequency | Organizer | Required Attendees | Optional |
|---------|-----------|-----------|-------------------|----------|
| **Daily Standup** | Daily | Eng Manager | Dev Team, DevOps | CTO |
| **Incident Review** | As needed | Eng Manager | Incident responders, CTO | Risk |
| **Sprint Planning** | Bi-weekly | Eng Manager | Dev Team, Product | CTO, Quant |
| **Risk Committee** | Monthly | Risk Officer | CTO, Quant, Trading Ops | Compliance |
| **All Hands** | Monthly | CEO | All employees | - |
| **Board Meeting** | Quarterly | CEO | Board, CTO, CFO | Others as needed |

---

## Handover & Knowledge Transfer

### Onboarding New Team Members

| Task | Owner | Support | Timeline |
|------|-------|---------|----------|
| **System Access** | DevOps | Security | Day 1 |
| **Codebase Tour** | Senior Engineer | Dev Team | Week 1 |
| **Documentation Review** | Eng Manager | Dev Team | Week 1 |
| **Shadow On-Call** | Current On-Call | DevOps | Week 2-3 |
| **First On-Call Shift** | New Member | Senior Eng (backup) | Week 4 |

### On-Call Handover

**Weekly Handover Checklist:**

- [ ] Review open incidents and action items
- [ ] Check system health metrics
- [ ] Verify alert configuration
- [ ] Test access to all systems (Vault, IBKR, Grafana)
- [ ] Review recent changes and deployments
- [ ] Update contact information
- [ ] Confirm escalation paths

**Handover Meeting:** 15 minutes every Sunday 9:00 AM

---

## Change Management

### Configuration Changes

| Change Type | Owner | Approval Required | Testing Required |
|------------|-------|-------------------|------------------|
| **Risk parameters** | Risk Officer | CTO | Yes (staging) |
| **Kill-switch thresholds** | Risk Officer | CTO | Yes (staging) |
| **Alert thresholds** | DevOps | Eng Manager | No |
| **Environment variables** | DevOps | Senior Engineer | Yes |
| **Secrets rotation** | Security Engineer | DevOps | Yes (staging) |
| **IBKR credentials** | Trading Ops | Risk Officer, CTO | Yes (paper trading) |

### Code Changes

| Change Type | Owner | Approval Required | Testing Required |
|------------|-------|-------------------|------------------|
| **Bug fix** | Software Engineer | Senior Engineer (code review) | Yes (unit tests) |
| **Feature** | Software Engineer | Senior Eng, Product | Yes (integration tests) |
| **Architecture change** | Senior Engineer | CTO | Yes (full test suite) |
| **Strategy change** | Quant Team | Risk Officer, CTO | Yes (backtesting) |
| **Infrastructure change** | DevOps | CTO | Yes (staging) |

---

## Review & Updates

### Document Maintenance

- **Owner:** Engineering Manager
- **Review Frequency:** Quarterly or after major org changes
- **Approvers:** CTO, Risk Officer
- **Communication:** All-hands announcement after updates

### Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-11-16 | Initial version | Engineering Team |

---

## Appendix

### Acronyms

- **RACI:** Responsible, Accountable, Consulted, Informed
- **CTO:** Chief Technology Officer
- **SRE:** Site Reliability Engineering
- **PIR:** Post-Incident Review
- **SLA:** Service Level Agreement

### Related Documents

- [RUNBOOK.md](./RUNBOOK.md) - Operational procedures
- [INCIDENT_PLAYBOOK.md](./INCIDENT_PLAYBOOK.md) - Incident response
- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md) - Security procedures
- [PRE_LIVE_CHECKLIST.md](./PRE_LIVE_CHECKLIST.md) - Go-live requirements

---

**Document Owner:** Engineering Manager
**Reviewers:** CTO, Risk Officer, Security Engineer
**Next Review:** 2025-02-16 (Quarterly)
**Status:** Draft → Review → Approved → Live

---

*This document is confidential and intended for internal use only.*
