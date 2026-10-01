document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('download-form');
    const submitBtn = document.getElementById('submit-btn');
    
    const statusCard = document.getElementById('status-card');
    const statusTitle = document.getElementById('status-title');
    const statusMessage = document.getElementById('status-message');
    const loaderContainer = document.getElementById('loader-container');
    const downloadLink = document.getElementById('download-link');

    let pollingInterval = null;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const baseUrl = document.getElementById('base-url').value;
        const youtubeUrl = document.getElementById('youtube-url').value;
        const formatType = document.getElementById('format').value;

        // Reset UI
        submitBtn.disabled = true;
        statusCard.classList.remove('hidden');
        downloadLink.classList.add('hidden');
        loaderContainer.classList.remove('hidden');
        statusTitle.textContent = 'שולח בקשה...';
        statusTitle.classList.remove('error-text');
        statusMessage.textContent = 'מתחיל את התהליך בשרת.';
        
        if (pollingInterval) clearInterval(pollingInterval);

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    base_url: baseUrl,
                    youtube_url: youtubeUrl,
                    format_type: formatType
                })
            });

            if (!response.ok) {
                throw new Error('שגיאה בחיבור לשרת');
            }

            const data = await response.json();
            const jobId = data.job_id;
            
            // Start polling
            pollStatus(jobId);

        } catch (error) {
            showError(error.message);
        }
    });

    function pollStatus(jobId) {
        pollingInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/status/${jobId}`);
                if (!res.ok) throw new Error('שגיאה בבדיקת סטטוס');
                
                const data = await res.json();
                
                // Update UI based on status
                statusMessage.textContent = data.message || 'מעבד...';

                if (data.status === 'running') {
                    statusTitle.textContent = 'מבצע המרה';
                } else if (data.status === 'done') {
                    clearInterval(pollingInterval);
                    showSuccess(jobId, data.filename, data.message);
                } else if (data.status === 'error') {
                    clearInterval(pollingInterval);
                    showError(data.message || 'אירעה שגיאה לא ידועה');
                }

            } catch (error) {
                clearInterval(pollingInterval);
                showError('אבד החיבור לשרת בזמן בדיקת הסטטוס.');
            }
        }, 2000); // Poll every 2 seconds
    }

    function showSuccess(jobId, filename, message) {
        loaderContainer.classList.add('hidden');
        statusTitle.textContent = 'ההמרה הסתיימה בהצלחה! 🎉';
        statusMessage.textContent = message;
        
        downloadLink.href = `/api/file/${jobId}`;
        downloadLink.download = filename;
        downloadLink.classList.remove('hidden');
        
        submitBtn.disabled = false;
        
        // Auto-click the download link
        setTimeout(() => {
            downloadLink.click();
        }, 500);
    }

    function showError(message) {
        loaderContainer.classList.add('hidden');
        statusTitle.textContent = 'שגיאה ❌';
        statusTitle.classList.add('error-text');
        statusMessage.textContent = message;
        submitBtn.disabled = false;
    }
});
