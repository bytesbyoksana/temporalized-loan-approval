# Temporalized Loan Pre-Approval Application

A demonstration of how Temporal transforms a standard web application into a durable, reliable, and scalable system.

## Table of contents

- [Overview](#overview)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Testing the application](#testing-the-application)
- [Security benefits](#security-benefits)
- [Next steps](#next-steps)
- [Resources](#resources)

---

## Overview

This is a **temporalized** version of a loan pre-approval application. Temporal is a durable Workflows-as-Code engine that ensures your code runs to completion, even in the situations of failures, crashes, or infrastructure issues.

### Before Temporal (original application)

The original application is a standard Flask web app that processes loan applications synchronously. To view the original application, see [Loan Pre-Approval Application](https://github.com/bytesbyoksana/loan-approval-app/tree/main).

The application has these characteristics:

**Architecture:**

- Single Flask application handling all logic
- Direct function calls for business logic
- Synchronous processing
- File-based storage (JSON)

**Problems:**

1. **No Failure Recovery**: If the server crashed mid-processing, the application state was lost
2. **No Retry Logic**: Failed operations required manual intervention
3. **No Visibility**: Couldn't see what step failed or replay execution history
4. **Tight Coupling**: Business logic mixed with HTTP handling
5. **Limited Scalability**: Single process handling all requests
6. **No Idempotency Guarantees**: Duplicate submissions could occur during network issues

### After Temporal (Temporalized application)

By integrating Temporal, I've transformed the application into a durable, fault-tolerant system that can handle failures gracefully and scale reliably.

**Architecture:**

- Flask app as thin API layer
- Temporal Workflows orchestrate business logic
- Temporal Activities handle individual tasks
- Temporal Workers execute the work
- Temporal Service provides durability

**Benefits:**

1. **Durable Execution**: Workflows survive crashes and resume automatically
2. **Automatic Retries**: Activities retry with configurable policies
3. **Full Visibility**: Temporal UI shows every step, retry, and state change
4. **Separation of Concerns**: Clear boundaries between orchestration and execution
5. **Horizontal Scalability**: Add more Workers to handle increased load
6. **Built-in Idempotency**: Workflow IDs prevent duplicate processing
7. **Audit Trail**: Complete history of every application processed

## Project structure

Following Temporal's recommended conventions:

```
temporalized-loan-approval/
├── activities.py                   # Temporal Activities (individual tasks)
├── workflows.py                    # Temporal Workflows (orchestration)
├── worker.py                       # Temporal Worker (executes workflows/activities)
├── starter.py                      # Flask app + workflow starter (contains Flask app)
├── test_workflows.py               # Pytest tests for workflows and activities
├── templates/
│   ├── form.html                   # User form
│   └── result.html                 # Decision result
├── static/
│   └── style.css                   # Styling
├── rules.json                      # Decision rules
├── messages.json                   # User-facing messages
├── submissions.json                # Stored applications
├── requirements.txt                # Python dependencies (includes pytest)
└── README.md                       # This file
```

---

## Quick start

Get the application running in a few minutes.

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- The Homebrew Package Manager on macOS. For more information, go to [https://brew.sh/](https://brew.sh/).

### Install Temporal CLI

**macOS:**

```bash
brew install temporal
```

**Linux:**
```bash
curl -sSf https://temporal.download/cli.sh | sh
```

### Setup the environment

```bash
# 1. Navigate to project
cd temporalized-loan-approval

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install "Flask[async]"
```

### Run an application with Temporal

1. You'll need 3 Terminal windows.

   - Terminal 1: In the open terminal where you activated the Python environment, start the Temporal service.

      ```bash
      temporal server start-dev
      ```

   - Terminal 2: Open the new terminal, navigate to the app directory, and start the Worker. The Worker executes your Workflow and Activity code.

      ```bash
      cd temporalized-loan-approval
      source venv/bin/activate
      python worker.py
      ```

   - Terminal 3: Open the new terminal, navigate to the app directory, and start the Flask app.

      ```bash
      cd temporalized-loan-approval
      source venv/bin/activate
      python starter.py
      ```

1. Review and test the app.

   - Open the web UI:

      1. Go to http://127.0.0.1:5001.
      1. Fill out and submit the form.
      1. View workflow in Temporal UI: http://localhost:8233.
      1. In the Temporal UI, choose your workflow to see all activities, retries, and state.

   - Test the app with `curl`:

      In a new Termianl window, enter the following:

      ```bash
      curl -X POST http://127.0.0.1:5001/api/evaluate \
      -H "Content-Type: application/json" \
      -d '{
         "name": "John Doe",
         "email": "john@example.com",
         "loan_amount": 50000,
         "credit_score": 750,
         "annual_income": 150000,
         "has_bankruptcy": false
      }'
      ```

   - Refresh Temporal UI to see the new workflow.

---

## Testing the application

Temporal provides powerful testing capabilities that let you test workflows and activities in isolation.

### Run all tests

```bash
# Run all tests
cd temporalized-loan-approval
source venv/bin/activate
pytest test_workflows.py -v
```

### Manual testing

Test the application in the web UI and in the CLI.

#### Test 1: Successful pre-approval

**To see a successful pre-approval workflow:**

1. Go to http://127.0.0.1:5001
1. Fill out form:
   - Name: John Doe
   - Email: john@example.com
   - Loan Amount: 50,000
   - Annual Income: 150,000
   - Credit Score: 750
   - Bankruptcy: No
1. Submit and receive pre-approval message.
1. Go to http://localhost:8233.
1. Choose your workflow to observe:
   - All activities executed
   - Timing information
   - Input/output data
   - Complete event history

#### Test 2: Conditional approval (high loan-to-income)

**To see conditional approval with excellent credit:**

1. In the new Teminal, enter the following:

   ```bash
   curl -X POST http://127.0.0.1:5001/api/evaluate \
   -H "Content-Type: application/json" \
   -d '{
      "name": "Sarah Test",
      "email": "sarah@example.com",
      "loan_amount": 100000,
      "credit_score": 750,
      "annual_income": 80000,
      "has_bankruptcy": false
   }'
   ```

1. Go to http://localhost:8233.
1. Observe the new execution.

#### Test 3: Duplicate submission (Idempotency)

**To see Temporal's idempotency protection:**

1. Submit the same email twice:

   ```bash
   # First submission
   curl -X POST http://127.0.0.1:5001/api/evaluate \
   -H "Content-Type: application/json" \
   -d '{
      "name": "Test User",
      "email": "test@example.com",
      "loan_amount": 50000,
      "credit_score": 720,
      "annual_income": 100000,
      "has_bankruptcy": false
   }'

   # Second submission (within 7 days)
   curl -X POST http://127.0.0.1:5001/api/evaluate \
   -H "Content-Type: application/json" \
   -d '{
      "name": "Test User",
      "email": "test@example.com",
      "loan_amount": 60000,
      "credit_score": 730,
      "annual_income": 110000,
      "has_bankruptcy": false
   }'
   ```

   **Result:** Second submission returns duplicate error with days remaining.

1. Open http://localhost:8233.
1. Observe the new execution.

#### Test 4: Simulating failures

**To see Temporal's retry capabilities and durability:**

1. Stop the Worker (Ctrl+C in Terminal 2).
1. Submit an application form via web or your CLI.
1. Flask will start the workflow, but it will queue.
1. Restart the Worker.
1. Watch the workflow execute immediately.
1. In Temporal UI:

   - You'll see the workflow was pending.
   - Once Worker restarted, it executed.
   - No data was lost.

#### Test 5: Simulating stress test

**To see Temporal's horizontal scalability:**

1. Run load test with 1 Worker:

   ```bash
   python load_test.py --count 10
   ```

   **Observe the results:**

   ```
   📊 Results
   ============================================================
   Total applications: 10
   Total time: ~15-20s
   Throughput: ~0.5-0.7 applications/second
   ============================================================
   ```

1. Start 2 additional Workers in separate terminals:

   **Terminal 4:**

   ```bash
   cd temporalized-loan-approval
   source venv/bin/activate
   python worker.py
   ```

   **Terminal 5:**

   ```bash
   cd temporalized-loan-approval
   source venv/bin/activate
   python worker.py
   ```

1. Run the load test again:

   ```bash
   python load_test.py --count 10
   ```

   **Observe the improvement:**

   ```
   📊 Results
   ============================================================
   Total applications: 10
   Total time: ~5-7s (3x faster!)
   Throughput: ~1.5-2 applications/second (3x higher!)
   ============================================================
   ```

1. Go to http://localhost:8233.
1. Observe multiple workflows executing in parallel.
1. Click on any workflow to see which Worker processed it.

**Result:** With 3 Workers, throughput increased 3x with no code changes. This demonstrates horizontal scalability.

---

## Security benefits

Temporal provides enterprise-grade security features that protect your application and data.

### Code execution boundaries

**Your code runs in your infrastructure, not on Temporal servers.**

- Workers execute in your environment (containers, VMs, on-premises)
- You maintain full control over your application security
- Temporal Service only orchestrates - it doesn't execute your business logic
- No need to trust a third party with your code execution

**In this application:**

- The Worker runs on your machine or server
- Activities (validation, decision logic, file operations) execute in your environment
- Temporal only tracks workflow state and coordinates execution

### Data encryption

**Client-side encryption with data converters**

Temporal supports transparent encryption of all workflow data before it leaves your environment:

```python
# Example: Encrypt sensitive data before sending to Temporal
from temporalio.converter import DataConverter, EncryptionConverter

# Your data is encrypted before leaving your Worker
# Temporal Service only sees encrypted data
# Data is decrypted when it returns to your Worker
```

**For this loan application:**

- Applicant names, emails, income, credit scores could be encrypted
- Only your Workers can decrypt the data
- Temporal UI would show encrypted values (or use a Codec Server for authorized viewing)

### Namespace isolation

**Multi-tenant security:**

- Each Temporal Namespace is logically isolated
- Namespaces cannot interact with each other
- Data is not shared across Namespaces
- Secure gRPC (mTLS) and HTTPS (TLS) endpoints per Namespace

**In production:**

- Separate Namespaces for dev, staging, production
- Different teams can have isolated Namespaces
- Customer data can be segregated by Namespace

### Authentication and authorization

**mTLS for Worker authentication:**

Workers authenticate to Temporal using mutual TLS (mTLS):

- Certificate-based authentication
- No passwords or API keys in code
- Automatic certificate rotation support
- Per-Namespace access control

**Role-based access control (RBAC):**

- Account-level roles: Admin, Developer, Read-only
- Namespace-level permissions
- Audit logs for all access

### Compliance

**Temporal Cloud is certified and compliant:**

- **SOC 2 Type 2** - Security, availability, and confidentiality
- **GDPR** - European data protection regulations
- **HIPAA** - Healthcare data protection (for Temporal Cloud)

---

## Next steps

**For production:**

1. Use Temporal Cloud instead of self-hosted
1. Add database instead of JSON files
1. Implement real email notifications
1. Add authentication and authorization
1. Set up monitoring and alerting
1. Implement comprehensive testing
1. Add CI/CD pipeline

**For learning:**

1. Explore Temporal UI features
1. Experiment with different retry policies
1. Implement workflow versioning
1. Try Temporal's testing framework

---

## Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [Temporal Python SDK](https://docs.temporal.io/develop/python)
- [Python Tutorials](https://learn.temporal.io/tutorials/python/)
- [Temporal Community Programs](https://learn.temporal.io/community_programs/)

---

**Built with Temporal, Flask, Python, and ❤️**
