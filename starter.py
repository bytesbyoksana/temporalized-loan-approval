"""
Flask Application with Temporal Integration (Starter)

Run this file to start the Flask application:
    python starter.py
"""

import asyncio
from flask import Flask, render_template, request, jsonify
import re
import bleach
from temporalio.client import Client
from workflows import LoanApprovalWorkflow, ContactPreferenceWorkflow

# Task queue name - must match the Worker's task queue
TASK_QUEUE_NAME = "loan-approval-task-queue"


def create_app(temporal_client: Client):
    """Create and configure Flask app with Temporal client."""
    app = Flask(__name__)
    
    def sanitize_input(text: str) -> str:
        """Sanitize text input to prevent injection."""
        if not isinstance(text, str):
            return str(text)
        return bleach.clean(text.strip())
    
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @app.route('/')
    def index():
        """Render user-facing form."""
        return render_template('form.html')
    
    @app.route('/submit', methods=['POST'])
    async def submit_application():
        """Handle form submission and trigger Temporal Workflow."""
        # Extract and sanitize form data
        name = sanitize_input(request.form.get('name', ''))
        email = sanitize_input(request.form.get('email', ''))
        loan_amount = request.form.get('loan_amount', '0')
        credit_score = request.form.get('credit_score', '0')
        annual_income = request.form.get('annual_income', '0')
        has_bankruptcy = request.form.get('has_bankruptcy', 'no')
        
        # Basic validation
        if not name or not email:
            return render_template('form.html', 
                                   error="Please fill out all required fields.",
                                   name=name, email=email, loan_amount=loan_amount,
                                   annual_income=annual_income, credit_score=credit_score,
                                   has_bankruptcy=has_bankruptcy)
        
        if not validate_email(email):
            return render_template('form.html', 
                                   error="Please provide a valid email address.",
                                   name=name, email=email, loan_amount=loan_amount,
                                   annual_income=annual_income, credit_score=credit_score,
                                   has_bankruptcy=has_bankruptcy)
        
        try:
            loan_amount = float(loan_amount)
            credit_score = int(credit_score)
            annual_income = float(annual_income)
            has_bankruptcy = (has_bankruptcy == 'yes')
        except ValueError:
            return render_template('form.html', 
                                   error="Invalid number format. Please check your inputs.",
                                   name=name, email=email)
        
        # Build application object
        application = {
            'name': name,
            'email': email,
            'loan_amount': loan_amount,
            'credit_score': credit_score,
            'annual_income': annual_income,
            'has_bankruptcy': has_bankruptcy
        }
        
        # Start Temporal Workflow
        workflow_id = f"loan-approval-{email.lower().replace('@', '-at-')}"
        
        try:
            # Execute workflow and wait for result
            result = await temporal_client.execute_workflow(
                LoanApprovalWorkflow.run,
                application,
                id=workflow_id,
                task_queue=TASK_QUEUE_NAME
            )
            
            # Handle different result statuses
            if result['status'] == 'error':
                error_msg = '; '.join(result.get('errors', ['Unknown error']))
                return render_template('form.html',
                                       error=error_msg,
                                       name=name, email=email, loan_amount=loan_amount,
                                       annual_income=annual_income, credit_score=credit_score,
                                       has_bankruptcy='yes' if has_bankruptcy else 'no')
            
            if result['status'] == 'duplicate':
                days = result.get('days_remaining', 7)
                error_msg = f"You have already submitted an application. You can resubmit in {days} day{'s' if days != 1 else ''}."
                return render_template('form.html',
                                       error=error_msg,
                                       name=name, email=email, loan_amount=loan_amount,
                                       annual_income=annual_income, credit_score=credit_score,
                                       has_bankruptcy='yes' if has_bankruptcy else 'no')
            
            # Success - show decision
            return render_template('result.html',
                                   decision=result['message'],
                                   application=application)
        
        except Exception as e:
            print(f"Error executing workflow: {str(e)}")
            return render_template('form.html',
                                   error="We're experiencing technical difficulties. Please try again later.",
                                   name=name, email=email)
    
    @app.route('/contact', methods=['POST'])
    async def contact_preference():
        """Handle contact preference using Temporal Workflow."""
        preference = request.form.get('preference', 'no')
        email = sanitize_input(request.form.get('email', ''))
        
        # Start Contact Preference Workflow
        workflow_id = f"contact-pref-{email.lower().replace('@', '-at-')}"
        
        try:
            result = await temporal_client.execute_workflow(
                ContactPreferenceWorkflow.run,
                args=[email, preference == 'yes'],
                id=workflow_id,
                task_queue=TASK_QUEUE_NAME
            )
            
            # Load message from messages.json
            import json
            with open('messages.json', 'r') as f:
                messages = json.load(f)
            
            pref_key = 'yes' if preference == 'yes' else 'no'
            message_template = messages['contact_preference'][pref_key]
            
            contact_message = {
                'title': message_template['title'],
                'message': message_template['message'].replace('{email}', email)
            }
            
            return render_template('result.html', contact_message=contact_message)
        
        except Exception as e:
            print(f"Error updating contact preference: {str(e)}")
            return render_template('result.html',
                                   error="Unable to update contact preference. Please try again.")
    
    @app.route('/api/evaluate', methods=['POST'])
    async def api_evaluate():
        """API endpoint for programmatic testing with JSON input."""
        try:
            application = request.get_json()
            
            # Validate required fields
            required = ['name', 'email', 'loan_amount', 'credit_score', 'annual_income', 'has_bankruptcy']
            for field in required:
                if field not in application:
                    return jsonify({'error': f'Missing required field: {field}'}), 400
            
            # Start Temporal Workflow
            workflow_id = f"loan-approval-api-{application['email'].lower().replace('@', '-at-')}"
            
            result = await temporal_client.execute_workflow(
                LoanApprovalWorkflow.run,
                application,
                id=workflow_id,
                task_queue=TASK_QUEUE_NAME
            )
            
            if result['status'] == 'duplicate':
                return jsonify({
                    'error': f"Email already submitted. Resubmission allowed in {result['days_remaining']} days.",
                    'existing_submission': result.get('existing_submission')
                }), 409
            
            return jsonify({
                'success': True,
                'decision': result['decision'],
                'message': result['message'],
                'application': result['application']
            })
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/submissions', methods=['GET'])
    def get_submissions():
        """Get all submissions (for programmatic review)."""
        import json
        try:
            with open('submissions.json', 'r') as f:
                submissions = json.load(f)
            return jsonify({'submissions': submissions})
        except FileNotFoundError:
            return jsonify({'submissions': []})
    
    return app


async def main():
    """Connect to Temporal Service and start Flask app."""
    # Connect to Temporal Service
    temporal_client = await Client.connect("localhost:7233")
    
    print("\n" + "="*60)
    print("✅ Connected to Temporal Service")
    print("🌐 Flask App Starting")
    print("="*60)
    print("URL: http://127.0.0.1:5001")
    print("Temporal Task Queue: " + TASK_QUEUE_NAME)
    print("="*60 + "\n")
    
    # Create Flask app with Temporal client
    app = create_app(temporal_client)
    
    # Run Flask app
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    asyncio.run(main())
