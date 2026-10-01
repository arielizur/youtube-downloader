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

        // Reset UI
        submitBtn.disabled = true;
        statusCard.classList.remove('hidden');
        downloadLink.classList.add('hidden');
        loaderContainer.classList.remove('hidden');
        statusTitle.textContent = 'מחלץ פרטים...';
        statusTitle.classList.remove('error-text');
        statusMessage.textContent = 'מתחיל את התהליך (רץ ישירות מהדפדפן שלך!)';
        
        // חילוץ ID מהקישור
        const videoIdMatch = youtubeUrl.match(/(?:v=|\/)([0-9A-Za-z_-]{11}).*/);
        if (!videoIdMatch) {
            showError("לא נמצא מזהה סרטון תקין בקישור.");
            return;
        }
        const videoId = videoIdMatch[1];

        try {
            statusMessage.textContent = 'מתחבר לשרתי ההמרה...';
            
            // 1. קריאה ראשונית ל-API
            const initUrl = `https://fancy-sea-5d3d.holy-breeze-fec5.workers.dev/?m=i&v=${videoId}&f=${formatType}&_=${Date.now()}`;
            const initRes = await fetch(initUrl);
            const initData = await initRes.json();
            
            if (initData.error > 0) {
                throw new Error("שגיאה בשרת ההמרה: " + initData.error);
            }

            const title = initData.title || "video";
            const progressUrl = initData.progressURL;
            const downloadUrl = initData.downloadURL;

            statusTitle.textContent = 'ממיר סרטון...';
            
            // 2. המתנה (Polling)
            const checkProgress = async () => {
                statusMessage.textContent = `מעבד: ${title}...`;
                const pRes = await fetch(`${progressUrl}&_=${Date.now()}`);
                const pData = await pRes.json();
                
                if (pData.progress === 3) {
                    showSuccess(downloadUrl, `${title}.${formatType}`, "ההמרה הסתיימה! מוריד כעת...");
                } else if (pData.error > 0) {
                    showError("שגיאה במהלך ההמרה.");
                } else {
                    setTimeout(checkProgress, 3000);
                }
            };
            
            checkProgress();

        } catch (error) {
            showError(error.message || "שגיאת חיבור");
        }
    });

    function showSuccess(downloadUrl, filename, message) {
        loaderContainer.classList.add('hidden');
        statusTitle.textContent = 'מוכן! 🎉';
        statusMessage.textContent = message;
        
        downloadLink.href = downloadUrl;
        downloadLink.download = filename;
        downloadLink.classList.remove('hidden');
        
        submitBtn.disabled = false;
        
        setTimeout(() => {
            // לחיצה אוטומטית שפותחת את הקובץ
            window.location.href = downloadUrl;
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
