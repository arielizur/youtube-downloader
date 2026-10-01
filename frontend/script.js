document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('download-form');
    const submitBtn = document.getElementById('submit-btn');
    
    const statusCard = document.getElementById('status-card');
    const statusTitle = document.getElementById('status-title');
    const statusMessage = document.getElementById('status-message');
    const loaderContainer = document.getElementById('loader-container');
    const downloadLink = document.getElementById('download-link');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const youtubeUrl = document.getElementById('youtube-url').value;
        const formatType = document.getElementById('format').value;

        // איפוס ממשק
        submitBtn.disabled = true;
        statusCard.classList.remove('hidden');
        downloadLink.classList.add('hidden');
        loaderContainer.classList.remove('hidden');
        statusTitle.textContent = 'מתחיל הורדה...';
        statusTitle.classList.remove('error-text');
        statusMessage.textContent = 'שולח בקשה לשרת...';
        
        try {
            // 1. שליחת בקשה לשרת שלנו
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    youtube_url: youtubeUrl,
                    format_type: formatType
                })
            });

            if (!response.ok) {
                throw new Error('שגיאה בתקשורת עם השרת');
            }

            const data = await response.json();
            const jobId = data.job_id;

            // 2. בדיקת סטטוס רציפה
            const checkStatus = async () => {
                try {
                    const statusRes = await fetch(`/api/status/${jobId}`);
                    const statusData = await statusRes.json();

                    statusMessage.textContent = statusData.message;

                    if (statusData.status === 'done') {
                        // סיום בהצלחה
                        loaderContainer.classList.add('hidden');
                        statusTitle.textContent = 'מוכן! 🎉';
                        
                        downloadLink.href = `/api/file/${jobId}`;
                        downloadLink.download = statusData.filename;
                        downloadLink.classList.remove('hidden');
                        submitBtn.disabled = false;
                        
                        // לחיצה אוטומטית להורדה
                        setTimeout(() => {
                            window.location.href = `/api/file/${jobId}`;
                        }, 500);

                    } else if (statusData.status === 'error') {
                        throw new Error(statusData.message || 'אירעה שגיאה בהורדה');
                    } else {
                        setTimeout(checkStatus, 2000);
                    }
                } catch (err) {
                    showError(err.message);
                }
            };

            setTimeout(checkStatus, 2000);

        } catch (error) {
            showError(error.message);
        }
    });

    function showError(message) {
        loaderContainer.classList.add('hidden');
        statusTitle.textContent = 'שגיאה ❌';
        statusTitle.classList.add('error-text');
        statusMessage.textContent = message;
        submitBtn.disabled = false;
    }
});
