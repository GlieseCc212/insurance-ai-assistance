"""
Notification Service
Handles email and SMS notifications for claim updates and system alerts
"""
from typing import Dict, Any, List, Optional
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

from ..config import get_settings

settings = get_settings()


class EmailService:
    """Email notification service using SMTP"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False
    ) -> Dict[str, Any]:
        """Send email notification"""
        
        if not self.smtp_username or not self.smtp_password:
            return {
                'success': False,
                'error': 'SMTP credentials not configured'
            }
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_username
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Send email in a thread to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_smtp_email,
                msg
            )
            
            return {
                'success': True,
                'message': f'Email sent to {to_email}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to send email: {str(e)}'
            }
    
    def _send_smtp_email(self, msg: MIMEMultipart):
        """Send email using SMTP (blocking operation)"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
    
    async def send_claim_notification(
        self,
        to_email: str,
        claim_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send claim processing notification"""
        
        claim_id = claim_data.get('claim_id', 'Unknown')
        decision = claim_data.get('decision', 'Unknown')
        amount = claim_data.get('amount', 0)
        
        subject = f"Insurance Claim Update - {claim_id}"
        
        # Create HTML email body
        html_body = f"""
        <html>
        <head></head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #333; margin-bottom: 20px;">Insurance Claim Update</h2>
                    
                    <div style="background: white; padding: 20px; border-radius: 6px; margin-bottom: 20px;">
                        <h3 style="color: #0d6efd; margin-bottom: 15px;">Claim Details</h3>
                        <p><strong>Claim ID:</strong> {claim_id}</p>
                        <p><strong>Amount:</strong> ${amount:,.2f}</p>
                        <p><strong>Decision:</strong> <span style="color: {'#198754' if decision == 'APPROVED' else '#dc3545' if decision == 'DENIED' else '#ffc107'}; font-weight: bold;">{decision}</span></p>
                        <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 6px; margin-bottom: 20px;">
                        <h3 style="color: #0d6efd; margin-bottom: 15px;">Explanation</h3>
                        <p>{claim_data.get('explanation', 'No explanation provided.')}</p>
                    </div>
                    
                    {'<div style="background: #d1ecf1; padding: 15px; border-radius: 6px; border-left: 4px solid #bee5eb;">' +
                     '<p><strong>Next Steps:</strong> Payment processing will begin within 3-5 business days.</p></div>' if decision == 'APPROVED' else
                     '<div style="background: #f8d7da; padding: 15px; border-radius: 6px; border-left: 4px solid #f5c6cb;">' +
                     '<p><strong>Next Steps:</strong> You may appeal this decision by contacting our customer service.</p></div>' if decision == 'DENIED' else
                     '<div style="background: #fff3cd; padding: 15px; border-radius: 6px; border-left: 4px solid #ffeaa7;">' +
                     '<p><strong>Next Steps:</strong> A specialist will review your case within 2 business days.</p></div>'}
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 12px;">
                        <p>This is an automated message from your Insurance AI Assistant. Please do not reply to this email.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, html_body, is_html=True)
    
    async def send_document_processed_notification(
        self,
        to_email: str,
        document_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send document processing notification"""
        
        filename = document_data.get('filename', 'Unknown')
        document_id = document_data.get('document_id', 'Unknown')
        
        subject = "Policy Document Processed Successfully"
        
        html_body = f"""
        <html>
        <head></head>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
                    <h2 style="color: #333; margin-bottom: 20px;">Document Processing Complete</h2>
                    
                    <div style="background: white; padding: 20px; border-radius: 6px; margin-bottom: 20px;">
                        <h3 style="color: #0d6efd; margin-bottom: 15px;">Processing Summary</h3>
                        <p><strong>Document:</strong> {filename}</p>
                        <p><strong>Document ID:</strong> {document_id}</p>
                        <p><strong>Pages Processed:</strong> {document_data.get('pages_processed', 'N/A')}</p>
                        <p><strong>Processing Time:</strong> {document_data.get('processing_time', 'N/A')} seconds</p>
                        <p><strong>Status:</strong> <span style="color: #198754; font-weight: bold;">Successfully Processed</span></p>
                    </div>
                    
                    <div style="background: #d1ecf1; padding: 15px; border-radius: 6px; border-left: 4px solid #bee5eb;">
                        <p><strong>What's Next:</strong> Your policy document has been analyzed and indexed. You can now ask questions about your policy or submit claims for processing.</p>
                    </div>
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 12px;">
                        <p>This is an automated message from your Insurance AI Assistant.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(to_email, subject, html_body, is_html=True)


class SMSService:
    """SMS notification service using Twilio"""
    
    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.client = None
        
        if self.account_sid and self.auth_token:
            self.client = TwilioClient(self.account_sid, self.auth_token)
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
        from_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS notification"""
        
        if not self.client:
            return {
                'success': False,
                'error': 'Twilio credentials not configured'
            }
        
        try:
            # Send SMS in a thread to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._send_twilio_sms,
                to_phone,
                message,
                from_phone
            )
            
            return {
                'success': True,
                'message_sid': result.sid,
                'status': result.status
            }
            
        except TwilioRestException as e:
            return {
                'success': False,
                'error': f'Twilio error: {e.msg}',
                'error_code': e.code
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to send SMS: {str(e)}'
            }
    
    def _send_twilio_sms(self, to_phone: str, message: str, from_phone: Optional[str]):
        """Send SMS using Twilio (blocking operation)"""
        return self.client.messages.create(
            body=message,
            from_=from_phone or self.client.api.account.phone_numbers.list()[0].phone_number,
            to=to_phone
        )
    
    async def send_claim_alert(
        self,
        to_phone: str,
        claim_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send claim decision SMS alert"""
        
        claim_id = claim_data.get('claim_id', 'Unknown')[:8]  # Shorten for SMS
        decision = claim_data.get('decision', 'Unknown')
        
        message = f"Insurance Claim Update: Claim {claim_id} has been {decision}. Check your email for details."
        
        return await self.send_sms(to_phone, message)


class NotificationService:
    """Unified notification service combining email and SMS"""
    
    def __init__(self):
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    async def notify_claim_decision(
        self,
        claim_data: Dict[str, Any],
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send claim decision notification via email and/or SMS"""
        
        results = {
            'email': None,
            'sms': None,
            'success': False
        }
        
        # Send email notification
        if email:
            email_result = await self.email_service.send_claim_notification(email, claim_data)
            results['email'] = email_result
        
        # Send SMS notification
        if phone:
            sms_result = await self.sms_service.send_claim_alert(phone, claim_data)
            results['sms'] = sms_result
        
        # Consider successful if at least one notification was sent
        results['success'] = (
            (results['email'] and results['email'].get('success', False)) or
            (results['sms'] and results['sms'].get('success', False))
        )
        
        return results
    
    async def notify_document_processed(
        self,
        document_data: Dict[str, Any],
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send document processing notification"""
        
        if not email:
            return {
                'success': False,
                'error': 'No email address provided'
            }
        
        return await self.email_service.send_document_processed_notification(email, document_data)
    
    async def send_system_alert(
        self,
        message: str,
        alert_type: str = 'info',
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send system alert notification"""
        
        results = {
            'email': None,
            'sms': None,
            'success': False
        }
        
        subject = f"Insurance AI Assistant Alert - {alert_type.upper()}"
        
        # Send email alert
        if email:
            email_result = await self.email_service.send_email(
                email,
                subject,
                message,
                is_html=False
            )
            results['email'] = email_result
        
        # Send SMS alert (if critical)
        if phone and alert_type in ['error', 'critical']:
            sms_result = await self.sms_service.send_sms(phone, f"ALERT: {message}")
            results['sms'] = sms_result
        
        results['success'] = (
            (results['email'] and results['email'].get('success', False)) or
            (results['sms'] and results['sms'].get('success', False))
        )
        
        return results
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of notification services"""
        return {
            'email': {
                'configured': bool(self.email_service.smtp_username and self.email_service.smtp_password),
                'smtp_server': self.email_service.smtp_server,
                'smtp_port': self.email_service.smtp_port
            },
            'sms': {
                'configured': bool(self.sms_service.client),
                'provider': 'Twilio' if self.sms_service.client else None
            }
        }


# Global instance
notification_service = NotificationService()