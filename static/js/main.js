document.addEventListener('DOMContentLoaded', function () {
    // --- AI Synergy Modal Logic ---
    const aiButton = document.getElementById('get-ai-synergy');
    if (aiButton) {
        const aiModal = new bootstrap.Modal(document.getElementById('aiSynergyModal'));
        const aiResultContent = document.getElementById('ai-result-content');

        aiButton.addEventListener('click', function () {
            const projectId = this.dataset.projectId;
            aiResultContent.innerHTML = '<p class.text-center">Analyzing project...</p>';
            aiModal.show();

            fetch(`/get_ai_synergy/${projectId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        aiResultContent.innerHTML = `<p class="text-danger">${data.error}</p>`;
                    } else {
                        let formattedHtml = data.analysis.replace(/\n/g, '<br>');
                        formattedHtml = formattedHtml.replace(/### (.*)/g, '<h3>$1</h3>');
                        formattedHtml = formattedHtml.replace(/\*\*(.*)\*\*/g, '<strong>$1</strong>');
                        aiResultContent.innerHTML = formattedHtml;
                    }
                })
                .catch(error => {
                    aiResultContent.innerHTML = '<p class="text-danger">Failed to fetch AI analysis.</p>';
                });
        });
    }

    // --- AI Priority Calculation Logic ---
    const priorityButton = document.getElementById('calculate-priority');
    if (priorityButton) {
        priorityButton.addEventListener('click', function () {
            const projectId = this.dataset.projectId;
            this.disabled = true;
            this.innerHTML = "Calculating...";

            fetch(`/calculate_priority/${projectId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        window.location.reload();
                    }
                })
                .catch(error => {
                    alert('An error occurred while calculating priorities.');
                })
                .finally(() => {
                    this.disabled = false;
                    this.innerHTML = "Calculate AI Priority 🚀";
                });
        });
    }
});