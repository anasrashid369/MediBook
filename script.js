document.getElementById('appointmentForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById('submitBtn');
    const formContainer = document.getElementById('booking-form');
    const confContainer = document.getElementById('confirmation');

    // 1. Gather Data
    const formData = {
        fullName: document.getElementById('fullName').value,
        email: document.getElementById('email').value,
        date: document.getElementById('date').value,
        time: document.getElementById('time').value,
        doctor: document.getElementById('doctor').value,
        reason: document.getElementById('reason').value
    };

    // 2. UI Loading State
    submitBtn.innerText = "Processing...";
    submitBtn.classList.add('loading');

    try {
        // 3. Fetch Call to API Gateway
        // Replace this URL with your actual Invoke URL from AWS API Gateway
        const response = await fetch('YOUR_API_GATEWAY_URL/appointments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (response.ok) {
            // 4. Show Success State
            document.getElementById('refId').innerText = result.appointmentId || "APT-" + Math.floor(Math.random() * 100000);
            document.getElementById('confDetails').innerText = `${formData.date} at ${formData.time} with ${formData.doctor}`;
            
            formContainer.style.display = 'none';
            confContainer.style.display = 'block';
        } else {
            alert("Error: " + (result.message || "Failed to book appointment"));
        }
    } catch (error) {
        console.error("Error connecting to API:", error);
        alert("Could not connect to the server. Check CORS settings in API Gateway.");
    } finally {
        submitBtn.innerText = "Book Appointment";
        submitBtn.classList.remove('loading');
    }
});