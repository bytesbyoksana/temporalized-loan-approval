"""
Temporal Activities for Loan Approval Application

Activities represent individual units of work that can fail and be retried.
Each activity handles a specific task in the loan approval process.
"""

import json
from datetime import datetime
from temporalio import activity
from typing import Dict, Any


@activity.defn
async def validate_application_data(application: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate application data for completeness and correctness.
    
    This activity checks:
    - Required fields are present
    - Email format is valid
    - Credit score is in valid range (300-850)
    - Loan amount and income are positive
    
    Returns validation result with any errors found.
    """
    activity.logger.info(f"Validating application for {application.get('email')}")
    
    errors = []
    
    # Check required fields
    required_fields = ['name', 'email', 'loan_amount', 'credit_score', 'annual_income', 'has_bankruptcy']
    for field in required_fields:
        if field not in application or application[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate credit score range
    credit_score = application.get('credit_score', 0)
    if not (300 <= credit_score <= 850):
        errors.append("Credit score must be between 300 and 850")
    
    # Validate positive amounts
    if application.get('loan_amount', 0) <= 0:
        errors.append("Loan amount must be greater than $0")
    
    if application.get('annual_income', 0) <= 0:
        errors.append("Annual income must be greater than $0")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


@activity.defn
async def check_duplicate_submission(email: str, submissions_file: str = 'submissions.json') -> Dict[str, Any]:
    """
    Check if email has already submitted an application recently.
    
    Returns information about existing submission if found.
    """
    activity.logger.info(f"Checking for duplicate submission: {email}")
    
    try:
        with open(submissions_file, 'r') as f:
            submissions = json.load(f)
        
        for submission in reversed(submissions):
            if submission.get('email', '').lower() == email.lower():
                submission_date = datetime.fromisoformat(submission['timestamp'])
                days_since = (datetime.now() - submission_date).days
                
                if days_since < 7:  # 7-day waiting period
                    return {
                        'is_duplicate': True,
                        'days_remaining': 7 - days_since,
                        'existing_submission': submission
                    }
        
        return {'is_duplicate': False}
    
    except FileNotFoundError:
        return {'is_duplicate': False}


@activity.defn
async def evaluate_credit_decision(application: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate loan application and make credit decision.
    
    This is the core business logic that determines:
    - Pre-approved
    - Conditional (needs agent review)
    - Denied
    
    Based on credit score, loan-to-income ratio, and bankruptcy status.
    """
    activity.logger.info(f"Evaluating credit decision for {application.get('email')}")
    
    credit_score = application['credit_score']
    loan_amount = application['loan_amount']
    annual_income = application['annual_income']
    has_bankruptcy = application['has_bankruptcy']
    
    # Calculate loan-to-income ratio
    loan_to_income = loan_amount / annual_income if annual_income > 0 else float('inf')
    
    # Decision logic
    decision = 'denied'
    
    # Pre-approved: excellent credit, no bankruptcy, reasonable ratio
    if credit_score >= 720 and not has_bankruptcy and loan_to_income <= 0.4:
        decision = 'pre_approved'
    
    # Conditional: excellent credit but bankruptcy
    elif credit_score >= 720 and has_bankruptcy:
        decision = 'conditional'
    
    # Conditional: excellent credit but high loan-to-income
    elif credit_score >= 720 and loan_to_income > 0.4:
        decision = 'conditional'
    
    # Conditional: moderate credit
    elif 680 <= credit_score < 720 and loan_to_income <= 0.5:
        decision = 'conditional'
    
    activity.logger.info(f"Decision: {decision} (LTI: {loan_to_income:.2f})")
    
    return {
        'decision': decision,
        'loan_to_income_ratio': round(loan_to_income, 2),
        'credit_score': credit_score
    }


@activity.defn
async def format_decision_message(decision: str, application: Dict[str, Any], messages_file: str = 'messages.json') -> Dict[str, Any]:
    """
    Format human-friendly message based on decision.
    
    Loads message templates from JSON and formats with application data.
    """
    activity.logger.info(f"Formatting message for decision: {decision}")
    
    with open(messages_file, 'r') as f:
        messages = json.load(f)
    
    message_template = messages['decisions'].get(decision, messages['decisions']['denied'])
    
    formatted_message = {
        'decision': decision,
        'title': message_template['title'],
        'message': message_template['message'].replace(
            '${loan_amount}', 
            f"${application.get('loan_amount', 0):,.2f}"
        ),
        'next_steps': message_template['next_steps']
    }
    
    return formatted_message


@activity.defn
async def save_application(application: Dict[str, Any], decision: str, submissions_file: str = 'submissions.json') -> Dict[str, Any]:
    """
    Persist application data to storage.
    
    This activity handles the final step of saving the application
    with its decision to the submissions file.
    """
    activity.logger.info(f"Saving application for {application.get('email')}")
    
    try:
        with open(submissions_file, 'r') as f:
            submissions = json.load(f)
    except FileNotFoundError:
        submissions = []
    
    submission_record = {
        **application,
        'decision': decision,
        'contact_requested': None,
        'timestamp': datetime.now().isoformat()
    }
    
    # Check if updating existing submission
    email = application['email'].lower()
    updated = False
    for i, sub in enumerate(submissions):
        if sub.get('email', '').lower() == email:
            submission_date = datetime.fromisoformat(sub['timestamp'])
            if (datetime.now() - submission_date).days >= 7:
                submissions[i] = submission_record
                updated = True
                break
    
    if not updated:
        submissions.append(submission_record)
    
    with open(submissions_file, 'w') as f:
        json.dump(submissions, f, indent=2)
    
    activity.logger.info(f"Application saved successfully")
    
    return {'saved': True, 'submission_id': email}


@activity.defn
async def update_contact_preference(email: str, preference: bool, submissions_file: str = 'submissions.json') -> Dict[str, Any]:
    """
    Update contact preference for an existing submission.
    
    This activity is called after the user indicates whether they want
    to be contacted by an agent.
    """
    activity.logger.info(f"Updating contact preference for {email}: {preference}")
    
    try:
        with open(submissions_file, 'r') as f:
            submissions = json.load(f)
        
        # Find and update the submission
        for submission in reversed(submissions):
            if submission.get('email', '').lower() == email.lower():
                submission['contact_requested'] = preference
                submission['contact_timestamp'] = datetime.now().isoformat()
                break
        
        with open(submissions_file, 'w') as f:
            json.dump(submissions, f, indent=2)
        
        return {'updated': True}
    
    except Exception as e:
        activity.logger.error(f"Error updating contact preference: {str(e)}")
        return {'updated': False, 'error': str(e)}


@activity.defn
async def send_notification_to_agent(application: Dict[str, Any], decision: str) -> Dict[str, Any]:
    """
    Send notification to agent for conditional approvals.
    
    In a real system, this would send an email or create a task
    for a loan officer to review the application.
    """
    activity.logger.info(f"Sending notification to agent for {application.get('email')}")
    
    # Simulate notification (in production, this would call an email service)
    notification = {
        'type': 'agent_review_required',
        'applicant_email': application.get('email'),
        'applicant_name': application.get('name'),
        'decision': decision,
        'loan_amount': application.get('loan_amount'),
        'credit_score': application.get('credit_score'),
        'timestamp': datetime.now().isoformat()
    }
    
    activity.logger.info(f"Notification sent: {notification}")
    
    return {'notification_sent': True, 'notification': notification}
