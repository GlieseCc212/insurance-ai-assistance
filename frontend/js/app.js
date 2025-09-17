/**
 * Insurance AI Assistant - Frontend JavaScript
 */

const API_BASE_URL = '/api/v1';

// Utility functions
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    element.innerHTML = '<div class="spinner"></div> Processing...';
    element.style.display = 'block';
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    element.style.display = 'none';
}

function showResult(elementId, content, type = 'info') {
    const element = document.getElementById(elementId);
    const alertClass = type === 'error' ? 'alert-danger' : 
                     type === 'success' ? 'alert-success' : 
                     type === 'warning' ? 'alert-warning' : 'alert-info';
    
    element.innerHTML = `<div class="alert ${alertClass}" role="alert">${content}</div>`;
    element.style.display = 'block';
}

function createResultBox(content, type = 'info') {
    const typeClass = type === 'approved' ? 'result-approved' : 
                     type === 'rejected' ? 'result-rejected' : 'result-info';
    
    return `<div class="result-box ${typeClass}">${content}</div>`;
}

// Document Upload Functionality
document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData();
    const fileInput = document.getElementById('policyFile');
    const policyTypeInput = document.getElementById('policyType');
    
    if (!fileInput.files[0]) {
        showResult('uploadResult', 'Please select a file to upload.', 'error');
        return;
    }
    
    formData.append('file', fileInput.files[0]);
    formData.append('policy_type', policyTypeInput.value);
    
    showLoading('uploadResult');
    
    try {
        const response = await fetch(`${API_BASE_URL}/documents/upload`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            const content = `
                <h5><i class="fas fa-check-circle text-success"></i> Document Uploaded Successfully</h5>
                <p><strong>Document ID:</strong> ${result.document_id}</p>
                <p><strong>Pages Processed:</strong> ${result.pages_processed || 'N/A'}</p>
                <p><strong>Text Chunks:</strong> ${result.chunks_created || 'N/A'}</p>
                <p><strong>Processing Time:</strong> ${result.processing_time || 'N/A'}s</p>
                <div class="mt-3">
                    <small class="text-muted">
                        Your document has been processed and indexed. You can now ask questions about your policy.
                    </small>
                </div>
            `;
            showResult('uploadResult', createResultBox(content, 'approved'), 'success');
        } else {
            showResult('uploadResult', `Error: ${result.detail || 'Upload failed'}`, 'error');
        }
    } catch (error) {
        showResult('uploadResult', `Network error: ${error.message}`, 'error');
    }
});

// Query Functionality
document.getElementById('queryForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const queryInput = document.getElementById('userQuery');
    const query = queryInput.value.trim();
    
    if (!query) {
        showResult('queryResult', 'Please enter a question about your policy.', 'error');
        return;
    }
    
    showLoading('queryResult');
    
    try {
        const response = await fetch(`${API_BASE_URL}/queries/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            let content = `
                <h5><i class="fas fa-lightbulb text-primary"></i> Answer</h5>
                <p>${result.answer}</p>
            `;
            
            if (result.relevant_clauses && result.relevant_clauses.length > 0) {
                content += `
                    <div class="explanation">
                        <h6><i class="fas fa-book"></i> Relevant Policy Clauses</h6>
                `;
                
                result.relevant_clauses.forEach(clause => {
                    content += `
                        <div class="clause-reference">
                            <strong>Section ${clause.section || 'N/A'}:</strong> ${clause.text}
                            ${clause.confidence ? `<br><small>Confidence: ${(clause.confidence * 100).toFixed(1)}%</small>` : ''}
                        </div>
                    `;
                });
                
                content += `</div>`;
            }
            
            if (result.confidence_score) {
                const confidencePercent = (result.confidence_score * 100).toFixed(1);
                content += `
                    <div class="mt-2">
                        <small class="text-muted">
                            <i class="fas fa-chart-bar"></i> Answer Confidence: ${confidencePercent}%
                        </small>
                    </div>
                `;
            }
            
            showResult('queryResult', createResultBox(content), 'success');
        } else {
            showResult('queryResult', `Error: ${result.detail || 'Query failed'}`, 'error');
        }
    } catch (error) {
        showResult('queryResult', `Network error: ${error.message}`, 'error');
    }
});

// Claims Processing Functionality
document.getElementById('claimForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const claimData = {
        claim_type: formData.get('claim_type'),
        amount: parseFloat(formData.get('amount')),
        description: formData.get('description'),
        incident_date: formData.get('incident_date')
    };
    
    showLoading('claimResult');
    
    try {
        const response = await fetch(`${API_BASE_URL}/claims/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(claimData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            const isApproved = result.decision === 'APPROVED';
            const statusIcon = isApproved ? 
                '<i class="fas fa-check-circle text-success"></i>' : 
                '<i class="fas fa-times-circle text-danger"></i>';
            
            let content = `
                <h5>${statusIcon} Claim ${result.decision}</h5>
                <div class="row mb-3">
                    <div class="col-md-6">
                        <strong>Claim ID:</strong> ${result.claim_id}
                    </div>
                    <div class="col-md-6">
                        <strong>Amount:</strong> $${claimData.amount.toFixed(2)}
                    </div>
                </div>
            `;
            
            if (result.explanation) {
                content += `
                    <div class="explanation">
                        <h6><i class="fas fa-info-circle"></i> Explanation</h6>
                        <p>${result.explanation}</p>
                    </div>
                `;
            }
            
            if (result.policy_references && result.policy_references.length > 0) {
                content += `
                    <div class="explanation">
                        <h6><i class="fas fa-file-contract"></i> Policy References</h6>
                `;
                
                result.policy_references.forEach(ref => {
                    content += `
                        <div class="clause-reference">
                            <strong>Clause ${ref.clause_number}:</strong> ${ref.clause_text}
                        </div>
                    `;
                });
                
                content += `</div>`;
            }
            
            if (result.fraud_score !== undefined) {
                const riskLevel = result.fraud_score > 0.7 ? 'High' : 
                                result.fraud_score > 0.4 ? 'Medium' : 'Low';
                const riskColor = result.fraud_score > 0.7 ? 'danger' : 
                                result.fraud_score > 0.4 ? 'warning' : 'success';
                
                content += `
                    <div class="mt-3">
                        <small class="text-${riskColor}">
                            <i class="fas fa-shield-alt"></i> Fraud Risk: ${riskLevel} (${(result.fraud_score * 100).toFixed(1)}%)
                        </small>
                    </div>
                `;
            }
            
            const resultType = isApproved ? 'approved' : 'rejected';
            showResult('claimResult', createResultBox(content, resultType), 'success');
        } else {
            showResult('claimResult', `Error: ${result.detail || 'Claim processing failed'}`, 'error');
        }
    } catch (error) {
        showResult('claimResult', `Network error: ${error.message}`, 'error');
    }
});

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Insurance AI Assistant loaded successfully');
    
    // Check API health on load
    fetch(`${API_BASE_URL}/health`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'healthy') {
                console.log('API is healthy and ready');
            }
        })
        .catch(error => {
            console.warn('API health check failed:', error);
        });
});