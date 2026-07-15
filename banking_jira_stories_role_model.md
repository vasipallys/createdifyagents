# 🏦 Exemplary Jira User Stories for Banking

> **Role Model Collection** — These stories follow industry best practices: clear persona-driven narratives, granular scope, testable acceptance criteria, and business value articulation.

---

## Table of Contents
1. [Digital Banking & Mobile App](#1-digital-banking--mobile-app)
2. [Payments & Transfers](#2-payments--transfers)
3. [Lending & Credit](#3-lending--credit)
4. [Fraud & Risk Management](#4-fraud--risk-management)
5. [Compliance & Regulatory](#5-compliance--regulatory)
6. [Corporate Banking](#6-corporate-banking)
7. [Customer Onboarding & KYC](#7-customer-onboarding--kyc)
8. [Wealth Management](#8-wealth-management)
9. [Story Writing Best Practices](#9-story-writing-best-practices-checklist)

---

## 1. Digital Banking & Mobile App

---

### Story DB-001: Biometric Login
**Priority:** High | **Story Points:** 5 | **Sprint:** Sprint 12

**User Story:**
> As a **retail banking customer**,  
> I want to **log in to the mobile app using Face ID or fingerprint**,  
> So that **I can access my accounts quickly without typing passwords**.

**Business Value:**
- Reduce login friction by 40% (measured via app analytics)
- Decrease password-reset support tickets by 25%
- Improve CSAT score for mobile app login experience

**Acceptance Criteria:**
```
Given I am on the mobile app login screen
When I tap "Use Face ID" (iOS) or "Use fingerprint" (Android)
And my biometric is successfully verified
Then I am authenticated and redirected to my account dashboard

Given I have enabled biometric login
When I open the app after 5 minutes of inactivity
Then I am prompted for biometric re-authentication

Given biometric authentication fails 3 consecutive times
When the 3rd attempt fails
Then I am redirected to username/password login
And a security alert is logged

Given I am on a device without biometric hardware
When I view the login screen
Then the biometric option is not displayed
```

**Definition of Done:**
- [ ] Unit tests >80% coverage
- [ ] Security review passed (OWASP Mobile Top 10)
- [ ] Accessibility audit passed (WCAG 2.1 AA)
- [ ] Performance: login <2 seconds
- [ ] iOS & Android parity verified

**Labels:** `mobile`, `authentication`, `security`, `ux`
**Dependencies:** DB-004 (Device Binding API)

---

### Story DB-002: Real-Time Balance Widget
**Priority:** Medium | **Story Points:** 3 | **Sprint:** Sprint 14

**User Story:**
> As a **checking account holder**,  
> I want to **see my real-time balance on my phone's home screen via a widget**,  
> So that **I can monitor my spending without opening the app**.

**Business Value:**
- Increase daily active engagement by 15%
- Reduce "check balance" in-app sessions (freeing server load)
- Differentiate from competitor apps lacking widget support

**Acceptance Criteria:**
```
Given I have added the bank widget to my home screen
When I view the widget
Then I see my primary checking account balance
And the timestamp of the last update

Given my balance changes due to a transaction
When the core banking system publishes the update
Then the widget refreshes within 30 seconds

Given I tap the widget
When the tap is registered
Then the mobile app opens to the account details screen

Given I have multiple checking accounts
When I configure the widget
Then I can select which account to display
```

**Labels:** `mobile`, `widget`, `engagement`, `ios`, `android`

---

### Story DB-003: Scheduled Transfer Recurrence
**Priority:** High | **Story Points:** 8 | **Sprint:** Sprint 15

**User Story:**
> As a **customer with recurring bills**,  
> I want to **set up recurring transfers (weekly, bi-weekly, monthly)**,  
> So that **I can automate my rent and utility payments without manual intervention**.

**Business Value:**
- Increase customer retention by reducing churn from payment friction
- Drive adoption of digital channels (target: +20% digital payment share)
- Reduce teller-assisted transaction costs

**Acceptance Criteria:**
```
Given I am setting up a new transfer
When I select "Recurring" as the transfer type
Then I can choose: Weekly, Bi-weekly, Monthly, or Custom

Given I select "Monthly" recurrence
When I configure the transfer
Then I can select the day of the month (1-28 or "last business day")
And set an end date or number of occurrences

Given a recurring transfer is due on a weekend or holiday
When the scheduled date arrives
Then the transfer executes on the next business day
And I receive a notification of the date adjustment

Given a recurring transfer fails due to insufficient funds
When the transfer attempt occurs
Then the transfer is skipped
And I receive an email + push notification
And the recurrence continues for the next scheduled date

Given I want to cancel a recurring transfer
When I navigate to "Scheduled Transfers" and select "Cancel"
Then all future occurrences are cancelled
And already-processed transfers remain unchanged
And I receive a confirmation notification
```

**Labels:** `transfers`, `payments`, `automation`, `retail`
**Dependencies:** DB-005 (Notification Service v2)

---

## 2. Payments & Transfers

---

### Story PY-001: Instant P2P Payment via Mobile Number
**Priority:** High | **Story Points:** 13 | **Sprint:** Sprint 18

**User Story:**
> As a **personal banking customer**,  
> I want to **send money to anyone using just their mobile number**,  
> So that **I can split bills and repay friends without knowing their bank details**.

**Business Value:**
- Compete with fintech P2P apps (Venmo, Zelle)
- Acquire 500K new active users in Q3
- Generate interchange revenue from merchant P2P volume

**Acceptance Criteria:**
```
Given I am on the "Send Money" screen
When I enter a mobile number
And the recipient is registered with the bank
Then I see their name and can proceed with the transfer

Given I enter a mobile number not registered with the bank
When I confirm the transfer
Then the recipient receives an SMS with a secure link
And they can claim the funds by registering or providing account details
And unclaimed funds are auto-returned after 7 days

Given I initiate a P2P transfer
When I confirm the amount and recipient
Then the funds are debited from my account immediately
And the recipient receives the funds within 30 seconds
And both parties receive transaction confirmations

Given I send money to the wrong mobile number
When I report the issue within 10 minutes
And the funds have not been claimed
Then I can cancel the transfer
And the funds are returned to my account
```

**Labels:** `p2p`, `payments`, `real-time`, `acquisition`
**Non-Functional Requirements:**
- 99.99% uptime during business hours
- <500ms API response time for transfer initiation
- PCI-DSS Level 1 compliance

---

### Story PY-002: Cross-Border SWIFT Transfer Tracking
**Priority:** Medium | **Story Points:** 8 | **Sprint:** Sprint 20

**User Story:**
> As a **corporate treasury manager**,  
> I want to **track my international SWIFT transfers in real-time with status updates**,  
> So that **I can reconcile payments and inform vendors of expected receipt dates**.

**Business Value:**
- Reduce WU (wire inquiry) calls to customer service by 35%
- Improve corporate client NPS by 12 points
- Reduce payment reconciliation time from 2 days to real-time

**Acceptance Criteria:**
```
Given I have initiated a SWIFT transfer
When I view the transfer details
Then I see a status tracker: Initiated → Sent → Acknowledged → Settled
And each status shows the timestamp and correspondent bank

Given the transfer status changes
When the SWIFT gpi API pushes an update
Then I receive a push notification and email
And the status tracker updates automatically

Given I am viewing a completed transfer
When I click "Download Confirmation"
Then I receive a PDF MT103 confirmation with UETR reference
And the document is digitally signed by the bank

Given I have 50+ pending international transfers
When I view the "International Payments" dashboard
Then I can filter by status, currency, date range, and beneficiary
And export the filtered list to Excel
```

**Labels:** `corporate`, `swift`, `international`, `tracking`, `gpi`

---

## 3. Lending & Credit

---

### Story LN-001: Pre-Approved Loan Offer Display
**Priority:** High | **Story Points:** 5 | **Sprint:** Sprint 11

**User Story:**
> As a **credit card holder with good standing**,  
> I want to **see personalized pre-approved loan offers in my dashboard**,  
> So that **I can access credit quickly when I need it without a hard inquiry**.

**Business Value:**
- Increase personal loan origination by $50M in Q4
- Improve cross-sell ratio from 1.2 to 2.0 products per customer
- Reduce cost of acquisition vs. outbound marketing by 60%

**Acceptance Criteria:**
```
Given I am eligible for a pre-approved loan
When I log in to online banking
Then I see a personalized offer card on my dashboard
With: loan amount, interest rate, monthly payment, and CTA

Given I tap "View Details" on a loan offer
When the details screen loads
Then I see: APR, term options (12/24/36/48 months), total cost of credit
And a representative example for my credit tier

Given I accept a pre-approved loan offer
When I confirm and e-sign the agreement
Then the funds are deposited to my chosen account within 2 hours
And no hard credit check is performed
And the offer is removed from my dashboard

Given I am not eligible for pre-approved offers
When I view my dashboard
Then no loan offer card is displayed
And I am not aware that an eligibility check occurred
```

**Labels:** `lending`, `personal-loan`, `cross-sell`, `pre-approved`
**Compliance Notes:**
- Must include Reg Z disclosures (APR, finance charge, amount financed)
- Must honor opt-out preferences (TCPA/GLBA)

---

### Story LN-002: Digital Mortgage Application
**Priority:** High | **Story Points:** 21 (Epic) | **Sprint:** Sprint 22-26

**User Story:**
> As a **first-time home buyer**,  
> I want to **complete my mortgage application entirely online with document upload**,  
> So that **I don't have to visit a branch or mail physical documents**.

**Business Value:**
- Reduce mortgage application abandonment from 65% to 30%
- Decrease time-to-decision from 14 days to 3 days
- Save $800 per loan in operational processing costs

**Acceptance Criteria (MVP Slice):**
```
Given I start a new mortgage application
When I complete Step 1 (Personal Info)
Then I can save and resume later
And my progress is preserved for 30 days

Given I am on the "Income & Employment" step
When I upload my W-2 and pay stubs
Then the system extracts data using OCR
And pre-fills the income fields
And flags any discrepancies for review

Given I have completed all required steps
When I submit the application
Then I receive an instant conditional pre-qualification
Or a notification that manual underwriting is required
And I can track my application status in real-time

Given my application is under review
When the loan officer updates the status
Then I receive a push notification
And the status tracker updates: Submitted → In Review → Approved → Closing
```

**Labels:** `mortgage`, `digital-lending`, `onboarding`, `epic`
**Dependencies:** LN-003 (OCR/Document AI), LN-004 (Credit Bureau Integration)

---

## 4. Fraud & Risk Management

---

### Story FR-001: Real-Time Transaction Fraud Alert
**Priority:** Critical | **Story Points:** 8 | **Sprint:** Sprint 10

**User Story:**
> As a **debit card holder**,  
> I want to **receive an instant push notification for suspicious transactions**,  
> So that **I can approve or decline them immediately and prevent fraud**.

**Business Value:**
- Reduce fraud losses by $2M annually
- Reduce false positives by 20% (customer friction reduction)
- Improve fraud detection speed from batch (T+1) to real-time

**Acceptance Criteria:**
```
Given a transaction triggers the fraud risk engine (score >0.7)
When the transaction is submitted
Then the transaction is held (not posted)
And I receive a push notification within 3 seconds
With: merchant name, amount, location, and Approve/Decline buttons

Given I tap "Approve" on a fraud alert
When the approval is processed
Then the transaction is posted to my account
And the risk model learns from my feedback

Given I tap "Decline" on a fraud alert
When the decline is processed
Then the transaction is rejected
And my card is temporarily blocked
And I am prompted to call customer service or unblock via app

Given I do not respond to the alert within 10 minutes
When the timeout occurs
Then the transaction is auto-declined
And I receive a follow-up email
And the case is escalated to the fraud team
```

**Labels:** `fraud`, `security`, `real-time`, `notifications`, `critical`
**NFRs:**
- Latency: alert delivery <3 seconds end-to-end
- Availability: 99.999% (5 nines) for fraud engine
- Model accuracy: precision >95%, recall >90%

---

### Story FR-002: Behavioral Biometric Authentication
**Priority:** Medium | **Story Points:** 13 | **Sprint:** Sprint 24

**User Story:**
> As a **risk operations manager**,  
> I want to **continuously authenticate users via behavioral biometrics (typing rhythm, swipe patterns)**,  
> So that **frictionless fraud detection occurs in the background without bothering legitimate users**.

**Business Value:**
- Detect account takeover in real-time with 40% higher accuracy
- Reduce step-up authentication challenges by 50%
- Maintain zero perceived friction for 98% of legitimate sessions

**Acceptance Criteria:**
```
Given a user is logged in and navigating the app
When their behavioral pattern deviates significantly (>2 std dev)
Then the risk score is elevated
And a silent challenge is triggered (invisible to user)

Given the silent challenge fails
When the failure is confirmed
Then the session is terminated
And the user is forced to re-authenticate with MFA
And a security alert is logged in SIEM

Given the behavioral model has insufficient data
When a new user logs in (<5 sessions)
Then the model operates in "learning mode" only
And no blocking decisions are made

Given the model flags a session as high-risk
When the risk score exceeds 0.85
Then the case is queued for manual review by the fraud team
And the user session is monitored in real-time
```

**Labels:** `fraud`, `biometrics`, `machine-learning`, `silent-auth`

---

## 5. Compliance & Regulatory

---

### Story RG-001: Automated CTR (Currency Transaction Report) Filing
**Priority:** High | **Story Points:** 8 | **Sprint:** Sprint 16

**User Story:**
> As a **BSA/AML compliance officer**,  
> I want to **automatically generate and file CTRs for cash transactions >$10,000**,  
> So that **we meet FinCEN requirements without manual data entry**.

**Business Value:**
- Eliminate 100% of manual CTR filing errors
- Reduce compliance staffing needs by 2 FTEs
- Ensure 100% on-time filing (within 15 days)

**Acceptance Criteria:**
```
Given a customer deposits $12,000 cash at a branch
When the teller completes the transaction
Then the system auto-generates a CTR with:
  - Customer profile data (name, TIN, address, occupation)
  - Transaction details (date, amount, type, account)
  - Beneficial owner information if applicable

Given the CTR is generated
When it is submitted for review
Then the compliance officer can edit fields if needed
And add suspicious activity notes
And approve or reject the filing

Given the CTR is approved
When the filing deadline approaches (day 14)
Then the system auto-submits to FinCEN BSA E-Filing
And generates a confirmation receipt with BSA ID
And archives the filing for 5 years

Given a customer has multiple transactions on the same day
When the aggregated amount exceeds $10,000
Then the system flags the aggregation
And generates a single CTR with all transaction details
```

**Labels:** `compliance`, `aml`, `bsa`, `automation`, `regulatory`
**Regulatory Ref:** 31 CFR 1010.311, FinCEN Form 104

---

### Story RG-002: GDPR Data Subject Access Request (DSAR) Portal
**Priority:** High | **Story Points:** 13 | **Sprint:** Sprint 19

**User Story:**
> As a **data privacy officer**,  
> I want to **provide a self-service portal for customers to request their personal data**,  
> So that **we comply with GDPR Article 15 and respond within 30 days**.

**Business Value:**
- Avoid GDPR fines (up to 4% of global turnover)
- Reduce DSAR processing cost from €500 to €50 per request
- Improve customer trust and transparency

**Acceptance Criteria:**
```
Given I am a customer in the EU
When I navigate to "Privacy Center" → "Request My Data"
Then I can submit a DSAR with identity verification
And select: all data, specific date range, or specific categories

Given a DSAR is submitted
When the request is logged
Then I receive a confirmation with a tracking number
And the system creates a case for the privacy team
And a 30-day countdown timer begins

Given the DSAR is being processed
When the privacy team compiles the data
Then the system aggregates data from:
  - Core banking system (accounts, transactions)
  - CRM (marketing preferences, call recordings)
  - Credit bureau inquiries
  - Third-party payment processors
And excludes other customers' data and trade secrets

Given the DSAR response is ready
When the privacy team approves the package
Then I receive a secure download link
And the data is provided in a machine-readable format (JSON/CSV)
And the response is retained for audit purposes
```

**Labels:** `compliance`, `gdpr`, `privacy`, `data-subject-rights`

---

## 6. Corporate Banking

---

### Story CB-001: Multi-Level Approval Workflow for Wire Transfers
**Priority:** High | **Story Points:** 13 | **Sprint:** Sprint 17

**User Story:**
> As a **corporate CFO**,  
> I want to **require dual approval for wire transfers above $100,000**,  
> So that **we enforce segregation of duties and prevent unauthorized payments**.

**Business Value:**
- Eliminate unauthorized wire fraud (industry avg loss: $150K per incident)
- Meet SOX 404 internal control requirements
- Reduce insurance premiums for cyber/fraud coverage

**Acceptance Criteria:**
```
Given I am a user with "wire initiator" role
When I initiate a wire transfer >$100,000
Then the transfer status is "Pending Approval"
And I cannot approve my own transfer

Given I am a user with "wire approver" role
When I view pending approvals
Then I see the transfer details: amount, beneficiary, purpose, supporting docs
And I can "Approve", "Reject", or "Request More Info"

Given a transfer is approved by the first approver
When the second approver logs in
Then they see the transfer with first approver's name and timestamp
And their approval completes the workflow

Given a transfer is rejected
When the rejection is submitted
Then the initiator receives a notification with the reason
And the transfer is archived with audit trail

Given I want to configure approval thresholds
When I access "Admin → Approval Policies"
Then I can set: amount thresholds, number of approvers, and eligible roles
And changes are effective immediately for new transfers
```

**Labels:** `corporate`, `workflow`, `approval`, `sox`, `wire`
**Security Requirements:**
- All approvals cryptographically signed
- Immutable audit trail (blockchain/WORM storage)
- Role-based access control (RBAC) with quarterly recertification

---

### Story CB-002: Cash Position Dashboard
**Priority:** Medium | **Story Points:** 8 | **Sprint:** Sprint 21

**User Story:**
> As a **corporate treasurer**,  
> I want to **see a real-time consolidated cash position across all accounts and currencies**,  
> So that **I can optimize liquidity and make informed investment decisions**.

**Business Value:**
- Reduce idle cash by 15% through better visibility
- Improve cash forecasting accuracy from 70% to 90%
- Enable same-day investment decisions vs. T+1

**Acceptance Criteria:**
```
Given I log in to the corporate treasury portal
When I view the "Cash Position" dashboard
Then I see:
  - Total consolidated balance in base currency (USD)
  - Breakdown by: account, entity, currency, bank
  - Intraday vs. prior day close comparison
  - Liquidity classification (available, pending, restricted)

Given I have accounts in EUR, GBP, and JPY
When I view the dashboard
Then all balances are converted to USD using real-time FX rates
And I can toggle to view in any currency

Given I want to drill down
When I click on a specific entity
Then I see account-level details with last transaction timestamp
And I can export to Excel or PDF

Given I want to set alerts
When I configure a threshold (e.g., balance <$1M)
Then I receive an email/SMS alert when the threshold is breached
And the alert includes recommended actions (sweep, drawdown)
```

**Labels:** `corporate`, `treasury`, `dashboard`, `liquidity`, `fx`

---

## 7. Customer Onboarding & KYC

---

### Story KYC-001: Digital Identity Verification with Liveness Detection
**Priority:** Critical | **Story Points:** 13 | **Sprint:** Sprint 9

**User Story:**
> As a **prospective customer**,  
> I want to **verify my identity by scanning my ID and taking a selfie with liveness detection**,  
> So that **I can open an account remotely without visiting a branch**.

**Business Value:**
- Increase digital account opening completion from 30% to 70%
- Reduce CAC (customer acquisition cost) by $120 per account
- Meet KYC/AML identity verification requirements

**Acceptance Criteria:**
```
Given I am on the identity verification step
When I scan my driver's license or passport
Then the system:
  - Extracts name, DOB, ID number, and expiry date via OCR/MRZ
  - Validates the document's security features (hologram, font)
  - Checks against known fraudulent document database

Given my ID is successfully scanned
When I proceed to selfie capture
Then the system:
  - Requires a liveness challenge (blink, turn head, smile)
  - Compares the selfie to the ID photo with >95% confidence
  - Detects spoofing attempts (screen replay, mask, deepfake)

Given identity verification succeeds
When the process completes
Then I am notified within 30 seconds
And I can proceed to fund my account
And the KYC record is stored encrypted for 7 years

Given identity verification fails
When the failure reason is determined
Then I see a specific message:
  - "Document unclear — please retake"
  - "Identity mismatch — contact support"
  - "System error — try again later"
And failed attempts are limited to 3 per session
```

**Labels:** `kyc`, `onboarding`, `identity`, `liveness`, `critical`
**Compliance:** CIP (Customer Identification Program) under USA PATRIOT Act

---

### Story KYC-002: Beneficial Ownership Collection for Business Accounts
**Priority:** High | **Story Points:** 8 | **Sprint:** Sprint 13

**User Story:**
> As a **small business owner**,  
> I want to **provide my company's beneficial ownership information during account opening**,  
> So that **the bank complies with FinCEN's CDD Rule while I complete everything in one session**.

**Business Value:**
- Achieve 100% CDD compliance for business accounts
- Reduce business onboarding time from 5 days to 1 day
- Eliminate back-and-forth document requests

**Acceptance Criteria:**
```
Given I am opening a business account
When I reach the "Beneficial Ownership" step
Then I am informed that I must provide:
  - Individuals owning ≥25% of the business
  - One control person (CEO, CFO, etc.)
  - Name, address, DOB, SSN, and ownership % for each

Given I enter beneficial owner details
When I submit the information
Then the system validates against:
  - OFAC sanctions list
  - Politically Exposed Persons (PEP) database
  - Adverse media screening
And flags any matches for enhanced due diligence

Given I have a complex ownership structure (LLC owned by Trust)
When I indicate this structure
Then the system guides me through a nested ownership flow
And calculates ultimate beneficial ownership percentages

Given I want to update beneficial ownership later
When I navigate to "Account Settings → Business Info"
Then I can edit ownership details
And the system creates a new version with audit trail
And prompts for re-verification if ownership changes >25%
```

**Labels:** `kyc`, `business`, `cdd`, `beneficial-ownership`, `finCEN`
**Regulatory Ref:** 31 CFR 1010.230 (Customer Due Diligence Requirements)

---

## 8. Wealth Management

---

### Story WM-001: Goal-Based Investment Portfolio
**Priority:** Medium | **Story Points:** 13 | **Sprint:** Sprint 23

**User Story:**
> As a **retail investor**,  
> I want to **set financial goals (retirement, education, home purchase) and get a recommended portfolio**,  
> So that **my investments align with my life objectives and risk tolerance**.

**Business Value:**
- Increase AUM (assets under management) by $200M in 12 months
- Improve client retention to 95% (vs. 85% for non-advised accounts)
- Generate advisory fee revenue (0.75% annually on advised assets)

**Acceptance Criteria:**
```
Given I am a new wealth management client
When I complete the onboarding questionnaire
Then the system assesses:
  - Risk tolerance (1-5 scale via validated questionnaire)
  - Time horizon per goal
  - Liquidity needs
  - Tax situation
And generates a personalized portfolio recommendation

Given I have set a "Retirement at 65" goal
When I view my goal dashboard
Then I see:
  - Target amount (calculated from income replacement needs)
  - Current progress (% funded)
  - Monthly contribution needed to stay on track
  - Probability of success (Monte Carlo simulation)

Given market conditions change significantly
When my portfolio drifts >5% from target allocation
Then I receive a rebalance recommendation
And I can approve the rebalance with one tap
Or schedule it for a specific date

Given I want to adjust my goal
When I edit the target amount or timeline
Then the system recalculates the portfolio
And shows me the impact on expected returns and risk
```

**Labels:** `wealth`, `investment`, `goals`, `advisory`, `robo`
**Compliance:** SEC Investment Advisers Act, suitability requirements, fiduciary duty disclosure

---

### Story WM-002: Tax-Loss Harvesting Automation
**Priority:** Medium | **Story Points:** 8 | **Sprint:** Sprint 25

**User Story:**
> As a **high-net-worth client**,  
> I want to **automatically harvest tax losses in my taxable investment account**,  
> So that **I minimize my tax burden while maintaining my target asset allocation**.

**Business Value:**
- Save clients an estimated 1.5% annually in tax alpha
- Differentiate from competitors offering manual tax-loss harvesting only
- Attract HNW clients with >$500K taxable assets

**Acceptance Criteria:**
```
Given I have a taxable brokerage account
When a security has an unrealized loss >$5,000
And it has been held >30 days (to avoid wash sale rules)
Then the system flags it as a tax-loss harvesting candidate
And I receive a notification with the estimated tax savings

Given I approve a tax-loss harvest trade
When the trade executes
Then the system:
  - Sells the losing security
  - Buys a substantially similar (but not identical) replacement
  - Ensures no wash sale violation (30-day rule)
  - Updates the cost basis records

Given a harvested loss is realized
When tax reporting season arrives
Then the system generates Form 1099-B with proper adjustments
And provides a summary of harvested losses for my tax advisor

Given I want to disable tax-loss harvesting
When I toggle the setting off
Then no automated harvesting occurs
And existing harvested losses remain on record
```

**Labels:** `wealth`, `tax`, `automation`, `hnw`, `harvesting`
**Compliance:** IRS Publication 550, wash sale rule (IRC Section 1091)

---

## 9. Story Writing Best Practices Checklist

Use this checklist to ensure every banking story meets role-model standards:

### ✅ Structure
- [ ] **INVEST** compliant: Independent, Negotiable, Valuable, Estimable, Small, Testable
- [ ] Follows "As a [persona], I want [action], so that [outcome]" format
- [ ] Contains a clear, singular business value proposition
- [ ] Includes measurable success metrics (KPIs)

### ✅ Personas
- [ ] Uses specific banking personas (not just "user"):
  - Retail: checking account holder, credit card holder, first-time home buyer
  - Corporate: CFO, treasurer, AP clerk, controller
  - Internal: compliance officer, risk manager, branch teller, loan officer
  - HNW: accredited investor, family office manager

### ✅ Acceptance Criteria
- [ ] Written in Given/When/Then format (BDD style)
- [ ] Covers happy path, edge cases, and error scenarios
- [ ] Includes non-functional requirements (performance, security, compliance)
- [ ] Testable without ambiguity

### ✅ Banking-Specific Considerations
- [ ] Regulatory compliance referenced (GDPR, SOX, BSA/AML, PCI-DSS, etc.)
- [ ] Security and fraud implications addressed
- [ ] Audit trail and data retention requirements specified
- [ ] Integration points with core banking systems identified
- [ ] SLA/availability requirements defined for customer-facing features

### ✅ Sizing & Scoping
- [ ] Can be completed in a single sprint (ideally 3-8 points)
- [ ] If larger, clearly marked as Epic with defined MVP slice
- [ ] Dependencies explicitly called out
- [ ] Definition of Done is clear and achievable

### ✅ Cross-Functional
- [ ] Considers UX/UI implications
- [ ] Includes API/backend requirements
- [ ] Addresses data/analytics needs
- [ ] Notes customer communication (emails, notifications, disclosures)

---

## Quick Reference: Banking Personas

| Persona | Description | Typical Goals |
|---------|-------------|---------------|
| **Retail Customer** | Individual with checking/savings account | Convenience, security, low fees |
| **Credit Card Holder** | Active credit card user | Rewards, fraud protection, spending insights |
| **First-Time Home Buyer** | Millennial/Gen Z purchasing first home | Pre-approval, low rates, digital process |
| **Corporate CFO** | Finance leader at mid-market company | Cash visibility, fraud prevention, controls |
| **Corporate Treasurer** | Manages liquidity and investments | Yield optimization, risk management, reporting |
| **Compliance Officer** | BSA/AML/GDPR officer | Regulatory adherence, audit readiness, automation |
| **Risk Manager** | Fraud and credit risk professional | Loss reduction, model accuracy, detection speed |
| **HNW Client** | >$1M investable assets | Tax efficiency, wealth preservation, advisory |
| **Branch Teller** | Front-line staff | Efficiency, error reduction, customer satisfaction |
| **Loan Officer** | Mortgage/commercial lender | Faster decisions, accurate risk assessment |

---

*Document Version: 1.0 | Last Updated: July 2026 | Recommended for: Product Owners, Business Analysts, Scrum Masters in Banking Technology*
