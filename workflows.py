"""
Temporal Workflows for Loan Approval Application

Workflows orchestrate the loan approval process, coordinating multiple activities
and handling the business logic flow. Workflows are durable and can recover from failures.
"""

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from typing import Dict, Any

# Import activities with Temporal's safe import mechanism
with workflow.unsafe.imports_passed_through():
    from activities import (
        validate_application_data,
        check_duplicate_submission,
        evaluate_credit_decision,
        format_decision_message,
        save_application,
        send_notification_to_agent,
        update_contact_preference
    )


@workflow.defn
class LoanApprovalWorkflow:
    """
    Main workflow for processing loan applications.
    
    This workflow orchestrates the entire loan approval process:
    1. Validate application data
    2. Check for duplicate submissions
    3. Evaluate credit decision
    4. Format decision message
    5. Save application
    6. Notify agent if conditional approval
    
    The workflow is durable - if any step fails, Temporal will retry
    according to the retry policy, and the workflow can resume from
    where it left off even after crashes.
    """
    
    @workflow.run
    async def run(self, application: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the loan approval workflow.
        
        Args:
            application: Dictionary containing applicant information
            
        Returns:
            Dictionary with decision and formatted message
        """
        workflow.logger.info(f"Starting loan approval workflow for {application.get('email')}")
        
        # Step 1: Validate application data
        # Retry policy: Fast retries for validation (likely transient issues)
        validation_result = await workflow.execute_activity(
            validate_application_data,
            application,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=5),
                maximum_attempts=3
            )
        )
        
        if not validation_result['valid']:
            workflow.logger.warning(f"Validation failed: {validation_result['errors']}")
            return {
                'status': 'error',
                'errors': validation_result['errors']
            }
        
        # Step 2: Check for duplicate submission
        # This activity checks idempotency
        duplicate_check = await workflow.execute_activity(
            check_duplicate_submission,
            application['email'],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3
            )
        )
        
        if duplicate_check['is_duplicate']:
            workflow.logger.info(f"Duplicate submission detected for {application['email']}")
            return {
                'status': 'duplicate',
                'days_remaining': duplicate_check['days_remaining'],
                'existing_submission': duplicate_check.get('existing_submission')
            }
        
        # Step 3: Evaluate credit decision
        # This is the core business logic - retry with exponential backoff
        decision_result = await workflow.execute_activity(
            evaluate_credit_decision,
            application,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=10),
                backoff_coefficient=2.0,
                maximum_attempts=5
            )
        )
        
        decision = decision_result['decision']
        workflow.logger.info(f"Credit decision: {decision}")
        
        # Step 4: Format decision message
        # Load message templates and format with application data
        message_data = await workflow.execute_activity(
            format_decision_message,
            args=[decision, application],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_attempts=3
            )
        )
        
        # Step 5: Save application to persistent storage
        # Critical step - use longer timeout and more retries
        save_result = await workflow.execute_activity(
            save_application,
            args=[application, decision],
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=10  # More retries for persistence
            )
        )
        
        # Step 6: Send notification to agent if conditional approval
        # This is a "fire and forget" notification - failures are logged but don't block
        if decision == 'conditional':
            try:
                await workflow.execute_activity(
                    send_notification_to_agent,
                    args=[application, decision],
                    start_to_close_timeout=timedelta(seconds=15),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        maximum_attempts=3
                    )
                )
            except Exception as e:
                # Log but don't fail the workflow if notification fails
                workflow.logger.warning(f"Failed to send agent notification: {str(e)}")
        
        workflow.logger.info(f"Loan approval workflow completed successfully")
        
        return {
            'status': 'success',
            'decision': decision,
            'message': message_data,
            'application': application,
            'loan_to_income_ratio': decision_result.get('loan_to_income_ratio')
        }


@workflow.defn
class ContactPreferenceWorkflow:
    """
    Workflow for updating contact preference after application submission.
    
    This is a simpler workflow that handles the user's choice about
    whether they want to be contacted by an agent.
    """
    
    @workflow.run
    async def run(self, email: str, preference: bool) -> Dict[str, Any]:
        """
        Update contact preference for an applicant.
        
        Args:
            email: Applicant's email address
            preference: True if they want to be contacted, False otherwise
            
        Returns:
            Dictionary with update status
        """
        workflow.logger.info(f"Updating contact preference for {email}: {preference}")
        
        update_result = await workflow.execute_activity(
            update_contact_preference,
            args=[email, preference],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=5),
                maximum_attempts=5
            )
        )
        
        return {
            'status': 'success' if update_result['updated'] else 'error',
            'email': email,
            'preference': preference
        }
