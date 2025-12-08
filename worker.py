"""
Temporal Worker for Loan Approval Application

The Worker is responsible for executing Workflows and Activities.
It polls the Temporal Service for tasks and executes them.

Run this file to start the Worker:
    python worker.py
"""

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from workflows import LoanApprovalWorkflow, ContactPreferenceWorkflow
from activities import (
    validate_application_data,
    check_duplicate_submission,
    evaluate_credit_decision,
    format_decision_message,
    save_application,
    send_notification_to_agent,
    update_contact_preference
)

# Task queue name - this is how the Worker knows which tasks to process
TASK_QUEUE_NAME = "loan-approval-task-queue"


async def main():
    """
    Connect to Temporal Service and start the Worker.
    """
    # Connect to Temporal Service
    # For local development: localhost:7233
    # For Temporal Cloud: use your cloud namespace
    client = await Client.connect("localhost:7233")
    
    print(f"\n{'='*60}")
    print(f"🚀 Temporal Worker Starting")
    print(f"{'='*60}")
    print(f"Task Queue: {TASK_QUEUE_NAME}")
    print(f"Workflows: LoanApprovalWorkflow, ContactPreferenceWorkflow")
    print(f"Activities: 7 activities registered")
    print(f"{'='*60}\n")
    
    # Create Worker with workflows and activities
    worker = Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[
            LoanApprovalWorkflow,
            ContactPreferenceWorkflow
        ],
        activities=[
            validate_application_data,
            check_duplicate_submission,
            evaluate_credit_decision,
            format_decision_message,
            save_application,
            send_notification_to_agent,
            update_contact_preference
        ]
    )
    
    print("✅ Worker is ready and listening for tasks...")
    print("   Press Ctrl+C to stop\n")
    
    # Run the Worker
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Worker stopped by user")
        print("="*60)
