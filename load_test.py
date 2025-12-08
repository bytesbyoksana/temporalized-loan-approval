"""
Load Testing Script - Demonstrate Temporal Scalability

This script submits multiple loan applications concurrently to show:
- App B (non-Temporal): Single Flask process handles requests sequentially
- App A (Temporal): Multiple Workers can process applications in parallel

Usage:
    python load_test.py --count 10
"""

import asyncio
import argparse
import time
from temporalio.client import Client
from workflows import LoanApprovalWorkflow

TASK_QUEUE_NAME = "loan-approval-task-queue"


async def submit_application(client: Client, app_number: int):
    """Submit a single loan application."""
    application = {
        'name': f'Test Applicant {app_number}',
        'email': f'test{app_number}@example.com',
        'loan_amount': 50000,
        'credit_score': 750,
        'annual_income': 150000,
        'has_bankruptcy': False
    }
    
    workflow_id = f"load-test-{app_number}"
    
    start_time = time.time()
    
    try:
        result = await client.execute_workflow(
            LoanApprovalWorkflow.run,
            application,
            id=workflow_id,
            task_queue=TASK_QUEUE_NAME
        )
        
        elapsed = time.time() - start_time
        
        print(f"✅ Application {app_number}: {result['decision']} ({elapsed:.2f}s)")
        return elapsed
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Application {app_number}: Error - {str(e)} ({elapsed:.2f}s)")
        return elapsed


async def run_load_test(count: int):
    """Run load test with specified number of applications."""
    print(f"\n{'='*60}")
    print(f"🚀 Load Test: Submitting {count} Applications")
    print(f"{'='*60}\n")
    
    # Connect to Temporal
    client = await Client.connect("localhost:7233")
    
    # Record start time
    overall_start = time.time()
    
    # Submit all applications concurrently
    tasks = [submit_application(client, i) for i in range(1, count + 1)]
    times = await asyncio.gather(*tasks)
    
    # Calculate statistics
    overall_elapsed = time.time() - overall_start
    avg_time = sum(times) / len(times)
    
    print(f"\n{'='*60}")
    print(f"📊 Results")
    print(f"{'='*60}")
    print(f"Total applications: {count}")
    print(f"Total time: {overall_elapsed:.2f}s")
    print(f"Average time per application: {avg_time:.2f}s")
    print(f"Throughput: {count/overall_elapsed:.2f} applications/second")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Load test the loan approval application')
    parser.add_argument('--count', type=int, default=10, help='Number of applications to submit')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("⚠️  IMPORTANT: Make sure you have Workers running!")
    print("="*60)
    print("\nFor best results:")
    print("1. Start with 1 Worker: python worker.py")
    print("2. Run this test: python load_test.py --count 10")
    print("3. Start 2-3 more Workers in separate terminals")
    print("4. Run test again and compare throughput!")
    print("="*60 + "\n")
    
    input("Press Enter to start load test...")
    
    asyncio.run(run_load_test(args.count))


if __name__ == "__main__":
    main()
