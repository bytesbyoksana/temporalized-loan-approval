"""
Tests for Loan Approval Workflows and Activities

This demonstrates Temporal's testing capabilities:
- Testing Activities in isolation
- Testing Workflows with mocked Activities
- Time skipping for long-running workflows
- Integration testing with real Workers

Run tests with: pytest test_workflows.py -v
"""

import pytest
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment, ActivityEnvironment
from temporalio.worker import Worker
from temporalio.client import Client

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


# ============================================================================
# Activity Tests - Test activities in isolation
# ============================================================================

@pytest.mark.asyncio
async def test_validate_application_data_success():
    """Test that valid application data passes validation."""
    env = ActivityEnvironment()
    
    valid_application = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'loan_amount': 50000,
        'credit_score': 750,
        'annual_income': 150000,
        'has_bankruptcy': False
    }
    
    result = await env.run(validate_application_data, valid_application)
    
    assert result['valid'] is True
    assert len(result['errors']) == 0


@pytest.mark.asyncio
async def test_validate_application_data_missing_fields():
    """Test that missing required fields are caught."""
    env = ActivityEnvironment()
    
    invalid_application = {
        'name': 'John Doe',
        'email': 'john@example.com'
        # Missing loan_amount, credit_score, annual_income, has_bankruptcy
    }
    
    result = await env.run(validate_application_data, invalid_application)
    
    assert result['valid'] is False
    assert len(result['errors']) > 0
    assert any('Missing required field' in error for error in result['errors'])


@pytest.mark.asyncio
async def test_validate_application_data_invalid_credit_score():
    """Test that invalid credit score is caught."""
    env = ActivityEnvironment()
    
    invalid_application = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'loan_amount': 50000,
        'credit_score': 900,  # Invalid - max is 850
        'annual_income': 150000,
        'has_bankruptcy': False
    }
    
    result = await env.run(validate_application_data, invalid_application)
    
    assert result['valid'] is False
    assert any('Credit score must be between 300 and 850' in error for error in result['errors'])


@pytest.mark.asyncio
async def test_evaluate_credit_decision_pre_approved():
    """Test pre-approval decision logic."""
    env = ActivityEnvironment()
    
    application = {
        'email': 'test@example.com',
        'loan_amount': 50000,
        'credit_score': 750,
        'annual_income': 150000,
        'has_bankruptcy': False
    }
    
    result = await env.run(evaluate_credit_decision, application)
    
    assert result['decision'] == 'pre_approved'
    assert result['loan_to_income_ratio'] == 0.33  # 50000/150000


@pytest.mark.asyncio
async def test_evaluate_credit_decision_conditional_high_ratio():
    """Test conditional approval for excellent credit with high loan-to-income."""
    env = ActivityEnvironment()
    
    application = {
        'email': 'test@example.com',
        'loan_amount': 100000,
        'credit_score': 750,
        'annual_income': 80000,
        'has_bankruptcy': False
    }
    
    result = await env.run(evaluate_credit_decision, application)
    
    assert result['decision'] == 'conditional'
    assert result['loan_to_income_ratio'] == 1.25  # 100000/80000


@pytest.mark.asyncio
async def test_evaluate_credit_decision_conditional_bankruptcy():
    """Test conditional approval for excellent credit with bankruptcy."""
    env = ActivityEnvironment()
    
    application = {
        'email': 'test@example.com',
        'loan_amount': 50000,
        'credit_score': 750,
        'annual_income': 150000,
        'has_bankruptcy': True
    }
    
    result = await env.run(evaluate_credit_decision, application)
    
    assert result['decision'] == 'conditional'


@pytest.mark.asyncio
async def test_evaluate_credit_decision_denied():
    """Test denial for low credit score."""
    env = ActivityEnvironment()
    
    application = {
        'email': 'test@example.com',
        'loan_amount': 50000,
        'credit_score': 650,
        'annual_income': 60000,
        'has_bankruptcy': False
    }
    
    result = await env.run(evaluate_credit_decision, application)
    
    assert result['decision'] == 'denied'


# ============================================================================
# Workflow Tests - Test workflows with time skipping
# ============================================================================

@pytest.mark.asyncio
async def test_loan_approval_workflow_success():
    """Test complete loan approval workflow with pre-approval."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-task-queue",
            workflows=[LoanApprovalWorkflow],
            activities=[
                validate_application_data,
                check_duplicate_submission,
                evaluate_credit_decision,
                format_decision_message,
                save_application,
                send_notification_to_agent
            ]
        ):
            application = {
                'name': 'John Doe',
                'email': 'john.test@example.com',
                'loan_amount': 50000,
                'credit_score': 750,
                'annual_income': 150000,
                'has_bankruptcy': False
            }
            
            result = await env.client.execute_workflow(
                LoanApprovalWorkflow.run,
                application,
                id="test-workflow-success",
                task_queue="test-task-queue"
            )
            
            assert result['status'] == 'success'
            assert result['decision'] == 'pre_approved'
            assert 'message' in result
            assert result['message']['decision'] == 'pre_approved'


@pytest.mark.asyncio
async def test_loan_approval_workflow_validation_error():
    """Test workflow with validation errors."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-task-queue",
            workflows=[LoanApprovalWorkflow],
            activities=[
                validate_application_data,
                check_duplicate_submission,
                evaluate_credit_decision,
                format_decision_message,
                save_application,
                send_notification_to_agent
            ]
        ):
            # Invalid application - credit score too high
            application = {
                'name': 'John Doe',
                'email': 'john.invalid@example.com',
                'loan_amount': 50000,
                'credit_score': 900,  # Invalid
                'annual_income': 150000,
                'has_bankruptcy': False
            }
            
            result = await env.client.execute_workflow(
                LoanApprovalWorkflow.run,
                application,
                id="test-workflow-validation-error",
                task_queue="test-task-queue"
            )
            
            assert result['status'] == 'error'
            assert 'errors' in result
            assert len(result['errors']) > 0


@pytest.mark.asyncio
async def test_loan_approval_workflow_conditional():
    """Test workflow resulting in conditional approval."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-task-queue",
            workflows=[LoanApprovalWorkflow],
            activities=[
                validate_application_data,
                check_duplicate_submission,
                evaluate_credit_decision,
                format_decision_message,
                save_application,
                send_notification_to_agent
            ]
        ):
            application = {
                'name': 'Jane Smith',
                'email': 'jane.conditional@example.com',
                'loan_amount': 100000,
                'credit_score': 750,
                'annual_income': 80000,
                'has_bankruptcy': False
            }
            
            result = await env.client.execute_workflow(
                LoanApprovalWorkflow.run,
                application,
                id="test-workflow-conditional",
                task_queue="test-task-queue"
            )
            
            assert result['status'] == 'success'
            assert result['decision'] == 'conditional'


@pytest.mark.asyncio
async def test_contact_preference_workflow():
    """Test contact preference workflow."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-task-queue",
            workflows=[ContactPreferenceWorkflow],
            activities=[update_contact_preference]
        ):
            result = await env.client.execute_workflow(
                ContactPreferenceWorkflow.run,
                args=['test@example.com', True],
                id="test-contact-preference",
                task_queue="test-task-queue"
            )
            
            assert result['status'] == 'success'
            assert result['email'] == 'test@example.com'
            assert result['preference'] is True


# ============================================================================
# Parameterized Tests - Test multiple scenarios efficiently
# ============================================================================

@pytest.mark.parametrize("credit_score,loan_amount,income,bankruptcy,expected_decision", [
    (750, 50000, 150000, False, 'pre_approved'),      # Pre-approved
    (750, 100000, 80000, False, 'conditional'),       # Conditional - high ratio
    (750, 50000, 150000, True, 'conditional'),        # Conditional - bankruptcy
    (690, 30000, 70000, False, 'conditional'),        # Conditional - moderate credit
    (650, 50000, 60000, False, 'denied'),             # Denied - low credit
])
@pytest.mark.asyncio
async def test_decision_logic_scenarios(credit_score, loan_amount, income, bankruptcy, expected_decision):
    """Test various decision scenarios with parameterized inputs."""
    env = ActivityEnvironment()
    
    application = {
        'email': 'test@example.com',
        'loan_amount': loan_amount,
        'credit_score': credit_score,
        'annual_income': income,
        'has_bankruptcy': bankruptcy
    }
    
    result = await env.run(evaluate_credit_decision, application)
    
    assert result['decision'] == expected_decision


# ============================================================================
# Time Skipping Tests - Demonstrate Temporal's time manipulation
# ============================================================================

@pytest.mark.asyncio
async def test_workflow_with_time_skipping():
    """
    Demonstrate time skipping capability.
    
    In a real scenario, you might have workflows with timers or delays.
    Temporal's test environment can skip time instantly.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Time skipping is automatic - any timers or sleeps in workflows
        # will be fast-forwarded during testing
        
        # You can also manually advance time if needed:
        await env.sleep(timedelta(hours=24))  # Instantly skips 24 hours
        
        # This is useful for testing workflows with:
        # - Long retry intervals
        # - Scheduled tasks
        # - Timeout scenarios
        
        assert True  # Placeholder - in real tests, verify workflow behavior after time skip


if __name__ == "__main__":
    # Run tests with: python test_workflows.py
    # Or better: pytest test_workflows.py -v
    import asyncio
    
    print("Running tests...")
    print("Use 'pytest test_workflows.py -v' for better output")
    
    # Run a simple test
    asyncio.run(test_validate_application_data_success())
    print("✅ Basic test passed!")
